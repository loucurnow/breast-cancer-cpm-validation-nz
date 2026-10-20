import os
from pathlib import Path
import pandas as pd

model_cols = [
    "age.start.in",
    "screen.in",
    "size.in",
    "grade.in",
    "nodes.in",
    "er.in",
    "her2.in",
    "ki67.in",
    "pr.in",
    "generation.in",
    "horm.in",
    "traz.in",
    "bis.in",
    "radio.in",
    "heart.gy.in",
    "smoker.in",
]

dem_cols = [
    "unique_key",
    "diag.year",
    "ethnic",
    "menopause",
    "Region",
    "dod",
    "cod",
    "final_survival_sweep",
]

cohort_cols = [
    "days_to_mets",
    "cohort_valid_diagnosis",
    "cohort_female",
    "cohort_first_diagnosis",
    "cohort_dx_20_85",
    "cohort_no_neoadj",
    "cohort_no_mets_baseline",
    "cohort_no_dcis",
    "cohort_primary_surgery",
    "cohort_locoregional_complete",
    "cohort_tumour_details",
    "cohort_er_valid",
]

other_cols = [
    "brca_result",
    "ax_node_presence",
    "node_total_remove",
    "node_involved_count",
    "node_largest_deposit",
    "primary_surgery",
    "adj_rad",
    "adj_chemo",
    "adj_mab",
    "adj_hormone",
]

surv_model_cols = [
    "surv.time.actual",
    "days.to.censor",
    "days.to.death",
    "surv.actual",
    "treatments.given",
]

variable_metadata = {
    "age.start.in": {
        "Group": "Model Variables",
        "Description": "Patient age at diagnosis (years)",
        "Derivation Rule": "Direct assignment from Age At Diagnosis",
    },
    "screen.in": {
        "Group": "Model Variables",
        "Description": "Screening detection status",
        "Derivation Rule": (
            "1 if ReferralSource is 'BreastScreen Aotearoa' or 'Screen detected"
            " - non BSA'; 0 if A&E/Emergency/GP symptomatic; 9 otherwise."
        ),
    },
    "size.in": {
        "Group": "Model Variables",
        "Description": "Maximum invasive tumour size (mm)",
        "Derivation Rule": "Max InvasiveTumourSize per case",
    },
    "grade.in": {
        "Group": "Model Variables",
        "Description": "Maximum histological tumour grade",
        "Derivation Rule": "Max HistologicalInvasiveCancerGrade per case",
    },
    "nodes.in": {
        "Group": "Model Variables",
        "Description": "Number of positive lymph nodes",
        "Derivation Rule": "Direct mapping fromNumberOfNodesInvolvedByTumour.",
    },
    "er.in": {
        "Group": "Model Variables",
        "Description": "Oestrogen Receptor status",
        "Derivation Rule": (
            "Mapped from HP Oestrogen Result (Positive = 1, Negative = 0)."
        ),
    },
    "pr.in": {
        "Group": "Model Variables",
        "Description": "Progesterone Receptor status",
        "Derivation Rule": (
            "Mapped from HP Progesterone Result (Positive = 1, Negative = 0)."
        ),
    },
    "her2.in": {
        "Group": "Model Variables",
        "Description": "HER2 receptor status",
        "Derivation Rule": (
            "Combined IHC and FISH priority mapping (1 = positive, 0 ="
            " negative, 9 = unknown)."
        ),
    },
    "ki67.in": {
        "Group": "Model Variables",
        "Description": "Ki-67 proliferation index status",
        "Derivation Rule": (
            "Assigned 9 (unknown) due to low availability in baseline dataset."
        ),
    },
    "generation.in": {
        "Group": "Model Variables",
        "Description": "Chemotherapy generation level",
        "Derivation Rule": (
            "Derived from chemo_type string matching: 3 if anthracycline and"
            " taxane present; else 0."
        ),
    },
    "horm.in": {
        "Group": "Model Variables",
        "Description": "Adjuvant hormone therapy indicator",
        "Derivation Rule": "1 if AdjuvantHormoneTherapy = 'Yes', 0 otherwise",
    },
    "traz.in": {
        "Group": "Model Variables",
        "Description": "Adjuvant Trastuzumab therapy indicator",
        "Derivation Rule": "1 if any HormoneTherapy = Trastuzumab, 0 otherwise",
    },
    "bis.in": {
        "Group": "Model Variables",
        "Description": "Bisphosphonate therapy indicator",
        "Derivation Rule": "Hardcoded default assignment to 0.",
    },
    "radio.in": {
        "Group": "Model Variables",
        "Description": "Adjuvant radiotherapy indicator",
        "Derivation Rule": "1 if AdjuvantRadiationTherapy = 'Yes', 0 otherwise",
    },
    "heart.gy.in": {
        "Group": "Model Variables",
        "Description": "Total radiation dose to the heart (Gray)",
        "Derivation Rule": "Sum of Total Dose records where Timing = Adjuvant.",
    },
    "smoker.in": {
        "Group": "Model Variables",
        "Description": "Smoking status indicator",
        "Derivation Rule": "1 if SmokingStatus = 'Current' or 'Non-smoker exposed to tobacco smoke', 0 otherwise.",
    },
    "diag.year": {
        "Group": "Demographics",
        "Description": "Year of tissue diagnosis",
        "Derivation Rule": "Extracted year component from DateOfTissueDiagnosis.",
    },
    "ethnic": {
        "Group": "Demographics",
        "Description": "Patient ethnic group",
        "Derivation Rule": "EthnicityLevel1 from demographic records. Maori, Pacific, Asian, European mapped directly. Remaining ethnicities grouped as 'Other'.",
    },
    "menopause": {
        "Group": "Demographics",
        "Description": "Menopausal status at diagnosis",
        "Derivation Rule": "Direct extraction from demographic records.",
    },
    "Region": {
        "Group": "Demographics",
        "Description": "Geographic treatment region",
        "Derivation Rule": "Direct extraction from source record sets.",
    },
    "dod": {
        "Group": "Demographics",
        "Description": "Date of death",
        "Derivation Rule": "Direct extraction from Demographics data.",
    },
    "cod": {
        "Group": "Demographics",
        "Description": "Cause of death",
        "Derivation Rule": "Direct extraction from Demographics data.",
    },
    "final_survival_sweep": {
        "Group": "Demographics",
        "Description": "Final follow-up or censoring date",
        "Derivation Rule": "DateOfDeath if exists, otherwise LastFollowupDate.",
    },
    "days.to.censor": {
        "Group": "Survival Outcomes",
        "Description": "Days from diagnosis to censoring sweep",
        "Derivation Rule": "Difference between final sweep and diagnosis date.",
    },
    "days.to.death": {
        "Group": "Survival Outcomes",
        "Description": "Days from diagnosis to death",
        "Derivation Rule": "Difference between death date and diagnosis date.",
    },
    "surv.time.actual": {
        "Group": "Survival Outcomes",
        "Description": "Actual follow-up time (days)",
        "Derivation Rule": "Minimum out of days.to.censor and days.to.death.",
    },
    "surv.actual": {
        "Group": "Survival Outcomes",
        "Description": "Survival status indicator",
        "Derivation Rule": "0 if DateOfDeath is available, 1 otherwise.",
    },
    "treatments.given": {
        "Group": "Survival Outcomes",
        "Description": "Concatenated systemic and local treatment string",
        "Derivation Rule": "Letter codes appended based on binary indicators for adjuvant hormone, trastuzumab, bisphosphonate, radiotherapy, chemotherapy.",
    },
    "days_to_mets": {
        "Group": "Survival Outcomes",
        "Description": "Days from diagnosis to first metastasis",
        "Derivation Rule": "Days between DateOfTissueDiagnosis and earliest DateOfMetastasis.",
    },
}


def escape_latex(val):
  return str(val).replace("_", "\\_")


def generate_data_dictionary_table(columns_list, title, filename):
  rows = []
  for col in columns_list:
    meta = variable_metadata.get(col, {})
    rows.append({
        "Variable": escape_latex(f"\\texttt{{{col}}}"),
        "Description": escape_latex(
            meta.get("Description", "Field description pending")
        ),
        "Derivation Rule": escape_latex(
            meta.get("Derivation Rule", "Direct extraction from raw data.")
        )
    })

  df_dict = pd.DataFrame(rows)

  output_path = f"tables/tex/{filename}_dictionary.tex"
  os.makedirs(os.path.dirname(output_path), exist_ok=True)

  # Enable longtable and set column widths appropriate for landscape
  latex_code = df_dict.to_latex(
      index=False,
      escape=False,
      na_rep="-",
      longtable=True,
      column_format="p{0.3\\textwidth} p{0.35\\textwidth} p{0.45\\textwidth}",
  )

  # Wrap the longtable code in a landscape environment
  landscape_latex = f"\\begin{{landscape}}\n{latex_code}\n\\end{{landscape}}"

  with open(output_path, "w", encoding="utf-8") as f:
    f.write(landscape_latex)
  print(f"Landscape multi-page data dictionary generated: {output_path}")


if __name__ == "__main__":
  generate_data_dictionary_table(
      model_cols + dem_cols + surv_model_cols,
      title="NHS Predict Model and Demographic Variables",
      filename="transformed_data",
  )