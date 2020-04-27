import logging
import os
import random
from datetime import datetime
import pickle
import sys
import pandas as pd

"""
Handling of experiments
"""

def create_experiment(args):
    log = logging.getLogger('run-model')
    JOBID = os.environ.get("PBS_JOBID", str(random.randint(1,1000000)))
    log.info("Jobid = {}".format(JOBID))

    fullstr = "fullrun" if args.full else "debug"
    exp_dir = "{}-{}-{}-{}".format(
        args.stanmodel,
        fullstr,
        datetime.now().strftime("%Y%m%dT%H%M%S"),
        JOBID
    )
    if not args.nosubdir:
        for folder in ["results", "figures", "input", "output"]:
            os.makedirs(os.path.join("exp", exp_dir, folder))
        exp_dir = os.path.join("exp", exp_dir)
    return exp_dir


def save_input(args, stan_data, exp_dir):
    # save input data
    with open("model_input_Py.pkl", "wb") as fd:
        pickle.dump(stan_data, fd)
    if args.only_dump_input:
        log = logging.getLogger('run-model')

        log.warning("Stopping here because we set --only-dump-input")
        sys.exit(0)
    else:
        with open(os.path.join(exp_dir, "input", "model_input.pkl"), "wb") as fd:
            pickle.dump(stan_data, fd)

def save_output(args, exp_dir, output_dict, zones):
    for k, v in output_dict.items():
        with open(os.path.join(exp_dir, "results", "{}.pkl".format(k)), "wb") as fd:
            pickle.dump(v, fd)
    df = pd.DataFrame(zones)
    df.to_csv(os.path.join(exp_dir, "results", "zones.csv"), index=True)
    for k, v in output_dict.items():
        if hasattr(v, 'shape'):
            if len(v.shape) < 3:
                df = pd.DataFrame(v)
                df.to_csv(os.path.join(exp_dir, "results", "{}.csv".format(k)), index=False)
        elif isinstance(v, list):
                df = pd.DataFrame(v)
                df.to_csv(os.path.join(exp_dir, "results", "{}.csv".format(k)), index=False)
