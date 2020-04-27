import pandas as pd
#import os
from .experiment import save_output
import logging


def postprocess(args, exp_dir, output_dict, zones):
    log = logging.getLogger('run-model')
    log.info("saving in {} ouput {}".format(exp_dir, output_dict.keys()))
    save_output(args, exp_dir, output_dict, zones)
