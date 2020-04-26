import pandas as pd
import numpy as np
import os
import logging

log = logging.getLogger('run-model')

class Preprocessor(object):
    def __init__(self, args):
        self.args = args
        self.selected_zones = None

    def read_deaths_data(self, zones):
        all_zones = set(zones.keys()).union(set(zones.values()))

        # concatenate all inputfiles
        df = pd.concat([pd.read_csv(input_file) for input_file in self.args.input_files])
        log.info("{} rows in data".format(len(df)))
        df.loc[df['countriesAndTerritories'] == "United_Kingdom", 'countriesAndTerritories'] = "United Kingdom"
        df['dateRep'] = pd.to_datetime(df['dateRep'], format="%d/%m/%Y")

        if self.args.maxdate: #  filter by max date
            len_before = len(df)
            df = df[df['dateRep'] > self.args.maxdate]
            len_after = len(df)
            log.warning("Applyed max_date {}: from {} to {} rows".format(
                self.args.maxdate,
                len_before,
                len_after
            ))

        # limit to active_countries and regions
        df = df[df['countriesAndTerritories'].apply(
            lambda zone: zone in zones
            )]

        # Trim countries and regions that fail the number of death test.
        max_deaths = df[['countriesAndTerritories', 'deaths']]\
            .groupby('countriesAndTerritories').agg('sum')

        # remove zones that do not reach death_thresh_epi_start
        less_deaths = max_deaths[max_deaths['deaths'] <= self.args.death_thresh_epi_start]
        max_deaths = max_deaths[max_deaths['deaths'] > self.args.death_thresh_epi_start]

        removed_zones = less_deaths.index.tolist()
        filtered_zones = max_deaths.index.tolist()
        ### FOR DEBUG ###
        #filtered_zones = ['Italy']
        #filtered_zones = ['Occitanie']

        df = df[df['countriesAndTerritories'].apply(lambda zone: zone in filtered_zones)]
        if removed_zones:
            log.warning("WARNING Removed low death zones: {}".format(removed_zones))

        self.selected_zones = set(df['countriesAndTerritories'].unique())

        missing_zones = all_zones.difference(self.selected_zones)
        log.info("Selected zones: {}".format(self.selected_zones))
        if missing_zones:
            log.warning("WARNING Missing zones: {}".format(missing_zones))

        # filter region_to_country_map
        region_to_country_map = {k:v for k,v in zones.items() if k in self.selected_zones}

        return df, region_to_country_map

    def read_npis(self, zones):

        # List of Non-Pharmaceutical Interventions (NPI) effective dates by zones
        df_interventions = pd.read_csv(
            os.path.join(self.args.root_dir, "data", "interventions.csv")
            )

        # For the moment to ensure data is consistent for UK **@@@***!!!
        df_interventions.loc[
            df_interventions['Country'] == "United_Kingdom", 'Country'
        ] = "United Kingdom"

        # filtering by zones
        df_interventions = df_interventions[
            df_interventions['Country'].apply(
                lambda country: country in zones or country in zones.values()
            )]
        
        # transpose
        df_interventions = df_interventions\
            .groupby('Country')[['Type', 'Date effective']]\
                .apply(
                    lambda df: df.reset_index(drop=True)
                        .groupby('Type').apply(
                            lambda df: df[['Date effective']]
                                .reset_index(drop=True)
                        ).unstack()
                        .transpose()
                ) 
        df_interventions = df_interventions.reset_index().drop(columns=['level_1', 'level_2'])

        covariate_names = self.args.covariates
        if "Any" in covariate_names:
            # Any is a computed covariate at the end
            df_interventions['Any'] = df_interventions['Lockdown']
        

        df_interventions = df_interventions[['Country'] + covariate_names]
        #covariate_names = df_interventions.columns[1:self.args.num_covariates + 1]
        log.debug("Using covariates {}".format(covariate_names))

        # convert to datetime
        df_interventions[covariate_names] = pd.to_datetime(
            df_interventions[covariate_names].stack(),
            errors='ignore', 
            format="%d.%m.%Y"
            ).unstack()

        # filter date max
        if self.args.maxdate:
            df_interventions = df_interventions[df_interventions['Date effective'] < self.args.maxdate]
        df_interventions = df_interventions[df_interventions['Country'].apply(
            lambda country: country in self.selected_zones
        )]
        log.info("{} NPI rows".format(len(df_interventions)))


        return df_interventions

    def read_ifr(self, zones):
        # weighted Infection Fatality Rate by zone
        #df_ifr = pd.read_csv("data/weighted_fatality.csv")
        df_ifr = pd.read_csv(
            os.path.join(self.args.root_dir, "data", "popt_ifr.csv")
            )
        col_zone = [col for col in df_ifr.columns if 'country' in col.lower()][0]
        df_ifr.rename(columns={col_zone: 'country'}, inplace=True)

        # if weighted_fatality.csv format, rename columns 
        if "weighted_fatality" in df_ifr.columns:
            df_ifr.rename(columns={"weighted_fatality": 'ifr'}, inplace=True)
            df_ifr.rename(columns={"population": 'popt'}, inplace=True)

        df_ifr = df_ifr[df_ifr['country'].apply(
            lambda country: country in zones or country in zones.values()
        )]

        return df_ifr


    def read_serial(self):
        # serial .??? liste de fit ??? 
        df_serial = pd.read_csv(
            os.path.join(self.args.root_dir, "data", "serial_interval.csv")
        )
        log.info("Len of serial : {} N2 : {}, needs padding: {}".format(
            len(df_serial), self.args.N2, len(df_serial) < self.args.N2
        ))
        df_serial.drop(columns=[col for col in df_serial.columns if col != "fit"], inplace=True)
        df_serial['fit']
        # padd with 0 if needed (lenght shorter than N2)
        if len(df_serial) < self.args.N2:
            df_serial = pd.concat([
                df_serial,
                pd.DataFrame({'fit':np.zeros(self.args.N2 - len(df_serial))})
            ])
        #print(df_serial.tail())
        return df_serial
