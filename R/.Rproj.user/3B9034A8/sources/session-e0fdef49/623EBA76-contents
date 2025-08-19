# code sourced from: https://cran.r-project.org/web/packages/LTRCtrees/vignettes/LTRCtrees.html
# for usage as reference

# imports
library(survival)
library(LTRCtrees)
library(rpart.plot)
library(partykit)

## Adjust data & clean data
set.seed(0)
## Since LTRCART uses cross-validation to prune the tree, specifying the seed 
## guarantees that the results given here will be duplicated in other analyses
Data <- flchain
Data <- Data[!is.na(Data$creatinine),]
Data$End <- Data$age + Data$futime/365
DATA <- Data[Data$End > Data$age,]
names(DATA)[6] <- "FLC"


## Setup training set and test set
Train = DATA[1:500,]
Test = DATA[1000:1020,]

## Fit LTRCART and LTRCIT survival tree
LTRCART.obj <- LTRCART(Surv(age, End, death) ~ sex + FLC + creatinine, Train)
LTRCIT.obj <- LTRCIT(Surv(age, End, death) ~ sex + FLC + creatinine, Train)

## Putting Surv(End, death) in formula would result an error message
## since both LTRCART and LTRCIT are expecting Surv(time1, time2, event)

## Plot the fitted LTRCART tree using rpart.plot function in rpart.plot[6] package
prp(LTRCART.obj, roundint=FALSE)

## Plot the fitted LTRCIT tree
plot(LTRCIT.obj)

LTRCART.obj.party <- as.party(LTRCART.obj) 
LTRCART.obj.party$fitted[["(response)"]]<- Surv(Train$age, Train$End, Train$death)
plot(LTRCART.obj.party)


## predict median survival time on test data using fitted LTRCIT tree
LTRCIT.pred <- predict(LTRCIT.obj, newdata=Test, type = "response")
head(LTRCIT.pred)

## predict Kaplan Meier survival curve on test data
## return a list of survfit objects -- the predicted KM curves
LTRCIT.pred <- predict(LTRCIT.obj, newdata=Test, type = "prob")
head(LTRCIT.pred,2)


## Predict relative risk on test set
LTRCART.pred <- predict(LTRCART.obj, newdata=Test)
head(LTRCART.pred)


## Predict median survival time and Kaplan Meier survival curve
## on test data using Pred.rpart
LTRCART.pred <- Pred.rpart(Surv(age, End, death) ~ sex + FLC + creatinine, Train, Test)
head(LTRCART.pred$KMcurves, 2)  ## list of predicted KM curves

head(LTRCART.pred$Medians)  ## vector of predicted median survival time

