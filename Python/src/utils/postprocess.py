import pandas as pd
#import os
from .experiment import save_output

def postprocess(args, exp_dir, output_dict):
    print("saving ouput {}".format(output_dict.keys()))
    save_output(args, exp_dir, output_dict)
