import logging
import os
import random 
import sys

#import numpy as np
import pystan
#import pandas as pd
#from datetime import datetime  
#from pathlib import Path

import pickle

from utils.argparser import parse_args
from utils.maths import get_gamma, convolution, poly, ECDF
from utils.experiment import create_experiment, save_input
from utils.zones import read_zones
from utils.preprocess import Preprocessor
from utils.stan_data import compute_stan_data
from utils.postprocess import postprocess

def main(args):
    log = logging.getLogger('run-model')
    exp_dir = create_experiment(args)
    region_to_country_map = read_zones(args)

    preprocessor = Preprocessor(args)

    df_cases, region_to_country_map = preprocessor.read_deaths_data(zones=region_to_country_map) 
    df_interventions = preprocessor.read_npis(region_to_country_map)
    df_ifr = preprocessor.read_ifr(region_to_country_map)
    df_serial = preprocessor.read_serial()

    # Gamma distributions for Infection to onset and onset to death
    infection_to_onset = {"mean":5.1, "deviation":0.86}
    onset_to_death = {"mean":18.8, "deviation":0.45}

    stan_data = compute_stan_data(
        args, 
        region_to_country_map, 
        df_cases, 
        df_interventions, 
        df_ifr, 
        df_serial,
        infection_to_onset,
        onset_to_death
        )

    # Note : stops here if we set --only-dump-input
    save_input(args, stan_data, exp_dir)

    # with open("model_input_R.pkl", "rb") as fd:
    #     Rstan_data = pickle.load(fd)
    #     Rstan_data['N0'] = int(Rstan_data['N0'])
    #     Rstan_data['N2'] = int(Rstan_data['N2'])
    #     import numpy as np 
    #     Rstan_data['cases'] = Rstan_data['cases'].astype(np.int)
    #     Rstan_data['deaths'] = Rstan_data['deaths'].astype(np.int)
    #     Rstan_data['EpidemicStart'] = [int(el) for el in Rstan_data['EpidemicStart']]
#    field = 'SI'
#    stan_data[field] = Rstan_data[field]

    log.info("Load model {}".format(args.stanmodel))
    sm = pystan.StanModel(file="stan-models/{}.stan".format(args.stanmodel))

    zones = stan_data['regions']
    # del from stan_data because model doesn't like text
    del stan_data['regions']
    
    stan_args = {
        "data": stan_data,
        "seed": args.seed,
        "chains":args.chains,
        "n_jobs":args.njobs,
        "control": {"adapt_delta": 0.95, "max_treedepth": 10},
    }

    if args.full:
        log.info("Run model {} with data".format(args.stanmodel))
        fit = sm.sampling(
            iter=args.iter,warmup=args.warmup,
            **stan_args
        )
    else:
        log.info("DEBUG MODE : Run model {} with data limiting to 40 iters".format(args.stanmodel))
        fit = sm.sampling(
            iter=40,warmup=20,
            **stan_args
        )

    with open(os.path.join(exp_dir, "output", "model.pkl"), "wb") as fd:
        pickle.dump((sm, fit), fd)

    output_dict = fit.extract()

    postprocess(args, exp_dir, output_dict, zones)

if __name__ == "__main__":
    args = parse_args()
    main(args)


"""
## get IFR and population from same file


out = rstan::extract(fit)
prediction = out$prediction
estimated.deaths = out$E_deaths
estimated.deaths.cf = out$E_deaths0

save.image(paste0('results/',run_name,'.Rdata'))

countries <- names(region_to_country_map)
save(
  fit, prediction, dates,reported_cases,deaths_by_country,countries,
  region_to_country_map, estimated.deaths, estimated.deaths.cf, 
  out,covariates,infection_to_onset, onset_to_death,
  file=paste0('results/',run_name,'-stanfit.Rdata'))

postprocess_simulation(run_name, out, countries, dates)
"""