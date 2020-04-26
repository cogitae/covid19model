
import pickle

def save_data(obj, filename):
    with open(filename, "wb") as fd:
        pickle.dump(obj, fd)