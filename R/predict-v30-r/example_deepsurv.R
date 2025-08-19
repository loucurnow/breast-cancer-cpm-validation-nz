library(reticulate)
library(here)
library(survivalmodels)
library(survival)
library(survcomp) # for c-index

# get data from source
setwd("C:/Users/loucu/Coding_Projects/breast-cancer-cpm-validation")
source(here("./preprocess.R"))

# Point R to use your conda environment
use_condaenv("predict-breast-deepsurv", required = TRUE)

data.test <- as.data.frame(data.test)
data.train <- as.data.frame(data.train)

model.deepsurv <- deepsurv(
  formula =  Surv(survtime, censdead) ~ age + grade + er + pr + size + year, 
  data = data.train,
  num_nodes = c(32L, 32L),
  dropout = 0,
  early_stopping = TRUE,
  batch_size = 256,
  epochs = 50,
  verbose = TRUE,
  activation = "relu",
  )

risk_scores <- predict(model.deepsurv, newdata = data.test)

c_index_result <- concordance.index(
  x = risk_scores,
  surv.time = data.test$survtime,
  surv.event = data.test$censdead
)

c_index_result$c.index  # This is your concordance index
