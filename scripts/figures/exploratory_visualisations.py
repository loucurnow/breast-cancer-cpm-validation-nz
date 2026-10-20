import matplotlib.pyplot as plt
import missingno as msno
import pandas as pd
import seaborn as sns
from lifelines import KaplanMeierFitter

import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# ==========================================
# 0. CONFIGURATION & SETUP
# ==========================================
# Set up plotting styles
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({"figure.autolayout": True, "font.size": 11})


import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from utils.analysis_vars import bin_age, bin_nodes, bin_size, pos_neg_unknown, screening_str_vals

# Create directory to save plots
output_dir = "./figures/bcfnr/eda_plots"
os.makedirs(output_dir, exist_ok=True)


# Define variables based on your schema
numerical_vars = [
    "age.start.in",
    "size.in",
    "nodes.in",
    "diag.year",
]
numerical_var_labels = [
    "Age at Diagnosis",
    "Tumor Size (mm)",
    "Number of Positive Nodes",
    "Diagnosis Year",
]

categorical_vars = [
    "smoker.in.str",
    "menopause",
    "Region",
    "screen.in.str",
    "er.in.str",
    "pr.in.str",
    "her2.in.str",
    "ethnicity_recoded",
    "grade.in",
]
categorical_var_labels = [
    "Smoker Status",
    "Menopause Status",
    "Region",
    "Referral Source",
    "Oestrogen Receptor (ER) Status",
    "Progesterone Receptor (PR) Status",
    "Human Epidermal Growth Factor Receptor 2 (HER2) Status",
    "Ethnicity",
    "Tumor Grade",
]

all_vars = numerical_vars + categorical_vars


def plot_diagnosis_year_by_region(df):

    # plot diagnosis year distribution by region
    plt.figure(figsize=(10, 6))
    sns.countplot(data=df, x="diag.year", hue="Region")
    plt.title("Diagnosis Year Distribution by Region", fontweight="bold")
    plt.xlabel("Diagnosis Year")
    plt.ylabel("Count")
    plt.legend(title="Region", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(f"{output_dir}/diag_year_by_region.pdf", dpi=300, bbox_inches="tight")
    plt.savefig(f"{output_dir}/diag_year_by_region.png", dpi=300, bbox_inches="tight")
    plt.close()


# ==========================================
# 1. UNIVARIATE DISTRIBUTIONS
# ==========================================
def plot_univariate_distributions(df):
  print("Generating univariate distribution plots...")

  # Numerical distributions (Histograms with KDE)
  for col in numerical_vars:
    print(col)
    print(df[col].max())
    plt.figure(figsize=(8, 5))
    sns.histplot(
        df[col].dropna(), kde=True, color="teal", bins=30, edgecolor="black"
    )
    plt.title(f"Distribution of {numerical_var_labels[numerical_vars.index(col)]}", fontsize=14, weight="bold")
    plt.xlabel(numerical_var_labels[numerical_vars.index(col)])
    plt.ylabel("Count")
    plt.savefig(f"{output_dir}/dist_{col}.png", dpi=300)
    plt.close()

  # Categorical distributions (Count plots)
  for col in categorical_vars:
    print(col)
    print(df[col].value_counts())
    plt.figure(figsize=(10, 5))
    ax = sns.countplot(
        data=df,
        x=col,
        order=df[col].value_counts().index,
        palette="Blues_r",
    )
    plt.title(f"Frequency Count of {categorical_var_labels[categorical_vars.index(col)]}", fontsize=14, weight="bold")
    plt.xlabel(categorical_var_labels[categorical_vars.index(col)])
    plt.ylabel("Count")
    plt.xticks(rotation=45, ha="right")

    # Add data labels on top of bars
    for p in ax.patches:
      ax.annotate(
          f"{int(p.get_height())}",
          (p.get_x() + p.get_width() / 2.0, p.get_height()),
          ha="center",
          va="bottom",
          fontsize=9,
          xytext=(0, 3),
          textcoords="offset points",
      )

    plt.savefig(f"{output_dir}/count_{col}.png", dpi=300)
    plt.close()


# ==========================================
# 2. ADVANCED COMPARATIVE VISUALIZATIONS
# ==========================================
def plot_comparative_analyses(df):
  print("Generating advanced comparative visualizations...")

  # --- A. Grouping by Region ---
  # Tumor Size by Region (Boxplot + Strip plot)
  # filter out region = 'NA_character_'
  df_filtered = df[df["Region"] != "NA_character_"]

  plt.figure(figsize=(12, 6))
  sns.boxplot(
      data=df_filtered, x="Region", y="size.in", palette="Set2", showmeans=True
  )
  sns.stripplot(
      data=df_filtered,
      x="Region",
      y="size.in",
      color="black",
      alpha=0.3,
      jitter=0.2,
      size=4,
  )
  plt.title("Tumor Size Distribution Across Regions", fontsize=14, weight="bold")
  plt.xticks(rotation=45, ha="right")
  plt.savefig(f"{output_dir}/compare_size_by_region.png", dpi=300)
  plt.close()

  # Referral source by region
  plt.figure(figsize=(12, 6))
  sns.countplot(
      data=df_filtered,
      x="Region",
      hue="screen.in.str",
      palette="Set1",
  )
  plt.title("Referral Source Distribution Across Regions", fontsize=14, weight="bold")
  plt.xticks(rotation=45, ha="right")
  plt.savefig(f"{output_dir}/compare_referral_by_region.png", dpi=300)
  plt.close()

  # grade by region
  plt.figure(figsize=(12, 6))
  sns.countplot(
      data=df_filtered,
      x="Region",
      hue="grade.in",
      palette="Set3",
  )
  plt.title("Tumor Grade Distribution Across Regions", fontsize=14, weight="bold")
  plt.xticks(rotation=45, ha="right")
  plt.savefig(f"{output_dir}/compare_grade_by_region.png", dpi=300)
  plt.close()

  # positive node count by region
  plt.figure(figsize=(12, 6))
  sns.violinplot(
      data=df_filtered, x="Region", y="nodes.in", palette="Pastel2", inner="quartile"
  )
  plt.title("Positive Node Count Distribution Across Regions", fontsize=14, weight="bold")
  plt.xticks(rotation=45, ha="right")
  plt.savefig(f"{output_dir}/compare_nodes_by_region.png", dpi=300)
  plt.close()

  # smoker status by region
  plt.figure(figsize=(12, 6))
  sns.countplot(
      data=df_filtered,
      x="Region",
      hue="smoker.in.str",
      palette="Set2",
  )
  plt.title("Smoker Status Distribution Across Regions", fontsize=14, weight="bold")
  plt.xticks(rotation=45, ha="right")
  plt.savefig(f"{output_dir}/compare_smoker_by_region.png", dpi=300)
  plt.close()

  # --- B. Grouping by Ethnicity ---
  # Age at start by Ethnicity
  plt.figure(figsize=(12, 6))
  sns.violinplot(
      data=df, x="ethnicity_recoded", y="age.start.in", palette="Pastel1", inner="quartile"
  )
  plt.title("Age Distribution by Recoded Ethnicity", fontsize=14, weight="bold")
  plt.xticks(rotation=45, ha="right")
  plt.savefig(f"{output_dir}/compare_age_by_ethnicity.png", dpi=300)
  plt.close()

  # --- C. Grouping by Diagnosis Year (Trends Over Time) ---
  # Yearly count of diagnoses tracked by Region
  plt.figure(figsize=(12, 6))
  yearly_region = (
      df_filtered.groupby(["diag.year", "Region"]).size().reset_index(name="count")
  )
  sns.lineplot(
      data=yearly_region,
      x="diag.year",
      y="count",
      hue="Region",
      marker="o",
      linewidth=2.5,
  )
  plt.title("Diagnostic Trends Over Years by Region", fontsize=14, weight="bold")
  plt.xlabel("Diagnosis Year")
  plt.ylabel("Number of Cases")
  plt.savefig(f"{output_dir}/trend_cases_by_year_region.png", dpi=300)
  plt.close()

  # --- D. Interesting Inter-variable Comparisons ---
  # 1. Smoker Status vs Tumor Grade (Stacked/Grouped Bar Chart)
  if "smoker.in.str" in df.columns and "grade.in" in df.columns:
    plt.figure(figsize=(10, 6))
    cross_tab = pd.crosstab(df["smoker.in.str"], df["grade.in"], normalize="index") * 100
    cross_tab.plot(kind="bar", stacked=True, colormap="viridis", figsize=(10, 6))
    plt.title("Tumor Grade Proportion by Smoking Status (%)", fontsize=14, weight="bold")
    plt.xlabel("Smoker Status")
    plt.ylabel("Percentage (%)")
    plt.legend(title="Grade", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.xticks(rotation=0)
    plt.savefig(f"{output_dir}/compare_smoker_vs_grade.png", dpi=300)
    plt.close()

  # 2. Correlation Heatmap for Numerical Variables
  plt.figure(figsize=(8, 6))
  corr = df[numerical_vars].corr()
  sns.heatmap(
      corr, annot=True, cmap="coolwarm", fmt=".2f", linewidths=0.5, vmin=-1, vmax=1
  )
  plt.title("Correlation Matrix of Numerical Variables", fontsize=14, weight="bold")
  plt.savefig(f"{output_dir}/correlation_heatmap.png", dpi=300)
  plt.close()

  # 3. Receptor Status Breakdown across Ethnicity (ER status vs Ethnicity)
  if "er.in.str" in df.columns and "ethnicity_recoded" in df.columns:
    plt.figure(figsize=(12, 6))
    sns.histplot(
    data=df,
    x="ethnicity_recoded",
    hue="er.in.str",
    multiple="fill",  # Turns it into a 100% normalized stacked bar representation
    palette="Set3",
    shrink=0.8,
    )
    plt.title("Distribution of Oestrogen Receptor (ER) Status by Ethnicity", fontsize=14, weight="bold")
    plt.xlabel("Ethnicity")
    plt.ylabel("Count")
    plt.xticks(rotation=45, ha="right")
    plt.legend(title="ER Status")
    plt.savefig(f"{output_dir}/compare_er_by_ethnicity.png", dpi=300)
    plt.close()

  if "pr.in.str" in df.columns and "ethnicity_recoded" in df.columns:
    plt.figure(figsize=(12, 6))
    sns.histplot(
    data=df,
    x="ethnicity_recoded",
    hue="er.in.str",
    multiple="fill",  # Turns it into a 100% normalized stacked bar representation
    palette="Set3",
    shrink=0.8,
    )
    plt.title("Distribution of Progesterone Receptor (PR) Status by Ethnicity", fontsize=14, weight="bold")
    plt.xlabel("Ethnicity")
    plt.ylabel("Count")
    plt.xticks(rotation=45, ha="right")
    plt.legend(title="PR Status")
    plt.savefig(f"{output_dir}/compare_pr_by_ethnicity.png", dpi=300)
    plt.close()

  if "her2.in.str" in df.columns and "ethnicity_recoded" in df.columns:
    plt.figure(figsize=(12, 6))
    sns.histplot(
    data=df,
    x="ethnicity_recoded",
    hue="her2.in.str",
    multiple="fill",  # Turns it into a 100% normalized stacked bar representation
    palette="Set3",
    shrink=0.8,
    )
    plt.title("Distribution of Human Epidermal Growth Factor Receptor 2 (HER2) Status by Ethnicity", fontsize=14, weight="bold")
    plt.xlabel("Ethnicity")
    plt.ylabel("Count")
    plt.xticks(rotation=45, ha="right")
    plt.legend(title="HER2 Status")
    plt.savefig(f"{output_dir}/compare_her2_by_ethnicity.png", dpi=300)
    plt.close()
        
  # --- Diagnosis Year Trend by Region (Time Series Line Plot) ---
  if "diag.year" in df.columns and "Region" in df.columns:
    # filter out rows with missing diagnosis year or region
    df_filtered = df[df["Region"] != "NA_character_"]

    plt.figure(figsize=(12, 6))

    # Aggregate counts by year and region
    yearly_region = (
        df_filtered.groupby(["diag.year", "Region"]).size().reset_index(name="count")
    )

    # Plot time series lines
    ax = sns.lineplot(
        data=yearly_region,
        x="diag.year",
        y="count",
        hue="Region",
        marker="o",
        linewidth=2.5,
        markersize=6,
    )

    plt.title("Count of Diagnoses by Year and Region", fontsize=14, weight="bold")
    plt.xlabel("Diagnosis Year")
    plt.ylabel("Count of Diagnoses")

    # Format x-axis ticks to show labels every 5 years
    min_year = int(yearly_region["diag.year"].min())
    max_year = int(yearly_region["diag.year"].max())
    # Round down to nearest 5 for the start tick
    start_tick = min_year - (min_year % 5)
    plt.xticks(range(start_tick, max_year + 1, 5), rotation=0)

    plt.legend(title="Region", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.savefig(f"{output_dir}/trend_diag_year_by_region.png", dpi=300, bbox_inches="tight")
    plt.close()


# ==========================================
# MAIN EXECUTION BLOCK
# ==========================================
if __name__ == "__main__":
  # Replace 'your_dataset.csv' with your actual file path
  df = pd.read_pickle("./datasets/bcfnz/pickle/processed/predict_3_model_results.pickle")
  df["ethnicity_recoded"] = df["ethnic"].apply(lambda x: "Māori" if x == "Maori" else "Other" if x not in ["European", "Māori", "Pacific Peoples", "Asian"] else x)
  df["screen.in.str"] = df["screen.in"].apply(screening_str_vals)
  df["er.in.str"] = df["er.in"].apply(pos_neg_unknown)
  df["pr.in.str"] = df["pr.in"].apply(pos_neg_unknown)
  df["her2.in.str"] = df["her2.in"].apply(pos_neg_unknown)
  df['smoker.in.str'] = df['smoker.in'].apply(lambda x: 'Smoker' if x == 1 else 'Non-Smoker' if x == 0 else 'Unknown')
  df = df[df['nodes.in'] != 999]

  # --- Define custom orders for categorical variables ---
  grade_order = [1, 2, 3] 
  smoker_order = ["Smoker", "Non-Smoker", "Unknown"]  
  her_order = ["Positive", "Negative", "Unknown"] 
  ethnicity_order = ["Māori", "Pacific Peoples", "European", "Asian", "Other"]
  
  # Convert to categorical type with explicit order
  if "grade.in" in df.columns:
    df["grade.in"] = pd.Categorical(
        df["grade.in"], categories=grade_order, ordered=True
    )

  if "smoker.in.str" in df.columns:
    df["smoker.in.str"] = pd.Categorical(
        df["smoker.in.str"], categories=smoker_order, ordered=True
    )

  if "her2.in.str" in df.columns:
    df["her2.in.str"] = pd.Categorical(
        df["her2.in.str"], categories=her_order, ordered=True
    )

  if "ethnicity_recoded" in df.columns:
    df["ethnicity_recoded"] = pd.Categorical(
        df["ethnicity_recoded"], categories=ethnicity_order, ordered=True
    )

  plot_univariate_distributions(df)
  plot_comparative_analyses(df)
  plot_diagnosis_year_by_region(df)