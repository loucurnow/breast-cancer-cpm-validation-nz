library(xgboost)
library(prodlim)
library(here)
library(survival)
library(pec)
library(survminer)
library(rms)
library(ROCR)
set.seed(1)

# get data from source
setwd("C:/Users/loucu/Coding_Projects/breast-cancer-cpm-validation")
source(here("preprocess.R"))

# remove vars which we won't use
data = subset(testdata, select = -c(diagdateb, deathdate, recdate, prog_recp, estrg_recp, rectime, censrec, hormone))

nthread = 1

xgb.params <- list(
  booster = "gbtree",
  eta = 0.1,
  max_depth = 4,
  gamma = 0.1,
  subsample = 0.75,
  colsample_bytree = 0.8,
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
cv <- xgb.cv(
  params = xgb.params,
  data = dmatrix_train,
  nrounds = 500,
  nfold = 5,
  early_stopping_rounds = 10,
  verbose = 1,
  showsd = TRUE,
  print_every_n = 10
)
best_nrounds <- cv$best_iteration

booster <- xgb.train(
  data = dmatrix_train,
  nrounds = best_nrounds,
  params = xgb.params
)

# testing
data.test.predictors = subset(data.test, select = c(age, menopause, size, grade, nodes, er, pr, year))
data.test.label = as.numeric(data.test[,"survtime"])
dmatrix_test <- xgb.DMatrix(data.test.predictors, label=data.test.label, nthread = nthread)

# predicting
xgb.importance(model=booster)

booster

# prediction output is the hazard ratio
pred <- predict(booster, data.test.predictors)
str(pred)

pred_leaf <- predict(booster, data.test.predictors, predleaf = TRUE)
str(pred_leaf)

# Predicting feature contributions to predictions:
# the result is an nsamples X (nfeatures + 1) matrix
pred_contr <- predict(booster, data.test.predictors, predcontrib = TRUE)
str(pred_contr)

# accuracy measures - bootstrap samples
set.seed(123)
n_boot <- 1000
n <- nrow(data.test)

# Create empty matrix
cindex_mat <- matrix(NA, nrow = n_boot, ncol = 2)
models <- c("Clinical_Cox", "XGB_Cox")
colnames(cindex_mat) <- models

for (i in 1:n_boot) {
  idx <- sample(1:n, replace = TRUE)
  data.boot <- data.frame(data.test[idx, ])
  
  data.boot$pred_boot <- predict(booster, as.matrix(data.boot[, c("age", "menopause", "size", "grade", "nodes", "er", "pr", "year")]))
  
  model_boot_cox        <- coxph(Surv(survtime, censdead) ~ age + grade + er + pr + size + year, data = data.boot, x=TRUE, y=TRUE)
  model_boot_xgb_cox      <- coxph(Surv(survtime, censdead) ~ pred_boot, data = data.boot, x=TRUE, y=TRUE, robust=TRUE)

  cindex_mat[i, 1] <- concordance(model_boot_cox)$concordance
  cindex_mat[i, 2] <- concordance(model_boot_xgb_cox)$concordance

}

head(cindex_mat)

mean_cindex = apply(cindex_mat, 2, mean)
cindex_CI = apply(cindex_mat, 2, function(x) quantile(x, probs = c(0.025, 0.975)))

cindex_CI

# new plotting window
par(mfrow = c(2, 2))
for (i in 1:5) {
  hist(cindex_mat[, i], breaks = 30, main = models[i], xlab = "C-index")
  abline(v = mean_cindex[i], col = "red", lwd = 2)
}

# brier score
# Step 1: Fit Kaplan-Meier to get baseline
fit.km <- survfit(surv.obj ~ 1)
ggsurvplot(fit.km, data=data.frame(data.test))
# Step 2: Interpolate baseline survival at required times
times <- seq(365, 365*5, by = 365)

# baseline survival probabilities 
S0_t <- summary(fit.km, times = times)$surv 

# survival probabilities
S_pred <- outer(pred, S0_t, FUN = function(hr, s0) s0^hr)

test_data <- data.frame(data.test)
test_data$pred = pred

# brier score calc
brier <- pec(
  object = list("coxph" = model.cox,
                "xgcoxph" = model.xg.cox),    # <- Matrix
  formula = Surv(survtime, censdead) ~ 1,
  data = test_data,  # <- Match formula
  times = times,
  cens.model = "cox",
  splitMethod = "Boot632",
  B = 1000
)

plot(brier)


summary(model.xg.cox)

ggsurvplot(sf, data.test)
plot(sf, col = rainbow(10), main = "Survival curves for test set")

# Survival curves for all individuals
sf_all <- survfit(model.xg.cox, newdata = data.frame(pred = pred))
ggsurvplot(sf_all, data=data.test)
plot(sf_all, col = rainbow(10), main = "Survival curves for test set")

# for the 1st record, let's inspect its features that had non-zero contribution to prediction:
contr1 <- pred_contr[1,]
contr1 <- contr1[-length(contr1)]    # drop BIAS
contr1 <- contr1[contr1 != 0]        # drop non-contributing features
contr1 <- contr1[order(abs(contr1))] # order by contribution magnitude
old_mar <- par("mar")
par(mar = old_mar + c(0,7,0,0))
barplot(contr1, horiz = TRUE, las = 2, xlab = "contribution to prediction in log-odds")
par(mar = old_mar)
