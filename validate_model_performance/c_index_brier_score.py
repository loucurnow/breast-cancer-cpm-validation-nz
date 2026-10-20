import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines.utils import concordance_index
# ssurv handles time-dependent brier scores cleanly
from sksurv.metrics import brier_score
import seaborn as sns

# 1. LOAD YOUR DATA & PREDICTED PROBABILITIES
df = pd.read_pickle("./datasets/bcfnz/pickle/processed/predict_3_model_results.pickle")

# exclude rows with negative survival times (22 found) or missing predictions
df = df[(df["surv.time.actual"] >= 0) & df["pred_all_yr5"].notna() & df["pred_all_yr10"].notna()]

nan_rows = df[df["pred_all_yr5"].isna()]
print(
    nan_rows[
        [
            "diag.year",
            "age.start.in",
            "size.in",
            "grade.in",
            "er.in",
            "nodes.in",
        ]
    ]
)

# Ensure clean arrays for time, event, and predicted risks
durations = df["surv.time.actual"].values

df['death.event'] = 1 - df['surv.actual']
events = df["death.event"].astype(bool).values

# Format structured array required by sksurv (Event indicator, Time)
# Structured array required by sksurv for Brier score
y_structured = np.array(
    list(zip(events, durations)), dtype=[("Status", "?"), ("Time", "<f8")]
)

# 2. Compute Discrimination (Harrell's C-index)
# Using 5-year predicted risk score (1 - survival probability)
risk_scores_5yr = 1.0 - df["pred_all_yr5"].values
c_index_5yr = concordance_index(durations, risk_scores_5yr, events)

risk_scores_10yr = 1.0 - df["pred_all_yr10"].values
c_index_10yr = concordance_index(durations, risk_scores_10yr, events)

print(f"C-index (based on 5-yr risk): {c_index_5yr:.3f}")
print(f"C-index (based on 10-yr risk): {c_index_10yr:.3f}")

# 3. Compute Real Time-Dependent Brier Scores at exactly 5 and 10 years
eval_times = np.array([5 * 365.25, 10 * 365.25])
# Convert probability of death to survival probability
surv_yr5 = 1.0 - df["pred_all_yr5"].values
surv_yr10 = 1.0 - df["pred_all_yr10"].values

# Build the prediction matrix using survival probabilities
eval_times = np.array([5 * 365.25, 10 * 365.25])
pred_matrix = np.column_stack([surv_yr5, surv_yr10])
pred_matrix = np.clip(pred_matrix, 0.001, 0.999)

_, brier_scores = brier_score(
    y_structured, y_structured, pred_matrix, eval_times
)

print(f"5-year Brier Score: {brier_scores[0]:.3f}")
print(f"10-year Brier Score: {brier_scores[1]:.3f}")

# --- 4. PLOT 2-POINT MILESTONE PERFORMANCE ---
sns.set_theme(style="whitegrid")
fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(11, 4.5))

time_points = [5, 10]

# Plot A: Discrimination at 5 and 10 years
axes[0].plot(
    time_points,
    [c_index_5yr, c_index_10yr],
    marker="o",
    color="b",
    lw=2,
    markersize=8,
    label="PREDICT Model",
)
axes[0].axhline(
    y=0.5, color="gray", linestyle="--", label="Random Discrimination"
)
axes[0].set_title(
    "Model Discrimination (Harrell's C-index)", fontweight="bold"
)
axes[0].set_xlabel("Time Horizon (Years)")
axes[0].set_ylabel("C-index")
axes[0].set_xticks([5, 10])
axes[0].set_ylim(0.5, 1.0)
axes[0].legend(loc="lower left")

# Plot B: Brier Score at 5 and 10 years
axes[1].plot(
    time_points,
    brier_scores,
    marker="s",
    color="r",
    lw=2,
    markersize=8,
    label="Time-dependent Brier Score",
)
axes[1].axhline(
    y=0.25, color="gray", linestyle="--", label="Uninformative Classifier"
)
axes[1].set_title("Overall Accuracy (Brier Score)", fontweight="bold")
axes[1].set_xlabel("Time Horizon (Years)")
axes[1].set_ylabel("Brier Score")
axes[1].set_xticks([5, 10])
axes[1].set_ylim(0, 0.3)
axes[1].legend(loc="upper right")

plt.tight_layout()
plt.savefig(
    "./figures/bcfnr/model_performance_milestones.pdf",
    dpi=300,
    bbox_inches="tight",
)
plt.savefig(
    "./figures/bcfnr/model_performance_milestones.png",
    dpi=300,
    bbox_inches="tight",
)
plt.close()

print("Milestone performance plots successfully generated!")


