"""
Summarise the transformed data in a table format for the report.

This includes variables from all 
"""

import os
import sys
from pathlib import Path
import pandas as pd
import warnings 
warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered in cast")


project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from scripts.compare_dataframes import load_py, load_r
from preprocessing.derived_vars import binary_neoadj_adj, dcis, days_to_mets
from utils.summary_funcs import duplicates_by_unique_id
from utils.dataviz import cohort_flowchart



dir = Path('datasets/bcfnz/pickle/processed/')

data_pickle = dir / 'filtered_cohort.pickle'

input_df = load_py(data_pickle)

input_df = input_df[input_df['nodes.in'] != 999]

# there are too many variables to summarise in one table. some are intermediate variables that are not relevant to the report.
# we will summarise the variables that are relevant to the report.

model_cols = ['age.start.in', 'screen.in', 'size.in', 'grade.in', 'nodes.in', 'er.in', 'her2.in', 
                'ki67.in', 'pr.in', 'generation.in', 'horm.in', 'traz.in', 'bis.in',
                'radio.in', 'heart.gy.in', 'smoker.in']

dem_cols = ['unique_key', 'diag.year', 'ethnic', 'menopause', 'Region', 
            'dod', 'cod', 'final_survival_sweep']

cohort_cols = ['days_to_mets', 'cohort_valid_diagnosis', 'cohort_female', 
               'cohort_first_diagnosis', 'cohort_dx_20_85', 'cohort_no_neoadj', 
 'cohort_no_mets_baseline', 'cohort_no_dcis', 'cohort_primary_surgery', 'cohort_locoregional_complete', 
 'cohort_tumour_details','cohort_er_valid']


other_cols = ['brca_result', 'ax_node_presence', 'node_total_remove', 
              'node_involved_count', 'node_largest_deposit',
              'primary_surgery', 
              'adj_rad', 'adj_chemo', 'adj_mab', 'adj_hormone']

surv_model_cols = ['surv.time.actual', 'days.to.censor', 'days.to.death', 'surv.actual', 'treatments.given']

col_selection = model_cols + dem_cols + cohort_cols + other_cols + surv_model_cols

model_df = input_df[col_selection]

surgical_completeness_cols =  ['any_mastectomy', 'any_ppx_mastectomy', 'any_wle_with_rt', 'any_wle_no_rt', 
 'any_surg_data_excl_ppx_mast', 'L_breast_final_completion_status', 'R_breast_final_completion_status', 
 'insufficient_breast_surg_data', 'rules_based_surgical_completion_breast', 'any_l2_l3', 'any_l1_snb', 
 'L_node_final_completion_status', 'R_node_final_completion_status', 'insufficient_node_surg_data', 
 'rules_based_surgical_completion_node', 'R_locoregional_complete', 'L_locoregional_complete', 'bilat_locoregional_complete', 
 'surgical_data_sufficient', 'primary_data_locoregional_completion', 'rules_based_locoregional_completion', 
 'final_locoregional_completion']

surg_complete_df = input_df[surgical_completeness_cols]

# create a summary table for main df
df_summary = model_df.describe(include='all').transpose()

# create a summary table for the surgical completeness variables
surg_complete_summary = surg_complete_df.describe(include='all').transpose()


def make_overleaf_file(filepath, latex_content):
  """Writes the generated LaTeX string into a .tex file,

  creating directories if they don't exist.
  """
  os.makedirs(os.path.dirname(filepath), exist_ok=True)
  with open(filepath, "w", encoding="utf-8") as f:
    f.write(latex_content)


def summary_table(df, title, output_path):
    for col in df.select_dtypes(include=["datetime64[ns]"]).columns:
        df[col] = df[col].dt.date.astype(str)

    # Generate descriptive statistics for all columns (numeric and non-numeric)
    summary_table = df.describe(include="all").transpose()

    # Add custom columns for missing values, data type, and variable names
    summary_table["missing"] = df.isnull().sum()
    summary_table["dtype"] = df.dtypes.astype(str)
    summary_table["variable"] = summary_table.index

    # Ensure all expected columns exist (categorical columns lack mean/std/percentiles)
    expected_cols = [
        "variable",
        "dtype",
        "count",
        "mean",
        "std",
        "min",
        "max",
        "missing",
    ]

    for col in expected_cols:
        if col not in summary_table.columns:
            summary_table[col] = ""  # Fill missing statistical columns safely

    # Reorder the columns
    summary_table = summary_table[expected_cols]

    # Format output filename
    safe_filename = title.lower().replace(" ", "_").replace("-", "_")
    output_path = f"tables/tex/{safe_filename}_summary.tex"

    # Export to LaTeX string and save file
    latex_code = summary_table.to_latex(
        index=False,
        float_format="%.3f",
        na_rep="-",  # Represent NaN values cleanly with a dash in the table
        escape=True,  # Escape special LaTeX characters like underscores in variable names
    )

    make_overleaf_file(output_path, latex_code)
    print(f"Successfully generated: {output_path}")


summary_table(model_df, "Transformed Data Summary", "tables/tex/transformed_data_summary.tex")
summary_table(surg_complete_df, "Surgical Completeness Summary", "tables/tex/surgical_completeness_summary.tex")

print("All summary tables generated!")

