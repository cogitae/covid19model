import argparse
import logging
import os
import pathlib
import pandas as pd

#import pyreadr
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('feth-ecdc')


def parse_args():
    parser = argparse.ArgumentParser("Fetch ECDC data")
    parser.add_argument("--url", type=str, 
        default="https://opendata.ecdc.europa.eu/covid19/casedistribution/csv"
        )
    parser.add_argument("--local-file", type=pathlib.Path, default=None)
    parser.add_argument("--dest-file", type=pathlib.Path, 
        default="data/COVID-19-up-to-date_formated.csv"
        )
    parser.add_argument("--dont-use-cache", action='store_true')
    parser.add_argument("--debug", action='store_true')
    
    parser.add_argument("--version", type=int, default=1)

    return parser.parse_args()

def load_csv(filename):
    try:
        df = pd.read_csv(filename)
    except Exception as e:
        log.exception("Reading CSV from ECDC", e)
    return df

def adapt_df(df):
    log.info('Adapting')
    try:
        #  decimal date : date <- ymd("2009-02-10")
        #  decimal_date(date)  # 2009.11
        # 365 for number of days should be enough approx
        ddates = pd.to_datetime(df['dateRep'], format='%d/%m/%Y')
        df['t'] = ddates.apply(
            lambda dt: round(dt.year + ( dt.dayofyear / 365 ), 4)
        )
        df['day'] = ddates.apply(lambda dt: dt.day)
        df['month'] = ddates.apply(lambda dt: dt.month)
        df['year'] = ddates.apply(lambda dt: dt.year)
        df.sort_values(by=['countriesAndTerritories', 't'], ascending=True, inplace=True)
    except Exception as e:
        log.exception("Exception dapting dataframe from ECDC", e)
    log.info('df adapted')
    return df

def load_df(args):
    log.info('Loading')
    if not args.dont_use_cache and args.local_file:
        if os.path.isfile(args.local_file):
            df = load_csv(args.local_file)
        else:
            df = load_csv(args.url)
            df.to_csv(args.local_file, index=False)
    else:
        df = load_csv(args.url)
    return df

def main(args):
    df = load_df(args)
    
    df = adapt_df(df)
    df.to_csv(args.dest_file, index=False)
    #pyreadr.write_rds(str(args.dest_file), df)


if __name__ == "__main__":
    args = parse_args()
    main(args)