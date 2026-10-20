import matplotlib.pyplot as plt
from lifelines import KaplanMeierFitter
import numpy as np
import pandas as pd
import seaborn as sns

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from utils.analysis_vars import bin_age, bin_nodes, bin_size, pos_neg_unknown, screening_str_vals

df = pd.read_pickle("./datasets/bcfnz/pickle/processed/predict_3_model_results.pickle")

# Correct event indicator: 1 for death event, 0 for censored/survived
df['death.event'] = 1 - df['surv.actual']

# -------------------------------------------------------------------------
# ACCESSIBLE PALETTE (PINK, GREY, AND BLUE THEME)
# -------------------------------------------------------------------------
COLOR_TEXT = "#212121"        # Dark Charcoal (Labels & Titles)
COLOR_REF_LINE = "#757575"    # Neutral Medium Grey

CUSTOM_PALETTE = [
    "#C2185B", # Deep Berry Pink
    "#1976D2", # Strong Blue
    "#F48FB1", # Soft Light Pink
    "#00ACC1", # Cyan/Teal Blue
    "#455A64", # Slate Grey/Blue
    "#303F9F"  # Indigo/Blue
]

# Set publication style aesthetics with larger font matching report standards
sns.set_theme(style="whitegrid")
plt.rcParams.update({
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8,
    "figure.titlesize": 14,
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "text.color": COLOR_TEXT,
    "axes.labelcolor": COLOR_TEXT,
    "xtick.color": COLOR_TEXT,
    "ytick.color": COLOR_TEXT,
})

# Create binned columns
df["nodes_binned"] = df["nodes.in"].apply(bin_nodes)
df["size_binned"] = df["size.in"].apply(bin_size)

# Explicitly order age categories chronologically
df["age_binned"] = df["age.start.in"].apply(bin_age)
df["age_binned"] = pd.Categorical(
    df["age_binned"], 
    categories=["$<45$", "45-60", "61-75", "$>$75"], 
    ordered=True
)

df["nodes_binned"] = pd.Categorical(
    df["nodes_binned"], 
    categories=["Unknown", "0", "1-5", "6-10", "11-15", "16+"], 
    ordered=True
)

df["size_binned"] = pd.Categorical(
    df["size_binned"], 
    categories=["Unknown", "$\\leq$10mm", "11-20mm", "21-40mm", "$>$40mm"], 
    ordered=True
)


df["screen.in.str"] = df["screen.in"].apply(screening_str_vals)
df["er.in.str"] = df["er.in"].apply(pos_neg_unknown)
df["pr.in.str"] = df["pr.in"].apply(pos_neg_unknown)
df["her2.in.str"] = df["her2.in"].apply(pos_neg_unknown)

# All 8 features to plot split into two sets of 4, including clean short names for individual files
feature_sets = [
    # Part 1 (First 4 plots)
    [
        ("er.in.str", "ER Status", "er_status"),
        ("pr.in.str", "PR Status", "pr_status"),
        ("her2.in.str", "HER2 Status", "her2_status"),
        ("screen.in.str", "Screening Referred", "screening_referred"),
    ],
    # Part 2 (Next 4 plots)
    [
        ("grade.in", "Tumor Grade", "tumor_grade"),
        ("nodes_binned", "Positive Nodes", "positive_nodes"),
        ("age_binned", "Age Group", "age_group"),
        ("size_binned", "Tumour Size Group", "tumour_size_group"),
    ]
]

output_dir = Path("./figures/bcfnr")
output_dir.mkdir(parents=True, exist_ok=True)

indiv_plots_dir = output_dir / "km_survival_plots"
indiv_plots_dir.mkdir(parents=True, exist_ok=True)

kmf = KaplanMeierFitter()

# Loop through to generate multi-panel figures AND individual standalone plots
for part_idx, features_to_plot in enumerate(feature_sets, start=1):
    fig, axes = plt.subplots(
        nrows=2, ncols=2, figsize=(10, 8), sharex=True, sharey=True
    )
    axes = axes.flatten()

    for idx, (col, title, short_name) in enumerate(features_to_plot):
        # Create a separate figure for the individual plot file
        fig_indiv, ax_indiv = plt.subplots(figsize=(6, 5))
        
        ax = axes[idx]
        
        # Handle sorting for categorical vs standard columns safely
        if isinstance(df[col].dtype, pd.CategoricalDtype):
            groups = [cat for cat in df[col].cat.categories if cat in df[col].dropna().unique()]
        else:
            groups = df[col].dropna().unique()
            try:
                groups = sorted(groups)
            except:
                pass

        for i, group in enumerate(groups):
            mask = df[col] == group
            sub_time = df.loc[mask, "surv.time.actual"]
            sub_event = df.loc[mask, "death.event"]

            if len(sub_time) > 0:
                color_val = CUSTOM_PALETTE[i % len(CUSTOM_PALETTE)]
                
                # Fit and plot on multi-panel subplot grid (Survival Probability)
                kmf.fit(sub_time, event_observed=sub_event, label=str(group))
                kmf.plot_survival_function(
                    ax=ax,
                    ci_show=False,
                    color=color_val,
                    linewidth=2,
                )
                
                # Fit and plot on individual standalone figure
                kmf.plot_survival_function(
                    ax=ax_indiv,
                    ci_show=False,
                    color=color_val,
                    linewidth=2,
                )

        # Style the multi-panel grid subplot
        ax.set_title(title, fontweight="bold")
        ax.set_ylim(0, 1.05)
        if idx >= 2:
            ax.set_xlabel("Time (Days)")
        else:
            ax.set_xlabel("")

        if idx % 2 == 0:
            ax.set_ylabel("Overall Survival Probability")
        else:
            ax.set_ylabel("")

        ax.legend(loc="lower left", frameon=True, framealpha=0.9)

        # Style and save the individual standalone plot
        ax_indiv.set_title(f"Kaplan-Meier Survival by {title}", fontweight="bold")
        ax_indiv.set_xlabel("Time (Days)")
        ax_indiv.set_ylabel("Overall Survival Probability")
        ax_indiv.set_ylim(0, 1.05)
        ax_indiv.legend(loc="lower left", frameon=True, framealpha=0.9)
        fig_indiv.tight_layout()
        
        indiv_filename = f"km_{short_name}"
        fig_indiv.savefig(indiv_plots_dir / f"{indiv_filename}.pdf", dpi=300, bbox_inches="tight")
        fig_indiv.savefig(indiv_plots_dir / f"{indiv_filename}.png", dpi=300, bbox_inches="tight")
        plt.close(fig_indiv)

    plt.tight_layout()

    # Save multi-panel composite figures
    filename_suffix = f"kaplan_meier_multipanel_part{part_idx}"
    fig.savefig(output_dir / f"{filename_suffix}.pdf", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / f"{filename_suffix}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

print("Successfully generated and saved correctly oriented survival probability plots!")