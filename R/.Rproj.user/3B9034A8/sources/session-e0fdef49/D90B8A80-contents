source("C:/Users/loucu/Coding_Projects/breast-cancer-cpm-validation/R/predict-v30-r/inst/defpackage.R")
library(haven)
library(condSURV)
library(lubridate)
library(here)


library(predictv30r)

data(gbcsCS)
data<- gbcsCS
data$er = ifelse(gbcsCS$estrg_recp >= 10, 1, 0)
data$pr = ifelse(gbcsCS$prog_recp >= 10, 1, 0)
data$year <- as.numeric(format(as.Date(data$diagdateb, format="%d-%m-%Y"),"%Y"))
data$age <- as.numeric(testdata$age) # treat age as continuous var in modelling

# missing data:
# her2       <- 1     # HER2+ = 1, HER2- = 0, missing = 9
# ki67       <- 0     # KI67+ = 1, KI67- = 0, missing = 9
data$her2 <- 9
data$ki67 <- 9


## --- treatment
# radio      <- 1     # Radiotherapy Yes = 1, no = 0
# horm       <- 1     # Hormone therapy Yes = 1, no = 0
# generation <- 3     # Chemo generation 0, 2 or 3 only
# traz       <- 1     # Trastuzumab therapy Yes = 1, no = 0
# bis        <- 1     # Bisphosphonate therapy Yes = 1, no = 0
# heart.gy   <- 4     # No grays radiotherapy to heart

## --- lifestyle
# smoker     <- 1     # Never/ex = 0, current = 1


# include only columns we will use as predictors
data = subset(testdata, select = c(censdead, survtime, age, menopause, size, grade, nodes, er, pr, year)) %>%
  na.omit()


#use 70% of dataset as training set and 30% as test set
sample <- sample(c(TRUE, FALSE), nrow(data), replace=TRUE, prob=c(0.7,0.3))
data.train  <- as.matrix(data[sample, ])
data.test   <- as.matrix(data[!sample, ])

# save to RDS file
save(data.train, file="../traindata.RDS")
save(data.test, file="../testdata.RDS")