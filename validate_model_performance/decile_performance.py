import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from lifelines import KaplanMeierFitter
from lifelines.utils import concordance_index
from sksurv.metrics import brier_score

# -------------------------------------------------------------------------
# ACCESSIBLE PALETTE (BREAST CANCER PUBLICATION THEME)
# -------------------------------------------------------------------------
COLOR_5YR = "#C2185B"       # Deep Berry Pink (High Contrast / Accessible)
COLOR_10YR = "#880E4F"      # Deep Plum Pink (High Contrast / Accessible)
COLOR_REF_LINE = "#757575"  # Neutral Medium Grey (Reference / Baselines)
COLOR_TEXT = "#212121"      # Dark Charcoal (Axes & Labels)

# -------------------------------------------------------------------------
# 1. LOAD & PREPARE DATA
# -------------------------------------------------------------------------
df = pd.read_pickle("./datasets/bcfnz/pickle/processed/predict_3_model_results.pickle")

# Exclude rows with negative survival times or missing prediction probabilities
df = df[(df["surv.time.actual"] >= 0) & df["pred_all_yr5"].notna() & df["pred_all_yr10"].notna()].copy()

# Compute binary death event indicator (1 = death event, 0 = censored)
df["death.event"] = (1 - df["surv.actual"]).astype(bool)

# Milestone Cohort Filtering based on follow-up availability (5yr: <=2018, 10yr: <=2013)
FINAL_FOLLOWUP_YEAR = 2023
if "diag.year" in df.columns:
    df_5yr = df[df["diag.year"] <= FINAL_FOLLOWUP_YEAR - 5].copy()
    df_10yr = df[df["diag.year"] <= FINAL_FOLLOWUP_YEAR - 10].copy()
else:
    df_5yr = df.copy()
    df_10yr = df.copy()

# -------------------------------------------------------------------------
# 2. DISCRIMINATION (Harrell's C-Index)
# -------------------------------------------------------------------------
c_index_5yr = concordance_index(
    df_5yr["surv.time.actual"], df_5yr["pred_all_yr5"], df_5yr["death.event"]
)
c_index_10yr = concordance_index(
    df_10yr["surv.time.actual"], df_10yr["pred_all_yr10"], df_10yr["death.event"]
)
c_index_5yr = 1 - round(c_index_5yr, 3)
c_index_10yr = 1 - round(c_index_10yr, 3)
# -------------------------------------------------------------------------
# 3. OVERALL ACCURACY (Time-Dependent IPCW Brier Score)
# -------------------------------------------------------------------------
durations = df["surv.time.actual"].values
events = df["death.event"].values

y_structured = np.array(
    list(zip(events, durations)), dtype=[("Status", "?"), ("Time", "<f8")]
)

eval_times = np.array([5 * 365.25, 10 * 365.25])

surv_yr5 = 1.0 - df["pred_all_yr5"].values
surv_yr10 = 1.0 - df["pred_all_yr10"].values

pred_matrix = np.column_stack([surv_yr5, surv_yr10])
pred_matrix = np.clip(pred_matrix, 0.001, 0.999)

_, brier_scores = brier_score(y_structured, y_structured, pred_matrix, eval_times)

# -------------------------------------------------------------------------
# 4. MODERATE CALIBRATION (Decile Risk Grouping & KM Analysis)
# -------------------------------------------------------------------------
def compute_decile_calibration(cohort, pred_col, target_days):
    data = cohort.copy()
    data["decile"] = pd.qcut(data[pred_col], q=10, labels=False, duplicates="drop")
    
    decile_summary = []
    kmf = KaplanMeierFitter()
    
    for decile_idx, group in data.groupby("decile"):
        mean_pred_surv = (1.0 - group[pred_col].mean()) * 100
        kmf.fit(durations=group["surv.time.actual"], event_observed=group["death.event"])
        valid_rows = kmf.survival_function_[kmf.survival_function_.index <= target_days]
        
        obs_surv = valid_rows.iloc[-1, 0] * 100 if len(valid_rows) > 0 else 100.0
        
        decile_summary.append({
            "decile": decile_idx + 1,
            "pred_surv": mean_pred_surv,
            "obs_surv": obs_surv,
            "n": len(group)
        })
        
    return pd.DataFrame(decile_summary)

deciles_5yr = compute_decile_calibration(df_5yr, "pred_all_yr5", 5 * 365.25)
deciles_10yr = compute_decile_calibration(df_10yr, "pred_all_yr10", 10 * 365.25)

# -------------------------------------------------------------------------
# 5. VISUALIZATION: UNIFIED ACCESSIBLE 2x2 MULTI-PANEL FIGURE
# -------------------------------------------------------------------------
sns.set_theme(style="whitegrid")
fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(12, 10))

time_points = [5, 10]

# --- Plot A: Discrimination (C-index) ---
axes[0, 0].plot(
    time_points, [c_index_5yr, c_index_10yr],
    marker="o", color=COLOR_5YR, lw=2.5, markersize=8, label="PREDICT v3"
)
axes[0, 0].axhline(y=0.5, color=COLOR_REF_LINE, linestyle="--", lw=1.5, label="Random Chance (0.50)")
axes[0, 0].set_title("A. Model Discrimination (Harrell's C-index)", fontweight="bold", color=COLOR_TEXT)
axes[0, 0].set_xlabel("Time Horizon (Years)", color=COLOR_TEXT)
axes[0, 0].set_ylabel("C-index", color=COLOR_TEXT)
axes[0, 0].set_xticks([5, 10])
axes[0, 0].set_ylim(0.5, 1.0)
axes[0, 0].legend(loc="upper left")

# --- Plot B: Overall Accuracy (IPCW Brier Score) ---
axes[0, 1].plot(
    time_points, brier_scores,
    marker="s", color=COLOR_5YR, lw=2.5, markersize=8, label="IPCW Brier Score"
)
axes[0, 1].axhline(y=0.25, color=COLOR_REF_LINE, linestyle="--", lw=1.5, label="Uninformative Model (0.25)")
axes[0, 1].set_title("B. Overall Prediction Error (Brier Score)", fontweight="bold", color=COLOR_TEXT)
axes[0, 1].set_xlabel("Time Horizon (Years)", color=COLOR_TEXT)
axes[0, 1].set_ylabel("Brier Score", color=COLOR_TEXT)
axes[0, 1].set_xticks([5, 10])
axes[0, 1].set_ylim(0, 0.3)
axes[0, 1].legend(loc="upper left")

# --- Plot C: 5-Year Decile Calibration ---
axes[1, 0].plot([50, 100], [50, 100], color=COLOR_REF_LINE, linestyle="--", lw=1.5, label="Perfect Calibration")
axes[1, 0].scatter(
    deciles_5yr["pred_surv"], deciles_5yr["obs_surv"],
    color=COLOR_5YR, s=60, zorder=3, label="5-Year Deciles"
)
axes[1, 0].plot(
    deciles_5yr["pred_surv"], deciles_5yr["obs_surv"],
    color=COLOR_5YR, lw=2, alpha=0.85
)
axes[1, 0].set_title("C. 5-Year Decile Calibration", fontweight="bold", color=COLOR_TEXT)
axes[1, 0].set_xlabel("Mean Predicted Overall Survival (%)", color=COLOR_TEXT)
axes[1, 0].set_ylabel("Kaplan-Meier Observed Survival (%)", color=COLOR_TEXT)
axes[1, 0].set_xlim(50, 100)
axes[1, 0].set_ylim(50, 100)
axes[1, 0].legend(loc="upper left")

# --- Plot D: 10-Year Decile Calibration ---
axes[1, 1].plot([30, 100], [30, 100], color=COLOR_REF_LINE, linestyle="--", lw=1.5, label="Perfect Calibration")
axes[1, 1].scatter(
    deciles_10yr["pred_surv"], deciles_10yr["obs_surv"],
    color=COLOR_10YR, s=60, zorder=3, label="10-Year Deciles"
)
axes[1, 1].plot(
    deciles_10yr["pred_surv"], deciles_10yr["obs_surv"],
    color=COLOR_10YR, lw=2, alpha=0.85
)
axes[1, 1].set_title("D. 10-Year Decile Calibration", fontweight="bold", color=COLOR_TEXT)
axes[1, 1].set_xlabel("Mean Predicted Overall Survival (%)", color=COLOR_TEXT)
axes[1, 1].set_ylabel("Kaplan-Meier Observed Survival (%)", color=COLOR_TEXT)
axes[1, 1].set_xlim(30, 100)
axes[1, 1].set_ylim(30, 100)
axes[1, 1].legend(loc="upper left")

plt.tight_layout()
plt.savefig("./figures/bcfnr/model_performance_milestones.pdf", dpi=300, bbox_inches="tight")
plt.savefig("./figures/bcfnr/model_performance_milestones.png", dpi=300, bbox_inches="tight")
plt.close()

print("Publication figure generated with accessible pink/grey color scheme!")