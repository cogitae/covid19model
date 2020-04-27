import argparse
import os
import random
import sys
import numpy as np
from datetime import datetime  
from pathlib import Path

"""
Argument parser for run-model.py
"""


def max_date_arg(val):
    if val is None:
        return None
    return datetime.strptime(val, "%d/%m/%y")

def parse_args():
    parser = argparse.ArgumentParser("Launch Base STAN model for France")
    parser.add_argument("--debug", "-D", action="store_true",
        help="Perform a debug run of the model")
    parser.add_argument("--full", "-F", action="store_true",
	    help="Perform a full run of the model")
    parser.add_argument("--nosubdir", action="store_true",
	    help="Do not create subdirectories for generated data.")
    parser.add_argument("--maxdate", type=max_date_arg,
	    help="Consider only data up to max date 'dd/mm/yy' format.")
    parser.add_argument("--stanmodel", type=str, default="base",
	    help="Model to use.")

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

    parser.add_argument("--root-dir", type=Path,
        default=root_dir,
	    help="Root directory.")

    parser.add_argument("--input-files", type=Path, action="append",
        default=[
            Path(os.path.join(root_dir, "data","COVID-19-up-to-date_formated.csv")),
            Path(os.path.join(root_dir, "data","all-france_formated.csv")),
        ],
	    help="Input CSV files.")

    parser.add_argument("--covariates", type=str, action="append",
        default=[
            'Schools + Universities', 
            'Self-isolating if ill', 
            'Public events', 
            'Any', # placeholder and computed after
            'Lockdown', 
            'Social distancing encouraged'
        ],
	    help="Covariates to consider.")

    parser.add_argument("--N2", type=int, 
        default=120,
	    help="Number of days including forecast.")

    parser.add_argument("--death-thresh-epi-start", type=int, 
        default=10,
	    help="Number of deaths to consider as epidemic start date.")

    parser.add_argument("--death-days-before-thresh-epi-start", type=int, 
        default=30,
	    help="Number of days to consider before epidemic start date.")


    parser.add_argument("--chains", type=int, 
        default=4,
	    help="Number of chains for STAN fit method.")

    parser.add_argument("--njobs", type=int, 
        default=-1,
	    help="Number of jobs for STAN fit method.")

    parser.add_argument("--iter", type=int, 
        default=4000,
	    help="Number of iteration for STAN fit method.")

    parser.add_argument("--warmup", type=int, 
        default=2000,
	    help="Warmup for STAN fit method.")

    parser.add_argument("--seed", type=int, 
        default=random.randint(0, sys.maxsize),
	    help="Seed for STAN fit method.")

    parser.add_argument("--only-dump-input", action="store_true")
    

    return parser.parse_args()
