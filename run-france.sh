#!/bin/bash

# Contributors : Thomas Soumarmon thomas.soumarmon@cogitae.net

# if [ "$CONDA_DEFAULT_ENV" != "covid19model" ]; then
#     if [ "`conda env list | grep covid19model`" != "" ]; then
#         echo "activate conda env covid19model"
#         conda activate covid19model
#     else
#         echo "create conda env covid19model"
#         conda create -n covid19model python=3.6 pandas numpy pyyaml pandas scipy  pystan
#         conda activate covid19model
#         conda install -c conda-forge  pyreadr statsmodel
#     fi;
# else
#     echo "already in covid19model conda env"
# fi;

datadir="data/FRA"
opencovid_SRC_dir="https://raw.githubusercontent.com/opencovid19-fr/data/master/dist"
covinc_SRC_dir="https://raw.githubusercontent.com/scrouzet/covid19-incrementality/master/data"
ecdc_cov_file="https://opendata.ecdc.europa.eu/covid19/casedistribution/csv"

source_opencovid="${opencovid_SRC_dir}/chiffres-cles.csv"
source_INSEE_reg="${covinc_SRC_dir}/departements.csv"
source_INSEE_dep="${covinc_SRC_dir}/INSEE%20-%20year%20x%20dept%20x%20sex%20x%20age%20-%20population.csv"

# retrieve last version of files
echo "Download ${source_opencovid}"
wget -O ${datadir}/opencovid19-fr-chiffres-cles.csv ${source_opencovid}
echo "Download ${source_INSEE_reg}"
wget -O ${datadir}/population-fra-INSEE-region-departement.csv ${source_INSEE_reg}
echo "Download ${source_INSEE_dep}"
wget -O ${datadir}/population-fra-INSEE-departement.csv ${source_INSEE_dep}
echo "Download ${ecdc_cov_file}"
wget -O ${datadir}/COVID-19-up-to-date.csv ${ecdc_cov_file}


echo "RUN extract covid all-france"
python data/extract_opencovidfr_2_ICL.py ${datadir}/opencovid19-fr-chiffres-cles.csv all-france
echo "RUN extract covid REG"
python data/extract_opencovidfr_2_ICL.py ${datadir}/opencovid19-fr-chiffres-cles.csv REG
echo "RUN extract covid DEP"
python data/extract_opencovidfr_2_ICL.py ${datadir}/opencovid19-fr-chiffres-cles.csv DEP

# Update data
# Update Europe wide data from ECDC and process to RDS
echo "RUN data/fetch-ecdc.py"
# force update ...
rm "data/COVID-19-up-to-date.csv"
python Python/src/fetch-ecdc.py \
    --local-file "data/COVID-19-up-to-date.csv" \
    --dest-file "data/COVID-19-up-to-date_formated.csv"

python Python/src/fetch-ecdc.py \
    --local-file "data/all-france.csv" \
    --dest-file "data/all-france_formated.csv"

echo "RUN Python/src/run-model.py"
python Python/src/run-model.py --stanmodel base --full 
#> results/stdout.txt 2> results/stderr.txt 
#python Python/src/run-model.py --stanmodel base --full --only-dump-input 
