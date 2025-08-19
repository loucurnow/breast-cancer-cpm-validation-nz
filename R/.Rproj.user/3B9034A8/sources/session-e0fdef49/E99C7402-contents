setwd("C:/Users/loucu/Coding_Projects/breast-cancer-cpm-validation")
library(here)
library(survminer)
library(survival)
library(rms)
library(mfp)
source(here("../preprocess.R"))
 
#PREDICT3::benefits31()


# null model
cox.model.null <- coxph(Surv(survtime, censdead) ~ 1, data = testdata)
summary(cox.model.null)
ggsurvplot(survfit(cox.model.null), data = testdata)

# testing proportional hazards assumption
test.ph = cox.zph(cox.model.null) 
# not statistically significant results -> valid assumptions
ggcoxzph(test.ph) # plot 

# testing overly influ8ential observations
# dfbeta: estimated changes in regression coefficients upon deleting each observation
# dfbetas: dfbeta but divide by coef standard errors
ggcoxdiagnostics(cox.model.null, type = "dfbetas", linear.predictions = TRUE)

# deviance residuals
ggcoxdiagnostics(cox.model.null, type = "deviance",
                 linear.predictions = FALSE, ggtheme = theme_bw())


# exploratory - survival plotting
# by grade
surv.model = survfit(Surv(survtime, censdead)~grade, data=testdata)
summary(surv.model)
ggsurvplot(surv.model)

surv.model = survfit(Surv(survtime, censdead)~er+pr, data=testdata)
summary(surv.model)
ggsurvplot(surv.model)

# model with same coefs as PREDICT 3 (when available)
cox.model <- coxph(Surv(survtime, censdead)~age+grade+er+pr+size, data=testdata)
summary(cox.model)
ggsurvplot(survfit(cox.model), data=testdata)

# testing non linearity
ggcoxfunctional(cox.model, data=testdata) # age is not linear!


# PREDICT uses age-24 as base, and fractional polynomial 
testdata$age <- testdata$age + 24
## ------------------------------------------------------------------------
testdata$age.mfp.1   <- ifelse(testdata$er==1, ((testdata$age/100)^-0.5), (testdata$age/100))
testdata$age.mfp.2   <- ifelse(testdata$er==1, ((testdata$age/100)^2), (testdata$age/100) * log(testdata$age/100))

cox.mfp <- mfp(Surv(survtime, censdead)~strata(er)+fp(age)+grade+pr+size, family=cox, data=testdata)
summary(cox.mfp)

cox.mfp$fptable # details of FP transformations 
cox.mfp.fit <- coxph(cox.mfp$formula, data=testdata)

# testing non linearity
ggcoxfunctional(cox.mfp.fit) 
ggcoxdiagnostics(cox.mfp$fit, type = "martingale",
                 linear.predictions = FALSE, ggtheme = theme_bw())


