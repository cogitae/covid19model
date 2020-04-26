import numpy as np
from numpy.random import gamma 
from statsmodels.distributions.empirical_distribution import ECDF

def get_gamma(mean, cv, size=int(5e6)):
    loc = 1 / cv ** 2
    scale = mean * cv ** 2
    return gamma(shape=loc, scale=scale, size=size)

def poly(x, p):
    """
    Thanks to https://stackoverflow.com/questions/41317127/python-equivalent-to-r-poly-function
    """
    x = np.array(x)
    X = np.transpose(np.vstack(list(x**k for k in range(p+1))))
    return np.linalg.qr(X)[0][:,1:]

# probability distribution of the infection-to-death distribution \pi_m in the paper
def convolution(u, ifr, gamma_cdf):
    return ifr * gamma_cdf(u)
