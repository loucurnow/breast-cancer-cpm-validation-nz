import os
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# -------------------------------------------------------------------------
# ACCESSIBLE PALETTE (PINK, GREY, AND BLUE THEME)
# -------------------------------------------------------------------------
COLOR_TEXT = "#212121"        # Dark Charcoal (Labels & Titles)
COLOR_REF_LINE = "#757575"    # Neutral Medium Grey

# Custom qualitative palette combining distinct blues, pinks, and grey tones
# ensuring high contrast and accessibility for multiple regions
CUSTOM_REGION_PALETTE = [
    "#C2185B", # Deep Berry Pink
    "#455A64", # Slate Grey/Blue
    "#F48FB1", # Soft Light Pink
    "#00ACC1", # Cyan/Teal Blue
    "#AD1457", # Dark Plum Pink
    "#78909C", # Cool Grey
    "#303F9F"  # Indigo/Blue
]

# Set plotting style for publication-ready aesthetics with larger, matching fonts
sns.set_theme(style="whitegrid")
plt.rcParams.update(
    {
        "font.size": 12,          # Increased base font size (was 10)
        "axes.labelsize": 13,     # Axis labels (was 11)
        "axes.titlesize": 14,     # Subplot titles (was 12)
        "xtick.labelsize": 11,    # X-tick labels (was 9)
        "ytick.labelsize": 11,    # Y-tick labels (was 9)
        "figure.titlesize": 16,   # Main figure title (was 14)
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"], # Matches standard clean academic report fonts
        "text.color": COLOR_TEXT,
        "axes.labelcolor": COLOR_TEXT,
        "xtick.color": COLOR_TEXT,
        "ytick.color": COLOR_TEXT,
    }
)

# Ensure output directories exist
output_dir = Path("./figures/bcfnr")
output_dir.mkdir(parents=True, exist_ok=True)

sub_plots_dir = output_dir / "missingness_plots"
sub_plots_dir.mkdir(parents=True, exist_ok=True)

# 1. LOAD DATA
df = pd.read_pickle("./datasets/bcfnz/pickle/processed/unfiltered_with_nhs_vars.pickle")

target_var = "er.in"
var_label = "Oestrogen Receptor Status"

if target_var not in df.columns:
    raise ValueError(f"Target variable '{target_var}' not found in DataFrame columns!")

# 2. PREPARE DATA
# Create binary missingness indicator
df["_is_missing"] = df[target_var].isna() | (df[target_var] == "") | (df[target_var] == "Unknown")

# Group by Region and Diagnosis Year, computing proportion missing
missing_prop_joint = (
    df.groupby(["Region", "diag.year"])["_is_missing"]
    .mean()
    .reset_index()
)

# Clean up temporary column from main dataframe
df.drop(columns=["_is_missing"], inplace=True)

# 3. CREATE UNIFIED LINE CHART BY REGION
fig, ax = plt.subplots(figsize=(12, 6))

sns.lineplot(
    data=missing_prop_joint,
    x="diag.year",
    y="_is_missing",
    hue="Region",
    marker="o",
    linewidth=2.2,
    markersize=6,
    palette=CUSTOM_REGION_PALETTE,
    ax=ax
)

ax.set_title(f"Missingness Trends in {var_label} by Diagnosis Year Across Regions", fontweight="bold", pad=15)
ax.set_xlabel("Diagnosis Year")
ax.set_ylabel("Proportion Missing")
ax.set_ylim(0, 1.0)

# Move legend cleanly to the upper right outside the plot area
ax.legend(title="Region", loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=4, frameon=True)

plt.tight_layout()

# 4. SAVE OUTPUTS
filename_suffix = "er_missingness_lineplot_by_region"

# Save to missingness subfolder
sub_png_path = sub_plots_dir / f"{filename_suffix}.png"
fig.savefig(sub_png_path, dpi=300, bbox_inches="tight")

# Save to main bcfnr folder (PDF & PNG)
fig.savefig(output_dir / f"{filename_suffix}.pdf", dpi=300, bbox_inches="tight")
fig.savefig(output_dir / f"{filename_suffix}.png", dpi=300, bbox_inches="tight")
plt.close(fig)

print(f"Successfully generated and saved unified line chart for ER missingness with pink/grey/blue palette.")