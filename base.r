library(rstan)
library(data.table)
library(lubridate)
library(gdata)
library(dplyr)
library(tidyr)
library(EnvStats)

# provide functions for pre and post processing
source("utils/arg-parser.r")
source("utils/read-covariates.r")


countries <- c(
  "Denmark",
  "Italy",
  "Germany",
  "Spain",
  "United_Kingdom",
  "France",
  "Norway",
  "Belgium",
  "Austria", 
  "Sweden",
  "Switzerland",
  "Greece",
  "Portugal",
  "Netherlands"
)

# Commandline options and parsing
parsedargs <- base_arg_parse()
DEBUG <- parsedargs[["DEBUG"]]
FULL_RUN <- parsedargs[["FULL"]]
StanModel <- parsedargs[["StanModel"]]

## Reading all data
d=readRDS('data/COVID-19-up-to-date.rds')

## Ensure that output directories exist
dir.create("results/", showWarnings = FALSE, recursive = TRUE)
dir.create("figures/", showWarnings = FALSE, recursive = TRUE)
dir.create("web/", showWarnings = FALSE, recursive = TRUE)

## get IFR and population from same file
ifr.by.country = read.csv("data/popt_ifr.csv")
ifr.by.country$country = as.character(ifr.by.country[,2])
ifr.by.country$country[ifr.by.country$country == "United Kingdom"] = "United_Kingdom"

serial.interval = read.csv("data/serial_interval.csv")

covariates <- covariates_read('data/interventions.csv')

forecast = 0
N2 = 120 # increase if you need more forecast

dates = list()
reported_cases = list()
# Pads serial interval with 0 if N2 is greater than the length of the serial
# interval array
if (N2 > length(serial.interval$fit)) {
  pad_serial.interval <- data.frame(
    "X"=(length(serial.interval$fit)+1):N2,
    "fit"=rep(0.0, max(N2-length(serial.interval$fit), 0 ))
  )
  serial.interval = rbind(serial.interval, pad_serial.interval)
}
stan_data = list(M=length(countries),N=NULL,covariate1=NULL,covariate2=NULL,covariate3=NULL,covariate4=NULL,covariate5=NULL,covariate6=NULL,deaths=NULL,f=NULL,
                 N0=6,cases=NULL,SI=serial.interval$fit[1:N2],
                 EpidemicStart = NULL, pop = NULL) # N0 = 6 to make it consistent with Rayleigh
deaths_by_country = list()

# various distributions required for modeling
mean1 = 5.1; cv1 = 0.86; # infection to onset
mean2 = 18.8; cv2 = 0.45 # onset to death
x1 = rgammaAlt(1e7,mean1,cv1) # infection-to-onset distribution
x2 = rgammaAlt(1e7,mean2,cv2) # onset-to-death distribution

ecdf.saved = ecdf(x1+x2)

for(Country in countries) {
  IFR=ifr.by.country$ifr[ifr.by.country$country == Country]
  
  covariates1 <- covariates[covariates$Country == Country, c(2,3,4,5,6)]
  
  d1_pop = ifr.by.country[ifr.by.country$country==Country,]
  d1=d[d$Countries.and.territories==Country,c(1,5,6,7)]
  d1$date = as.Date(d1$DateRep,format='%d/%m/%Y')
  d1$t = decimal_date(d1$date) 
  d1=d1[order(d1$t),]
  
  date_min <- dmy('31/12/2019') 
  if (as.Date(d1$DateRep[1], format='%d/%m/%Y') > as.Date(date_min, format='%d/%m/%Y')){
    print(paste(Country,'In padding'))
    pad_days <- as.Date(d1$DateRep[1], format='%d/%m/%Y') - date_min
    pad_dates <- date_min + days(1:pad_days[[1]]-1)
    padded_data <- data.frame("Countries.and.territories" = rep(Country, pad_days),
                              "DateRep" = format(pad_dates, '%d/%m/%Y'),
                              "t" = decimal_date(as.Date(pad_dates,format='%d/%m/%Y')),
                              "date" = as.Date(pad_dates,format='%d/%m/%Y'),
                              "Cases" = as.integer(rep(0, pad_days)),
                              "Deaths" = as.integer(rep(0, pad_days)),
                              stringsAsFactors=F)
    
    d1 <- bind_rows(padded_data, d1)
  }
  index = which(d1$Cases>0)[1]
  index1 = which(cumsum(d1$Deaths)>=10)[1] # also 5
  index2 = index1-30
 
  print(sprintf("First non-zero cases is on day %d, and 30 days before 10 deaths is day %d",index,index2))
  d1=d1[index2:nrow(d1),]
  stan_data$EpidemicStart = c(stan_data$EpidemicStart,index1+1-index2)
  stan_data$pop = c(stan_data$pop, d1_pop$popt)
  
  
  for (ii in 1:ncol(covariates1)) {
    covariate = names(covariates1)[ii]
    d1[covariate] <- (as.Date(d1$DateRep, format='%d/%m/%Y') >= as.Date(covariates1[1,covariate]))*1  # should this be > or >=?
  }
  
  dates[[Country]] = d1$date
  # hazard estimation
  N = length(d1$Cases)
  print(sprintf("%s has %d days of data",Country,N))
  forecast = N2 - N
  if(forecast < 0) {
    print(sprintf("%s: %d", Country, N))
    print("ERROR!!!! increasing N2 to have at least 7 days")
    N2 = N
    forecast = N2 - N
  }
  
  # IFR is the overall probability of dying given infection
  convolution = function(u) (IFR * ecdf.saved(u))

  f = rep(0,N2) # f is the probability of dying on day i given infection
  f[1] = (convolution(1.5) - convolution(0))
  for(i in 2:N2) {
    f[i] = (convolution(i+.5) - convolution(i-.5)) 
  }
  
  reported_cases[[Country]] = as.vector(as.numeric(d1$Cases))
  deaths=c(as.vector(as.numeric(d1$Deaths)),rep(-1,forecast))
  cases=c(as.vector(as.numeric(d1$Cases)),rep(-1,forecast))
  deaths_by_country[[Country]] = as.vector(as.numeric(d1$Deaths))
  covariates2 <- as.data.frame(d1[, colnames(covariates1)])
  # x=1:(N+forecast)
  covariates2[N:(N+forecast),] <- covariates2[N,]
  
  ## append data
  stan_data$N = c(stan_data$N,N)
  # stan_data$x = cbind(stan_data$x,x)
  stan_data$covariate1 = cbind(stan_data$covariate1,covariates2[,1])
  stan_data$covariate2 = cbind(stan_data$covariate2,covariates2[,2])
  stan_data$covariate3 = cbind(stan_data$covariate3,covariates2[,3])
  stan_data$covariate4 = cbind(stan_data$covariate4,covariates2[,4])
  stan_data$covariate5 = cbind(stan_data$covariate5,covariates2[,4])
  stan_data$covariate6 = cbind(stan_data$covariate6,covariates2[,5])
  stan_data$f = cbind(stan_data$f,f)
  stan_data$deaths = cbind(stan_data$deaths,deaths)
  stan_data$cases = cbind(stan_data$cases,cases)
  
  stan_data$N2=N2
  stan_data$x=1:N2
  if(length(stan_data$N) == 1) {
    stan_data$N = as.array(stan_data$N)
  }
}

# create the `any intervention` covariate
stan_data$covariate4 = 1*as.data.frame((stan_data$covariate1+
                                          stan_data$covariate2+
                                          stan_data$covariate3+
                                          stan_data$covariate5+
                                          stan_data$covariate6) >= 1)

if(DEBUG) {
  for(i in 1:length(countries)) {
    write.csv(
      data.frame(date=dates[[i]],
                 `school closure`=stan_data$covariate1[1:stan_data$N[i],i],
                 `self isolating if ill`=stan_data$covariate2[1:stan_data$N[i],i],
                 `public events`=stan_data$covariate3[1:stan_data$N[i],i],
                 `government makes any intervention`=stan_data$covariate4[1:stan_data$N[i],i],
                 `lockdown`=stan_data$covariate5[1:stan_data$N[i],i],
                 `social distancing encouraged`=stan_data$covariate6[1:stan_data$N[i],i]),
      file=sprintf("results/%s-check-dates.csv",countries[i]),row.names=F)
  }
}

options(mc.cores = parallel::detectCores())
rstan_options(auto_write = TRUE)
m = stan_model(paste0('stan-models/',StanModel,'.stan'))


if(DEBUG) {
  fit = sampling(m,data=stan_data,iter=40,warmup=20,chains=2)
} else if (FULL_RUN) {
  fit = sampling(m,data=stan_data,iter=4000,warmup=2000,chains=4,thin=4,control = list(adapt_delta = 0.95, max_treedepth = 10))
} else { 
  fit = sampling(m,data=stan_data,iter=200,warmup=100,chains=4,thin=4,control = list(adapt_delta = 0.95, max_treedepth = 10))
}

JOBID = Sys.getenv("PBS_JOBID")
if(JOBID == "")
  JOBID = as.character(abs(round(rnorm(1) * 1000000)))
print(sprintf("Jobid = %s",JOBID))

save.image(paste0('results/',StanModel,'-',JOBID,'.Rdata'))

save(fit, dates, reported_cases, deaths_by_country, countries, covariates,
     stan_data,
     file = paste0('results/',StanModel,'-',JOBID,'-stanfit.Rdata'))

filename <- paste0(StanModel,'-',JOBID)
system(paste0("Rscript covariate-size-effects.r ", filename,'-stanfit.Rdata'))
out = rstan::extract(fit)
mu = (as.matrix(out$mu))
colnames(mu) = countries
g = bayesplot::mcmc_intervals(mu,prob = .9)
ggplot2::ggsave(sprintf("results/%s-mu.png",filename),g,width=4,height=6)
tmp = lapply(1:length(countries), function(i) (out$Rt_adj[,stan_data$N[i],i]))
Rt_adj = do.call(cbind,tmp)
colnames(Rt_adj) = countries
g = bayesplot::mcmc_intervals(Rt_adj,prob = .9)
ggsave(sprintf("results/%s-final-rt.png",filename),g,width=4,height=6)
system(paste0("Rscript plot-3-panel.r ", filename,'-stanfit.Rdata'))
system(paste0("Rscript plot-forecast.r ",filename,'-stanfit.Rdata'))
system(paste0("Rscript make-table.r results/",filename,'-stanfit.Rdata'))

