library(xgboost)

library(here)
library(survival)

set.seed(1)

# get data from source
setwd("C:/Users/loucu/Coding_Projects/breast-cancer-cpm-validation")
source(here("../preprocess.R"))

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
pred <- predict(booster, data.test.predictors, type="risk")
pred 

pred_leaf <- predict(booster, data.test.predictors, predleaf = TRUE)
str(pred_leaf)

# Predicting feature contributions to predictions:
# the result is an nsamples X (nfeatures + 1) matrix
pred_contr <- predict(booster, data.test.predictors, predcontrib = TRUE)
str(pred_contr)

pred_margins <- predict(booster, data.test.predictors, output_margin = TRUE)
pred_margins

# verify that contributions' sums are equal to margin values
summary(rowSums(pred_contr) - pred_margins)


# for the 1st record, let's inspect its features that had non-zero contribution to prediction:
contr1 <- pred_contr[1,]
contr1 <- contr1[-length(contr1)]    # drop BIAS
contr1 <- contr1[contr1 != 0]        # drop non-contributing features
contr1 <- contr1[order(abs(contr1))] # order by contribution magnitude
old_mar <- par("mar")
par(mar = old_mar + c(0,7,0,0))
barplot(contr1, horiz = TRUE, las = 2, xlab = "contribution to prediction in log-odds")
par(mar = old_mar)
