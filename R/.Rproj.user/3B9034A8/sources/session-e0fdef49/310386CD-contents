library(xgboost)
library(prodlim)
library(here)
library(survival)
library(pec)
library(survminer)

set.seed(1)

# get data from source
setwd("C:/Users/loucu/Coding_Projects/breast-cancer-cpm-validation")
source(here("preprocess.R"))

# remove vars which we won't use
data = subset(testdata, select = -c(diagdateb, deathdate, recdate, prog_recp, estrg_recp, rectime, censrec, hormone))

nthread = 1

xgb.params <- list(
  booster = "gbtree",
  eta = 0.5,
  max_depth = 6,
  gamma = 0.2,
  subsample = 0.75,
  objective = "survival:cox",
  nthread = nthread,
  eval_metric = "cox-nloglik"
)

#use 70% of dataset as training set and 30% as test set
sample <- sample(c(TRUE, FALSE), nrow(data), replace=TRUE, prob=c(0.7,0.3))
data.train  <- as.matrix(data[sample, ])
data.test   <- as.matrix(data[!sample, ])

data.train.predictors = subset(data.train, select = c(age, menopause, size, grade, nodes, er, pr, year))
data.train.label = as.numeric(data.train[,"survtime"])

dmatrix_train <- xgb.DMatrix(data.train.predictors, label=data.train.label, nthread = 1)

# create model from training data
booster <- xgb.train(
  data = dmatrix_train,
  nrounds = 10,
  params = xgb.params
)

# testing
data.test.predictors = subset(data.test, select = c(age, menopause, size, grade, nodes, er, pr, year))
data.test.label = as.numeric(data.test[,"survtime"])
dmatrix_test <- xgb.DMatrix(data.test.predictors, label=data.test.label, nthread = nthread)

# predicting
xgb.importance(model=booster)

booster

# prediction output is the hazard ratio, but to validate we need survival time estimate?
pred <- predict(booster, data.test.predictors)
pred 

pred_leaf <- predict(booster, data.test.predictors, predleaf = TRUE)
str(pred_leaf)

# Predicting feature contributions to predictions:
# the result is an nsamples X (nfeatures + 1) matrix
pred_contr <- predict(booster, data.test.predictors, predcontrib = TRUE)
str(pred_contr)
  
# use prediction as a covariate in a Cox model
surv.obj <- Surv(data.test.label, data.test[, "censdead"])
model.cox <- coxph(surv.obj ~ pred)
summary(model.cox)

sf <- survfit(model.cox, newdata = data.test)
ggsurvplot(sf, data.test)
plot(sf, col = rainbow(10), main = "Survival curves for test set")

# Survival curves for all individuals
sf_all <- survfit(model.cox, newdata = data.frame(pred = pred))
plot(sf_all, col = rainbow(10), main = "Survival curves for test set")

# c index
c_index <- concordance(model.cox)$concordance
c_index

# brier score

# Estimate Brier score using .632 bootstrap
brier <- pec(
  object = list(xgboost = model.cox),
  formula = surv.obj ~ .,
  data = data.frame(surv.obj, pred),
  times = seq(365, 365*15, by = 365), # e.g. yearly for 15 years
  cens.model = "cox",
  splitMethod = "Boot632",
  B = 100
)
brier <- pec(
  object = list("XGBoost Cox" = model.cox),
  formula = surv.obj ~ 1,
  data = data.frame(surv.obj, pred),
  times = seq(12, 60, by = 6),
  cens.model = "cox",
  splitMethod = "Boot632", # or "cv", or "none"
  B = 100
)
plot(brier)



# for the 1st record, let's inspect its features that had non-zero contribution to prediction:
contr1 <- pred_contr[1,]
contr1 <- contr1[-length(contr1)]    # drop BIAS
contr1 <- contr1[contr1 != 0]        # drop non-contributing features
contr1 <- contr1[order(abs(contr1))] # order by contribution magnitude
old_mar <- par("mar")
par(mar = old_mar + c(0,7,0,0))
barplot(contr1, horiz = TRUE, las = 2, xlab = "contribution to prediction in log-odds")
par(mar = old_mar)
