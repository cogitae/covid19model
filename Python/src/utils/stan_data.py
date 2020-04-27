import logging
import os
import random 
import sys

import numpy as np
import pystan
import pandas as pd
from datetime import datetime  
#from pathlib import Path

#import pickle

from utils.argparser import parse_args
from utils.maths import get_gamma, convolution, poly, ECDF


def compute_stan_data(
    args, 
    region_to_country_map, 
    df_cases, 
    df_interventions, 
    df_ifr, 
    df_serial,
    infection_to_onset,
    onset_to_death
    ):
    """ Compute the STAN data """
    log = logging.getLogger('run-model')

    num_zones = len(region_to_country_map)
    num_covariates = len(args.covariates)
    covariate_names = args.covariates

    # assume that IFR is probability of dying given infection
    x1 = get_gamma(infection_to_onset["mean"], infection_to_onset["deviation"])
    # infection-to-onset ----> do all people who are infected get to onset?
    x2 = get_gamma(onset_to_death["mean"], onset_to_death["deviation"])

    # CDF of sum of 2 gamma distributions
    gamma_cdf = ECDF(x1 + x2)

    stan_data = {}

    # M, number of countries
    stan_data["M"] = num_zones
    # TODO: this is hardcoded in base.r, beware
    stan_data["N0"] = num_covariates
    stan_data["N2"] = args.N2
    stan_data["SI"] = df_serial["fit"][:args.N2]
    stan_data["x"] = np.linspace(1, args.N2, args.N2)

    # TODO: we will use lists, but we need to be careful of stack memory in the future
    stan_data["pop"] = [] # population
    stan_data["EpidemicStart"] = [] # start of epidemic in zone
    stan_data["N"] = [] 
    # initialise with number of covariates
    for i in range(1, num_covariates+1):
        stan_data["covariate{}".format(i)] = np.zeros((args.N2, num_zones))

    # store the covariates in a numpy array, initialised
    stan_data["deaths"] = np.ones((args.N2, num_zones)) * (-1)
    stan_data["cases"] = np.ones((args.N2, num_zones)) * (-1)
    stan_data["f"] = np.zeros((args.N2, num_zones))

    # for exploratory/debug add list of zone names
    stan_data["regions"] = []

    # we will generate the dataset in this country order. Could also use a pandas dataframe, but not necessary in my opinion
    for country_num, region in enumerate(region_to_country_map):
        stan_data["regions"].append(region)

        country = region_to_country_map[region]
        log.info("Processing {} in {}".format(region, country))

        row_zone_ifr = df_ifr[df_ifr["country"] == country] 
        zone_ifr = row_zone_ifr["ifr"].values[0]
        stan_data["pop"].append(row_zone_ifr["popt"].values[0])
        
        covariates1 = df_interventions.loc[
            df_interventions["Country"] == country, covariate_names
        ]

        cases = df_cases[df_cases["countriesAndTerritories"] == region] #.copy()
        cases = cases.sort_values(by="t")
        cases = cases.reset_index()

        # when the first case occurs
        index = np.where(cases["cases"] > 0)[0].min() 
        # when the cumulative deaths reaches 10
        index_1 = np.where(cases["deaths"].cumsum() >= args.death_thresh_epi_start)[0].min()
        # 30 days before 10th death
        index_2 = index_1 - args.death_days_before_thresh_epi_start

        # TODO: what is the latter?
        if (index_2 < 0):
            # pad zeros before
            log.info(
                "Adding zero-padding size : {}".format(
                    -index_2
                )
            )
            padding = np.zeros(-index_2)
            epidemicStart = args.death_days_before_thresh_epi_start + 1
        else:
            log.info(
                "First non-zero cases is on day {} for '{}', and 30 days before 10 deaths is day {}".format(
                    index, region, index_2
                )
            )
            padding = np.zeros(0)
            # # only care about this timeframe
            cases = cases[index_2:]
            epidemicStart = index_1 + 1 - index_2

        # update Epidemic Start day for each country
        # starts the day having 10 cumulated deaths relatively to index_2
        # +1 is for STAN indexing from 1, not from 0
        stan_data["EpidemicStart"].append(epidemicStart)

        # turn intervention dates into boolean
        for covariate in covariate_names:
            cases[covariate] = (
                cases["dateRep"] >= covariates1[covariate].iloc[0]#.values[0]
            ) * 1

        # record dates for cases in the country
        cases[country] = cases["dateRep"]

        # Hazard estimation
        log.debug("{} has {} data".format(region, len(cases)))
        N = len(cases) + len(padding)

        # number of days to forecast
        forecast = args.N2 - N

        if forecast < 0:
            raise ValueError("Increase N2 to at least {} to make it work. N2=N, forecast=N2-N".format(N))

        # discrete hazard rate from time t=0,...,99
        h = np.zeros(args.N2)

        h[0] = convolution(1.5, zone_ifr, gamma_cdf) - convolution(0, zone_ifr, gamma_cdf)

        for i in range(1, len(h)):
            h[i] = (convolution(i + 0.5, zone_ifr, gamma_cdf) - convolution(i - 0.5, zone_ifr, gamma_cdf)) / (
                1 - convolution(i - 0.5, zone_ifr, gamma_cdf)
            )

        s = np.zeros(args.N2)
        s[0] = 1
        for i in range(1, args.N2):
            s[i] = s[i - 1] * (1 - h[i - 1])

        # check some consistency
        if sum(cases["deaths"] < 0) != 0:
            log.error('Negative deaths data in dataset. You may accept with --accept-negative-data')
            if not args.accept_negative_data:
                sys.exit(-3)
        if sum(cases["cases"] < 0) != 0:
            log.error('Negative deaths data in dataset. You may accept with --accept-negative-data')
            if not args.accept_negative_data:
                sys.exit(-3)
        # slot in these values
        stan_data["N"].append(N)
        stan_data["f"][:, country_num] = h * s
        #print(stan_data["f"][:, country_num])
        #print(stan_data["f"][:, country_num].shape)
        #sys.exit(0)
        #stan_data["y"].append(cases["cases"].values[0])
        stan_data["deaths"][:len(padding), country_num] = padding
        stan_data["deaths"][len(padding):N, country_num] = cases["deaths"] #.cumsum()
        stan_data["cases"][:len(padding), country_num] = padding
        stan_data["cases"][len(padding):N, country_num] = cases["cases"] #.cumsum()
        # 0 
        covariates2 = np.zeros((args.N2, num_covariates))
        #covariates2[:N, :len(covariate_names)] = cases[covariate_names].values
        covariates2[len(padding):N, :] = cases[covariate_names].values
        covariates2[N:args.N2, :] = covariates2[N - 1, :]
        covariates2 = pd.DataFrame(covariates2, columns=covariate_names)

        # checkl some consistency
        def check_range(df_to_check, idxmin, idxmax):
            df_test = df_to_check[idxmin:idxmax] < 0
            if df_test.sum() != 0:
                print("{} - {} : {}".format(
                    idxmin,
                    idxmax,
                    np.where(df_test < 0)
                ))
                if df_test.sum() != 0:
                    log.error('Negative data in dataset. You may accept with --accept-negative-data')
                    if not args.accept_negative_data:
                        sys.exit(-3)
                    

        check_range(stan_data["deaths"][:, country_num], epidemicStart - 1,N-1)
        check_range(stan_data["cases"][:, country_num], epidemicStart - 1,N-1)
        check_range(stan_data["deaths"][:, country_num], epidemicStart,N)
        check_range(stan_data["cases"][:, country_num], epidemicStart,N)
        
        # specific computed covariate 'Any' 
        if "Any" in covariate_names:
            covariates2['Any'] = covariates2.values.any(axis=1) * 1 

        for j, covariate in enumerate(covariate_names):
            stan_data["covariate{}".format(j+1)][:, country_num] = covariates2[
                covariate
            ]

        stan_data["cases"] = stan_data["cases"].astype(int) 
        stan_data["deaths"] = stan_data["deaths"].astype(int)


    # adjustments after checking against R pickled data
    stan_data['x'] = stan_data['x'].tolist()
    stan_data['SI'] = stan_data['SI'].tolist()

    stan_data["covariates"] = np.zeros((num_zones, args.N2, num_covariates))
    for j in range(len(args.covariates)):
        stan_data["covariates"][:,:,j] = np.swapaxes(stan_data["covariate{}".format(j+1)], 0, 1)

    #print(np.where(np.isnan(stan_data["covariates"])))
    #for i in range(num_covariates):
    #    cov = "covariate{}".format(i + 1)
    #    print(cov, np.where(np.isnan(stan_data[cov])))

    return stan_data