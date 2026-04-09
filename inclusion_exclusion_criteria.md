---
title: "Inclusion/Exclusion Criteria"
format: html
editor: visual
---

## Inclusion/Exclusion Criteria

## Review of Strategy

The table below presents some inclusion and exclusion criteria and the proposed plan for each.

+---------------------+-------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Inclusion/Exclusion | Criteria                      | Proposed Method                                                                                                                                                                     |
+=====================+===============================+=====================================================================================================================================================================================+
| Inclusion           | Female                        | filter gender == female                                                                                                                                                             |
+---------------------+-------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|                     | Index Cancer                  | cancer events defined by PatientNo+tissue_dx_date, arranged in descending sequence, and row number                                                                                  |
|                     |                               |                                                                                                                                                                                     |
|                     |                               | filter diagnosis_number == 1                                                                                                                                                        |
|                     |                               |                                                                                                                                                                                     |
|                     |                               | done in e                                                                                                                                                                           |
+---------------------+-------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|                     | Age                           | 20-85 years old (per Wishart 2011)                                                                                                                                                  |
|                     |                               |                                                                                                                                                                                     |
|                     |                               | for now leave in and can create age-defined sets later                                                                                                                              |
+---------------------+-------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|                     | Follow-Up of at Least 5 Years | Requested data with enrollment up to Dec 2017 with survival follow-up untill Dec 2022 (survival follow-up was \~ Aug 2023)                                                          |



+---------------------+-------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Exclusion           | Multiple lesions              | will flag as more than 1 lesion, but leave in for subsequent analysis. This is for sensitivity to clinical practice of pick the largest lesion.                                     |
+---------------------+-------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|                     | Neoadjuvant Therapy           | Will use neo_rad, neo_mab, neo_hormone, and neo_chemo flags from Demographics                                                                                                       |
|                     |                               |                                                                                                                                                                                     |
|                     |                               | Attempt made to define relative to surgical date, but would drop the \~5000 missing surgical date information                                                                       |
|                     |                               |                                                                                                                                                                                     |
|                     |                               | done in this section in exclusion_df_4                                                                                                                                              |
+---------------------+-------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|                     | Incomplete Local Therapy      | see Locoregional_completion - has flag to indicate relative completion                                                                                                              |
+---------------------+-------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|                     | Metastatic at baseline        | Exclude those with a 1st metastasis before tissue_dx_date.                                                                                                                          |
|                     |                               |                                                                                                                                                                                     |
|                     |                               | Create flag for windows of 30, 60, and 120 days post tissue_dx_date - this is because if metastatic within 1 month, likely metastatic at outset - test exclusion sensitivity later. |
|                     |                               |                                                                                                                                                                                     |
|                     |                               | done in this section in exclusion_df_4                                                                                                                                              |
+---------------------+-------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|                     | DCIS                          | removed T_stage DCIS or DCIS NA                                                                                                                                                     |
|                     |                               |                                                                                                                                                                                     |
|                     |                               | done in merged_breast_table_no_DCIS                                                                                                                                                 |
+---------------------+-------------------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

## Excluding Metastatic at baseline cases

```{r}
load("~/Library/CloudStorage/OneDrive-Personal/Documents/PhD_Stuff/PREDICT_BREAST_NZ_calibration/BCF_data/tidy_Aug_23_Data/exclusion_df_3_1.Rda")

exclusion_df_3_2<-exclusion_df_3_1 |>
  mutate(tissue_to_first_met = difftime(met_date_1, tissue_dx_date, units="days"))|>
  mutate(met_at_dx = case_when(
    tissue_to_first_met <= 0 & MetsId_1 != 99999 ~ "YES",
    TRUE~"NO"
  ))|>
  mutate(met_at_30_days = case_when(
    tissue_to_first_met <= 30 & MetsId_1 != 99999~ "YES",
    TRUE~"NO"
  ))|>
  mutate(met_at_60_days = case_when(
    tissue_to_first_met <= 60 & MetsId_1 != 99999~ "YES",
    TRUE~"NO"
  ))|>
  mutate(met_at_120_days = case_when(
    tissue_to_first_met <= 120 & MetsId_1 != 99999~ "YES",
    TRUE~"NO"
  ))

exclusion_df_3_3 <-exclusion_df_3_2 |>
  select(!c(MetsId_1:met_date_14, tissue_to_first_met))

save(exclusion_df_3_3, file="/Users/rms/Library/CloudStorage/OneDrive-Personal/Documents/PhD_Stuff/PREDICT_BREAST_NZ_calibration/BCF_data/tidy_Aug_23_Data/exclusion_df_3_3.Rda")  
```

Look at the varying thresholds to call met at diagnosis

Within 30 days of tissue dx - I would argue this is almost understaging rather than non-metastatic disease at outside, but leave all the flags in to look at sensitivity.

```{r}
exclusion_df_3_3|>
  group_by(met_at_30_days)|>
  tally()
```

Within 60 days of tissue dx

```{r}
exclusion_df_3_3|>
  group_by(met_at_60_days)|>
  tally()
```

Within 120 days of tissue dx

```{r}
exclusion_df_3_3|>
  group_by(met_at_120_days)|>
  tally()
```

## Neo-adjuvant Therapies

This will rely on the neo-adjuvant flag. An attempt was made based on surgical dates, but enough were missing it wasn't tenable to try to calculate neo-adjuvant with any fidelity across the dataset, without needing to drop a large percent of cases without surgical data.

```{r}
load("~/Library/CloudStorage/OneDrive-Personal/Documents/PhD_Stuff/PREDICT_BREAST_NZ_calibration/BCF_data/tidy_Aug_23_Data/exclusion_df_3_3.Rda")

#consolidating neo-adjuvant
exclusion_df_3_4<-exclusion_df_3_3 |>
  mutate(neo_given=case_when(
    neo_rad %in% c("n/a - treatment for metastatic disease", "Not referred - deemed not necessary", "Not referred - patient declined", "Not referred - patient unfit", "Other (specify)", "Referred - deemed not necessary", "Referred - patient declined", "Referred - patient unfit") ~ "NO",
    neo_rad == "Unknown" ~ NA, 
    neo_rad == "Yes" ~ "YES",
    neo_chemo %in% c("n/a - treatment for metastatic disease", "Not referred - deemed not necessary", "Not referred - patient declined", "Not referred - patient unfit", "Other (specify)", "Referred - deemed not necessary", "Referred - patient declined", "Referred - patient unfit") ~ "NO",
    neo_chemo == "Unknown" ~ NA, 
    neo_chemo == "Yes" ~ "YES", 
    neo_mab %in% c("n/a - treatment for metastatic disease", "Not referred - deemed not necessary", "Not referred - patient declined", "Not referred - patient unfit", "Other (specify)", "Referred - deemed not necessary", "Referred - patient declined", "Referred - patient unfit") ~ "NO",
    neo_mab == "Unknown" ~ NA, 
    neo_mab == "Yes" ~ "YES", 
    neo_hormone %in% c("n/a - treatment for metastatic disease", "Not referred - deemed not necessary", "Not referred - patient declined", "Not referred - patient unfit", "Other (specify)", "Referred - deemed not necessary", "Referred - patient declined", "Referred - patient unfit") ~ "NO",
    neo_hormone == "Unknown" ~ NA, 
    neo_hormone == "Yes" ~ "YES", 
    TRUE ~ "PPPP"
  ))|>
  relocate(neo_given, .before = neo_rad)

exclusion_df_3_4|>
 group_by(neo_given)|>
  tally()

save(exclusion_df_3_4, file="/Users/rms/Library/CloudStorage/OneDrive-Personal/Documents/PhD_Stuff/PREDICT_BREAST_NZ_calibration/BCF_data/tidy_Aug_23_Data/exclusion_df_3_4.Rda")  
```

This identifies a small number of patients that received their first adjuvant hormone, chemotherapy, or monoclonal after a diagnosis of metastasis. I will create a flag to indicate these cases.

## Metastatic Status - Based on Neo- and Adj- Therapy Flagging

It's notable that the various adjuvant therapy flags include a metastatic flag option - and that a number of cases are flagged as such - just briefly explore the category of metastatic in relation to the metastatic windows I've provided.

```{r}

met_flag<-exclusion_df_3_4 |>
  select(PatientNo, tissue_dx_date, neo_rad:neo_hormone,adj_chemo:adj_rad, met_at_dx:met_at_120_days)|>
  filter(neo_rad == "n/a - treatment for metastatic disease" | 
           neo_chemo =="n/a - treatment for metastatic disease" | 
           neo_mab =="n/a - treatment for metastatic disease" |
           neo_hormone =="n/a - treatment for metastatic disease" |
           adj_chemo =="n/a - treatment for metastatic disease" |
           adj_mab =="n/a - treatment for metastatic disease" |
           adj_hormone=="n/a - treatment for metastatic disease" |
           ovarian_ablation =="n/a - treatment for metastatic disease" |
           adj_rad =="n/a - treatment for metastatic disease") |>
  mutate(flagged_as_met_treatment = "YES")

met_flag|>
  group_by(flagged_as_met_treatment)|>
  mutate(across(c(met_at_dx:met_at_120_days), as_factor))|>
  summarise(across(c(met_at_dx:met_at_120_days), ~ mean(.x == "YES")))|>
  gt()|>
  tab_header(
    title="Percent of Patients Flagged as Metastatic in Treatment Column Showing
    as Metastatic by Date of Metastatsis relative to Tissue Diagnosis Date"
  ) |>
  fmt_number(
    decimals = 2
  )|>
  gtsave(filename = "met_at_treatment.png")

met_flag<-met_flag |>
  select(PatientNo, tissue_dx_date, flagged_as_met_treatment)

exclusion_df_3_5 <-exclusion_df_3_4 |>
  left_join(met_flag, join_by(PatientNo,tissue_dx_date))|>
  filter(is.na(flagged_as_met_treatment))|>
  select(!c(flagged_as_met_treatment))


save(exclusion_df_3_5, file="/Users/rms/Library/CloudStorage/OneDrive-Personal/Documents/PhD_Stuff/PREDICT_BREAST_NZ_calibration/BCF_data/tidy_Aug_23_Data/exclusion_df_3_5.Rda")  
```

![](met_at_treatment.png)

This identifies 41 cases that were flagged at entry as having metastatic disease - but noting that they are not flagged as metastatic by the first date of a metastasis relative to tissue diagnosis date.

Remove the 41 in dataframe.

Creation of exclusion_df_4

This final step removes the cases that had neo-adjuvant therapy (any type) or were missing data about receipt of neo-adjuvant.

```{r}

exclusion_df_4_1<-exclusion_df_3_5|>
  select(!c(neo_rad:neo_hormone))|>
  filter(!c(neo_given == "YES" | is.na(neo_given)))

save(exclusion_df_4_1, file="/Users/rms/Library/CloudStorage/OneDrive-Personal/Documents/PhD_Stuff/PREDICT_BREAST_NZ_calibration/BCF_data/tidy_Aug_23_Data/exclusion_df_4_1.Rda")

```
