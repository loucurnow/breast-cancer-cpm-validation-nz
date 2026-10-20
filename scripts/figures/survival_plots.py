import matplotlib.pyplot as plt
from lifelines import KaplanMeierFitter
import numpy as np
import pandas as pd
import seaborn as sns

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from utils.analysis_vars import bin_age, bin_nodes, bin_size, pos_neg_unknown, screening_str_vals

df = pd.read_pickle("./datasets/bcfnz/pickle/processed/predict_3_model_results.pickle")

# Set publication style aesthetics
sns.set_style("whitegrid")
plt.rcParams.update({
    "font.size": 8,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.titlesize": 11,
})

# Create binned columns
df["nodes_binned"] = df["nodes.in"].apply(bin_nodes)
df["age_binned"] = df["age.start.in"].apply(bin_age)
df["size_binned"] = df["size.in"].apply(bin_size)

df["screen.in.str"] = df["screen.in"].apply(screening_str_vals)
df["er.in.str"] = df["er.in"].apply(pos_neg_unknown)
df["pr.in.str"] = df["pr.in"].apply(pos_neg_unknown)
df["her2.in.str"] = df["her2.in"].apply(pos_neg_unknown)

# Define variables to plot: (Column Name, Display Title)
features_to_plot = [
    ("er.in.str", "ER Status"),
    ("pr.in.str", "PR Status"),
    ("screen.in.str", "Screening Referred"),
    ("her2.in.str", "HER2 Status"),
    ("grade.in", "Tumor Grade"),
    ("nodes_binned", "Positive Nodes"),
    ("age_binned", "Age Group"),
    ("size_binned", "Tumour Size Group"),
]

# 2. SET UP COMPACT 2x3 SUBPLOT GRID
fig, axes = plt.subplots(
    nrows=2, ncols=4, figsize=(12, 7), sharex=True, sharey=True
)
axes = axes.flatten()

kmf = KaplanMeierFitter()
palette = sns.color_palette("pastel")

for idx, (col, title) in enumerate(features_to_plot):
  ax = axes[idx]
  groups = df[col].dropna().unique()

  # Sort groups cleanly if possible
  try:
    groups = sorted(groups)
  except:
    pass

  for i, group in enumerate(groups):
    mask = df[col] == group
    sub_time = df.loc[mask, "surv.time.actual"]
    sub_event = df.loc[mask, "surv.actual"]

    if len(sub_time) > 0:
      kmf.fit(sub_time, event_observed=sub_event, label=str(group))
      kmf.plot_survival_function(
          ax=ax,
          ci_show=False,
          color=palette[i % len(palette)],
          linewidth=1.5,
      )

  ax.set_title(title, fontweight="bold")
  ax.set_ylim(0, 1.05)
  if idx >= 3:
    ax.set_xlabel("Time (Days)")
  else:
    ax.set_xlabel("")

  if idx % 3 == 0:
    ax.set_ylabel("Overall Survival Probability")
  else:
    ax.set_ylabel("")

  # Clean up legend
  ax.legend(loc="lower left", frameon=True, framealpha=0.8)

# Adjust layout spacing to avoid overlaps
plt.tight_layout()

# 3. SAVE AS HIGH-RES VECTOR PDF (Ideal for Overleaf)
plt.savefig("./figures/bcfnr/kaplan_meier_multipanel.pdf", dpi=300, bbox_inches="tight")
plt.savefig("./figures/bcfnr/kaplan_meier_multipanel.png", dpi=300, bbox_inches="tight")

print("Compact multi-panel KM plot successfully saved as PDF and PNG!")