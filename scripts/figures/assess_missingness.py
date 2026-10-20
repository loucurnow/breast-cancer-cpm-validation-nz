import matplotlib.pyplot as plt
import missingno as msno
import pandas as pd
import seaborn as sns
from lifelines import KaplanMeierFitter

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from utils.analysis_vars import bin_age, bin_nodes, bin_size, pos_neg_unknown, screening_str_vals

df = pd.read_pickle("./datasets/bcfnz/pickle/processed/unfiltered_with_nhs_vars.pickle")
df["ethnicity_recoded"] = df["ethnic"].apply(lambda x: "Māori" if x == "Maori" else "Other" if x not in ["European", "Māori", "Pacific Peoples", "Asian"] else x)
df["screen.in.str"] = df["screen.in"].apply(screening_str_vals)


# Map your columns to clean names if necessary
# Let's assume your dataset has columns like:
# 'er.in', 'tumor_size', 'grade.in', 'nodes.in', 'diagnosis_year', 'ethnicity', 'region'
missing_cols = ["er.in", "size.in", "grade.in", "nodes.in"]
aux_cols = ["diag.year", "ethnicity_recoded", "Region", "screen.in.str"]

# Set plot style
sns.set_theme(style="whitegrid")
plt.rcParams.update({
    "font.size": 8,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.titlesize": 11,
})

features_to_plot = [
    ("diag.year", "Diagnosis Year"),
    ("ethnicity_recoded", "Ethnicity"),
    ("Region", "Region"),
    ("screen.in.str", "Referral Source"),
]


# Creates a binary missing indicator for each key variable
for col in missing_cols:
  df[f"{col}_missing"] = df[col].isna().astype(int)

# Plot and save the missing variables by year first


fig, axes = plt.subplots(
    nrows=2, ncols=2, figsize=(12, 7), sharex=False, sharey=True
)
axes = axes.flatten()

palette = sns.color_palette("tab10", len(missing_cols))


for idx, (group_col, title) in enumerate(features_to_plot):
  ax = axes[idx]

  # Calculate missing percentage grouped by the feature
  group_missing = (
      df.groupby(group_col, observed=True)[
          [f"{col}_missing" for col in missing_cols]
      ].mean()
      * 100
  )

  # Plot each missing column on the specific subplot axis (ax.plot instead of plt.plot)
  for c_idx, col in enumerate(missing_cols):
    ax.plot(
        group_missing.index.astype(str),
        group_missing[f"{col}_missing"],
        marker="o",
        linewidth=1.5,
        label=col,
        color=palette[c_idx],
    )

    ax.set_title(title, fontweight="bold")
    ax.set_ylabel("Missing (%)")
    ax.set_ylim(-2, 105)  # Percentage bounds

  #ax.set_xlim(0, len(group_missing))
  # Custom tick handling for Diagnosis Year
  if group_col == "diag.year":
    # Extract ticks and filter for years that are multiples of 5
    xticks = ax.get_xticks()
    xticklabels = [label.get_text() for label in ax.get_xticklabels()]
    
    # Filter ticks where the year integer is divisible by 5
    filtered_ticks = []
    filtered_labels = []
    for tick, label in zip(xticks, xticklabels):
      try:
        year_val = int(label)
        if year_val % 5 == 0:
          filtered_ticks.append(tick)
          filtered_labels.append(label)
      except ValueError:
        continue
        
    ax.set_xticks(filtered_ticks)
    ax.set_xticklabels(filtered_labels, rotation=0, ha="center")
  else:
    plt.sca(ax)
    plt.xticks(rotation=30, ha="right")

  # Add legend only to the first subplot to reduce clutter
  if idx == 0:
    ax.legend(title="Variables", loc="upper right")

  # Add legend only to the first subplot to reduce clutter, or keep on all
  if idx == 0:
    ax.legend(title="Variables", loc="upper right")

plt.tight_layout()
Path("./figures/bcfnr").mkdir(parents=True, exist_ok=True)
plt.savefig("./figures/bcfnr/missingness_by_groups.pdf", dpi=300, bbox_inches="tight")
plt.savefig("./figures/bcfnr/missingness_by_groups.png", dpi=300, bbox_inches="tight")
plt.close()

print(
    "Missingness breakdown plots successfully generated and saved to"
    " './figures/bcfnr/'!"
)


# also plot missingness by year for ER status, with groups for diagnosis region
# -------------------------------------------------------------------------
# 1. Missingness of 'er.in' over Diagnosis Year, split by Region (U-shape check)
# -------------------------------------------------------------------------
plt.figure(figsize=(12, 6))

# Calculate percentage of missing 'er.in' grouped by diagnosis year and region
er_missing_by_year_region = (
    df.groupby(["diag.year", "Region"], observed=False)["er.in_missing"]
    .mean()
    .reset_index()
)
er_missing_by_year_region["er.in_missing"] *= 100

# Create line plot
sns.lineplot(
    data=er_missing_by_year_region,
    x="diag.year",
    y="er.in_missing",
    hue="Region",
    marker="o",
    linewidth=1.5
)

plt.title("ER Status Missingness Over Diagnosis Year by Region", fontweight="bold")
plt.xlabel("Diagnosis Year")
plt.ylabel("ER Status Missing (%)")
plt.ylim(-2, 105)
plt.legend(title="Region", bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()

# Save figure
Path("./figures/bcfnr").mkdir(parents=True, exist_ok=True)
plt.savefig("./figures/bcfnr/er_missingness_by_year_and_region.pdf", dpi=300, bbox_inches="tight")
plt.savefig("./figures/bcfnr/er_missingness_by_year_and_region.png", dpi=300, bbox_inches="tight")
plt.close()


# -------------------------------------------------------------------------
# 2. Regional Breakdown of 'er.in' Missingness by Referral Source
# -------------------------------------------------------------------------
plt.figure(figsize=(10, 6))

# Calculate missing percentage by Region and Referral Source
er_missing_by_region_referral = (
    df.groupby(["Region", "screen.in.str"], observed=False)["er.in_missing"]
    .mean()
    .reset_index()
)
er_missing_by_region_referral["er.in_missing"] *= 100

# Create bar plot
sns.barplot(
    data=er_missing_by_region_referral,
    x="Region",
    y="er.in_missing",
    hue="screen.in.str",
    palette="muted"
)

plt.title("ER Status Missingness by Region and Referral Source", fontweight="bold")
plt.xlabel("Region")
plt.ylabel("ER Status Missing (%)")
plt.xticks(rotation=30, ha="right")
plt.ylim(0, 105)
plt.legend(title="Referral Source", bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()

# Save figure
plt.savefig("./figures/bcfnr/er_missingness_by_region_and_referral.pdf", dpi=300, bbox_inches="tight")
plt.savefig("./figures/bcfnr/er_missingness_by_region_and_referral.png", dpi=300, bbox_inches="tight")
plt.close()

print("Exploratory ER missingness plots successfully generated and saved to './figures/bcfnr/'!")