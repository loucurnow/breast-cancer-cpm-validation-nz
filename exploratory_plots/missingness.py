import os
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from utils.analysis_vars import bin_age, bin_diag_year, bin_nodes, bin_size, screening_str_vals, pos_neg_unknown

# -------------------------------------------------------------------------
# ACCESSIBLE PALETTE (LIGHT PINK, DARK PINK, GREY THEME)
# -------------------------------------------------------------------------
COLOR_BAR_LIGHT = "#F48FB1"   # Soft Light Pink (Accessible pastel shade)
COLOR_BAR_DARK = "#AD1457"    # Deep Berry Dark Pink (High contrast accent)
COLOR_REF_LINE = "#757575"    # Slate Grey (Borders & Neutrals)
COLOR_TEXT = "#212121"        # Dark Charcoal (Labels & Titles)

# Set plotting style for publication-ready aesthetics
sns.set_theme(style="whitegrid")
plt.rcParams.update(
    {
        "font.size": 10,
        "axes.labelsize": 11,
        "axes.titlesize": 12,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "figure.titlesize": 14,
        "text.color": COLOR_TEXT,
        "axes.labelcolor": COLOR_TEXT,
        "xtick.color": COLOR_TEXT,
        "ytick.color": COLOR_TEXT,
    }
)

# Ensure output directories exist (main folder + individual missingness plots subfolder)
output_dir = Path("./figures/bcfnr")
output_dir.mkdir(parents=True, exist_ok=True)

sub_plots_dir = output_dir / "missingness_plots"
sub_plots_dir.mkdir(parents=True, exist_ok=True)

# 1. LOAD YOUR DATA
df = pd.read_pickle("./datasets/bcfnz/pickle/processed/unfiltered_with_nhs_vars.pickle")

df["ethnicity_recoded"] = df["ethnic"].apply(lambda x: "Māori" if x == "Maori" else "Other" if x not in ["European", "Māori", "Pacific Peoples", "Asian"] else x)
df["screen.in.str"] = df["screen.in"].apply(screening_str_vals)

cols = list(df.columns)
print(cols)

# Define variables of interest to check for missingness
missing_vars = [
    "er.in",
    "size.in",
    "grade.in",
    "nodes.in",
]

# Map friendly display names for plot titles and labels
var_labels = {
    "er.in": "Oestrogen Receptor Status",
    "size.in": "Invasive Tumour Size",
    "grade.in": "Tumour Grade",
    "nodes.in": "Positive Node Count",
}

# Define stratifying factors
stratifying_factors = [
    "diag.year",
    "ethnicity_recoded",
    "Region",
    "screen.in.str"
]

factor_labels = {
    "diag.year": "Diagnosis Year",
    "ethnicity_recoded": "Ethnicity",
    "Region": "Diagnosis Region",
    "screen.in.str": "Referral Source"
}

# 2. GENERATE MISSINGNESS PLOTS FOR EACH STRATIFYING FACTOR
for factor in stratifying_factors:
    if factor not in df.columns:
        print(f"Warning: Stratifying factor '{factor}' not found in dataframe. Skipping...")
        continue

    # --- PART A: Create and save the multi-panel overview figure ---
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharey=True)
    axes = axes.flatten()

    for idx, var in enumerate(missing_vars):
        if var not in df.columns:
            print(f"Warning: Variable '{var}' not found in dataframe. Skipping...")
            continue

        # Create a binary missingness indicator (1 if missing, 0 if present)
        df["_is_missing"] = df[var].isna() | (df[var] == "") | (df[var] == "Unknown")

        # Group by the stratifying factor and calculate the missingness proportion
        missing_prop = df.groupby(factor)["_is_missing"].mean().reset_index()

        palette_colors = [
            COLOR_BAR_LIGHT if i % 2 == 0 else COLOR_BAR_DARK 
            for i in range(len(missing_prop))
        ]

        # --- ALSO: Save each individual variable plot separately as a single PNG file ---
        fig_single, ax_single = plt.subplots(figsize=(7, 5))
        sns.barplot(
            data=missing_prop,
            x=factor,
            y="_is_missing",
            ax=ax_single,
            palette=palette_colors,
            edgecolor="black",
        )
        ax_single.set_title(f"Missingness in {var_labels.get(var, var)} by {factor_labels.get(factor, factor)}", fontweight="bold")
        ax_single.set_xlabel(factor_labels.get(factor, factor))
        ax_single.set_ylabel("Proportion Missing")
        ax_single.set_ylim(0, 1.0)
        plt.setp(ax_single.get_xticklabels(), rotation=45, ha="right")
        fig_single.tight_layout()

        single_plot_path = sub_plots_dir / f"missingness_{var}_by_{factor}.png"
        fig_single.savefig(single_plot_path, dpi=300, bbox_inches="tight")
        plt.close(fig_single)

        # --- Populate the main multi-panel figure axes ---
        ax = axes[idx]
        sns.barplot(
            data=missing_prop,
            x=factor,
            y="_is_missing",
            ax=ax,
            palette=palette_colors,
            edgecolor="black",
        )

        ax.set_title(f"Missingness in {var_labels.get(var, var)}", fontweight="bold")
        ax.set_xlabel(factor_labels.get(factor, factor))
        ax.set_ylabel("Proportion Missing")
        ax.set_ylim(0, 1.0)

        # Rotate x-tick labels for readability
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    # Clean up temporary column
    df.drop(columns=["_is_missing"], inplace=True)

    plt.suptitle(
        f"Pattern of Missing Data Stratified by {factor_labels.get(factor, factor)}",
        fontweight="bold",
        y=1.02,
    )
    plt.tight_layout()

    # Save multi-panel outputs in requested formats
    pdf_path = output_dir / f"missingness_by_{factor}.pdf"
    png_path = output_dir / f"missingness_by_{factor}.png"

    plt.savefig(pdf_path, dpi=300, bbox_inches="tight")
    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Successfully generated multi-panel and individual plots for stratifier: {factor}")