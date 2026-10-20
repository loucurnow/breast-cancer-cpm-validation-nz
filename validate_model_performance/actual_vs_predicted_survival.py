import numpy as np
import pandas as pd
from pathlib import Path
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test
from scipy import stats

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from utils.analysis_vars import bin_age, bin_diag_year, bin_nodes, bin_size, screening_str_vals, pos_neg_unknown

df = pd.read_pickle("./datasets/bcfnz/pickle/processed/predict_3_model_results.pickle")

df['death.event'] = 1 - df['surv.actual']

FINAL_FOLLOWUP_YEAR = 2023
        
T_5_YEARS = 5 * 365.25
T_10_YEARS = 10 * 365.25

def calculate_calibration_pval(sub, pred_col, target_time):
  """Calculates a p-value testing if model predictions match Kaplan-Meier observed survival

  using a one-sample z-test on binary outcomes at the specific landmark time,
  accounting for censoring via pseudo-values or binomial approximation.
  """
  n = len(sub)
  if n < 5:
    return 1.0

  # Mean predicted survival for this subgroup
  mean_pred = (1 - sub[pred_col].mean()) * 100

  # Observed KM survival percentage
  obs_surv = get_km_survival(
      sub["surv.time.actual"], sub["death.event"], target_time
  )
  if np.isnan(obs_surv):
    return 1.0

  # Standard error approximation for the proportion
  obs_fraction = obs_surv / 100.0
  se = np.sqrt((obs_fraction * (1 - obs_fraction)) / n) * 100
  if se == 0:
    return 1.0

  # Z-score and two-tailed p-value
  z_stat = (mean_pred - obs_surv) / se
  p_val = 2 * (1 - stats.norm.cdf(abs(z_stat)))
  return p_val


def get_km_survival(time_col, event_col, target_time):
  """Calculates Kaplan-Meier survival probability at a specific point in time."""
  if len(time_col) == 0:
    return np.nan
  kmf = KaplanMeierFitter()
  try:
    kmf.fit(durations=time_col, event_observed=event_col)

    # Extract the survival function dataframe
    surv_df = kmf.survival_function_

    # Find the closest timeline index less than or equal to the target time
    # (If target_time is before the very first event, fallback to 1.0)
    valid_rows = surv_df[surv_df.index <= target_time]
    if len(valid_rows) == 0:
      return 100.0

    # Get the survival probability at the latest recorded time <= target_time
    surv_prob = valid_rows.iloc[-1, 0]
    return surv_prob * 100
  except Exception as e:
    return np.nan


def compute_metrics(data, group_col, group_name, total_n_5yrs, total_n_10yrs):
  rows = []
  rows.append(f"\\textbf{{{group_name}}} \\\\")

  grouped = data.groupby(group_col, dropna=False)

  for cat, sub in grouped:
    sub_5yr = sub[sub["diag.year"] <= FINAL_FOLLOWUP_YEAR - 5]
    sub_10yr = sub[sub["diag.year"] <= FINAL_FOLLOWUP_YEAR - 10]

    # DEBUG: Check event distribution in the filtered subset
    print(f"Cohort: {cat}")
    print(
        "Total rows 5 years:",
        len(sub_5yr),
        "Events (surv.actual == 1):",
        sub_5yr["surv.actual"].sum(),
    )
    print(
        "Min time:",
        sub_5yr["surv.time.actual"].min(),
        "Max time:",
        sub_5yr["surv.time.actual"].max(),
    )

    print(
        "Total rows 10 years:",
        len(sub_10yr),
        "Events (surv.actual == 1):",
        sub_10yr["surv.actual"].sum(),
    )
    print(
        "Min time:",
        sub_10yr["surv.time.actual"].min(),
        "Max time:",
        sub_10yr["surv.time.actual"].max(),
    )

    if len(sub_5yr) == 0:
      continue

    n_5yrs = len(sub_5yr)
    pct_total_5 = (n_5yrs / total_n_5yrs) * 100

    n_10yrs = len(sub_10yr)
    pct_total_10 = (n_10yrs / total_n_10yrs) * 100

    # 1. PREDICTED OS (%)
    # pred columns are probability of death (0 to 1)
    # Predicted Survival % = (1 - mean probability of death) * 100
    pred_5 = (1 - sub_5yr["pred_all_yr5"].mean()) * 100
    pred_10 = (1 - sub_10yr["pred_all_yr10"].mean()) * 100

    # 2. OBSERVED OS (%) using Kaplan-Meier Estimator
    obs_5 = (
        get_km_survival(
            sub_5yr["surv.time.actual"], sub_5yr["death.event"], T_5_YEARS
        )
        if n_5yrs > 0
        else 0.0
    )
    obs_10 = (
        get_km_survival(
            sub_10yr["surv.time.actual"], sub_10yr["death.event"], T_10_YEARS
        )
        if n_10yrs > 0
        else 0.0
    )

    print(
        "observed survival: 5yr:", obs_5, "10yr:", obs_10, "predicted survival: 5yr:", pred_5, "10yr:", pred_10
    )

    # 3. DIFFERENCE (%)
    diff_5 = obs_5 - pred_5
    diff_10 = obs_10 - pred_10

    # 4. P-VALUE
    # Calculated p-values (Calibration p-value comparing prediction to observation)
    p_5 = calculate_calibration_pval(sub_5yr, "pred_all_yr5", T_5_YEARS)
    p_10 = calculate_calibration_pval(sub_10yr, "pred_all_yr10", T_10_YEARS)

    cat_label = str(cat)
    row_str = (
        f"\\quad {cat_label} & {n_5yrs:,} ({pct_total_5:.1f}) "
        f"& {pred_5:.1f} & {obs_5:.1f} & {diff_5:+.1f} & {p_5:.3f} "
        f"& {n_10yrs:,} ({pct_total_10:.1f}) "
        f"& {pred_10:.1f} & {obs_10:.1f} & {diff_10:+.1f} & {p_10:.3f}"
        f" \\\\"
    )
    rows.append(row_str)

  return rows


# 2. ENTIRE COHORT CALCULATION
# filter to just the patients with at least 5 yers of follow-up or who died within 5 years: diagnosed <= 2018-12-31
df_5yrs = df[df["diag.year"] <= FINAL_FOLLOWUP_YEAR - 5]
# same for 10 years
df_10yrs = df[df["diag.year"] <= FINAL_FOLLOWUP_YEAR - 10]

total_n_5yrs = len(df_5yrs)
total_n_10yrs = len(df_10yrs)
cohort_pred_5 = (1 - df_5yrs["pred_all_yr5"].mean()) * 100
cohort_pred_10 = (1 - df_10yrs["pred_all_yr10"].mean()) * 100

cohort_obs_5 = get_km_survival(
    df_5yrs["surv.time.actual"], df_5yrs["death.event"], T_5_YEARS
)
cohort_obs_10 = get_km_survival(
    df_10yrs["surv.time.actual"], df_10yrs["death.event"], T_10_YEARS
)

cohort_diff_5 = cohort_obs_5 - cohort_pred_5
cohort_diff_10 = cohort_obs_10 - cohort_pred_10

# p values
p_5 = calculate_calibration_pval(df_5yrs, "pred_all_yr5", T_5_YEARS)
p_10 = calculate_calibration_pval(df_10yrs, "pred_all_yr10", T_10_YEARS)

entire_cohort_row = (
    f"Entire cohort & {total_n_5yrs:,} (100) &"
    f" {cohort_pred_5:.1f} & {cohort_obs_5:.1f} & {cohort_diff_5:+.1f} & {p_5:.3f} &"
    f" {total_n_10yrs:,} (100) &"
    f" {cohort_pred_10:.1f} & {cohort_obs_10:.1f} &"
    f" {cohort_diff_10:+.1f} & {p_10:.3f} \\\\"
)

# 3. GENERATE ALL SUB-GROUPS
table_rows = [entire_cohort_row, "\\midrule"]

# referral source
df["screen.in.str"] = df["screen.in"].apply(screening_str_vals)
table_rows.extend(compute_metrics(df, "screen.in.str", "Screening Referred", total_n_5yrs, total_n_10yrs))
table_rows.append("\\midrule")


# ER status
df["er.in.str"] = df["er.in"].apply(pos_neg_unknown)
df["pr.in.str"] = df["pr.in"].apply(pos_neg_unknown)
df["her2.in.str"] = df["her2.in"].apply(pos_neg_unknown)

table_rows.extend(compute_metrics(df, "er.in", "ER status", total_n_5yrs, total_n_10yrs))
table_rows.append("\\midrule")

# PR status
table_rows.extend(compute_metrics(df, "pr.in.str", "PR status", total_n_5yrs, total_n_10yrs))
table_rows.append("\\midrule")

# HER2 status
table_rows.extend(compute_metrics(df, "her2.in.str", "HER2 status", total_n_5yrs, total_n_10yrs))
table_rows.append("\\midrule")

# Grade
table_rows.extend(compute_metrics(df, "grade.in", "Grade", total_n_5yrs, total_n_10yrs))
table_rows.append("\\midrule")


df["nodes_binned"] = df["nodes.in"].apply(bin_nodes)
table_rows.extend(
    compute_metrics(df, "nodes_binned", "Positive nodes", total_n_5yrs, total_n_10yrs)
)
table_rows.append("\\midrule")

df["size_binned"] = df["size.in"].apply(bin_size)
table_rows.extend(
    compute_metrics(df, "size_binned", "Invasive tumour size", total_n_5yrs, total_n_10yrs)
)
table_rows.append("\\midrule")

df["age_binned"] = df["age.start.in"].apply(bin_age)
table_rows.extend(compute_metrics(df, "age_binned", "Age", total_n_5yrs, total_n_10yrs))

table_rows.append("\\midrule")
df["ethnicity_recoded"] = df["ethnic"].apply(lambda x: "Māori" if x == "Maori" else "Other" if x not in ["European", "Māori", "Pacific Peoples", "Asian"] else x)
table_rows.extend(compute_metrics(df, "ethnicity_recoded", "Ethnicity", total_n_5yrs, total_n_10yrs))

table_rows.append("\\midrule")
df["diag_year_binned"] = df["diag.year"].apply(bin_diag_year)
table_rows.extend(compute_metrics(df, "diag_year_binned", "Diagnosis Year", total_n_5yrs, total_n_10yrs))

table_rows.append("\\midrule")
table_rows.extend(compute_metrics(df, "Region", "Region", total_n_5yrs, total_n_10yrs))

# 4. BUILD FINAL LATEX STRING
latex_content = r"""
\begin{landscape}
\begin{table}[ht]
\setlength{\tabcolsep}{3pt}
\centering
\caption{Observed and predicted overall survival (5 and 10 years)}
\resizebox{\textwidth}{!}{% Scale down to fit exact page height/width
\begin{tabular}{lcccccccccc}
\toprule
& \multirow{2}{*}{N (\%)} & \multicolumn{4}{c}{5-year OS} 
& \multirow{2}{*}{N (\%)} & \multicolumn{4}{c}{10-year OS} \\
\cmidrule(lr){3-6} \cmidrule(lr){8-11}
&& Predicted (\%) & Observed (\%) & Diff (\%) & p-value* && Predicted (\%) & Observed (\%) & Diff (\%) & p-value* \\
\midrule
"""

latex_content += "\n".join(table_rows)

latex_content += r"""
\bottomrule
\end{tabular}
}% Close resizebox
\end{table}
\end{landscape}
"""

# 5. WRITE TO .TEX FILE
with open(Path("./tables/tex/survival_table.tex"), "w") as f:
  f.write(latex_content)

print("LaTeX table successfully generated and saved to 'survival_table.tex'!")

print(list(df.columns))