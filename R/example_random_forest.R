library(here)
library(survminer)
library(survival)
library(randomForestSRC)

# get data from source
setwd("C:/Users/loucu/Coding_Projects/breast-cancer-cpm-validation")
source(here("preprocess.R"))


# set up a random forest, all vars
rf.model.all <- rfsrc(Surv(survtime, censdead) ~ ., data = data)
print(rf.model.all)
oo <- subsample(rf.model.all, verbose = FALSE)

# take a delete-d-jackknife procedure for vimp
vimpCI <- extract.subsample(oo)$var.jk.sel.Z
vimpCI

# Confidence Intervals for VIMP
plot.subsample(oo)
# nodes partial plot
plot.variable(rf.model.all, xvar.names = "nodes", partial = TRUE)
# pr partial plot
plot.variable(rf.model.all, xvar.names = "pr", partial = TRUE)
# er partial plot
plot.variable(rf.model.all, xvar.names = "er", partial = TRUE)
# age partial plot
plot.variable(rf.model.all, xvar.names = "age", partial = TRUE)
# size partial plot
plot.variable(rf.model.all, xvar.names = "size", partial = TRUE)

plot.variable(rf.model.all, partial=T)


get.cindex(time = data$survtime, censoring = data$censdead, predicted = rf.model.all$predicted.oob)

