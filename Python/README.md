
# Python vesion of the Impercial Colleger model launcher

Work In Progress : 
* outputs have not been verifyed yet
* outputs are just dumped into exp/.../results as pkl and csv, no further processing


## Easy install

### Requirement
You need to have anaconda installed before

### Create anaconda env

`conda env create -f environment-python.yml`

### activate anaconda env

`conda activate covid19modelpython`

### launch the main script

This script downloads the data, preprocess it and run the `base` model.

`run-france.sh`

### launch again the model or the dynamic version of the model

You can launch the base model with in a environment having python

`python Python/src/run-model.py --full`   

or a dynamic version (covariates not limited to 6 by the model ) with 

`python Python/src/run-model.py --full --stanmodel dynamic`   

