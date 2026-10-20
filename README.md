# Breast Cancer PREDICT Model Validation (New Zealand)

This repository contains a research pipeline for preparing New Zealand breast
cancer registry data, applying the PREDICT 3.1 model, and assessing model
performance. It also includes code for reproducing tidy tables, comparing the
Python transformations with reference R data, and producing descriptive and
survival analyses.

The data are sourced from **Te Rehita Mate Utaetae - Breast Cancer Foundation
Register NZ**. The code was originally written by **Louie Curnow**, building
upon R code by **Matthew Strother**. This repository contributes toward a Part IV Research Project undertaken by Louie Curnow the **University of Auckland**.

The main end-to-end path is:

```text
approved source Excel workbooks
  -> preprocessing/reproduce_strother_tables.py
  -> preprocessing/preprocessing_final.py
  -> predict_nhs/predict_v3_batch.py
  -> validate_model_performance/ and scripts/figures/
```

Run commands from the repository root unless stated otherwise. Several scripts
use paths relative to the current working directory.

## Important data and privacy note

The clinical source data are not included in this repository and should be
handled only in an approved, access-controlled environment. The pipeline
expects private workbooks under `datasets/bcfnz/excel/` and writes derived
patient-level data under `datasets/bcfnz/pickle/processed/`. Do not commit,
publish, or share source workbooks or generated patient-level files.

The data paths are ignored by Git. Obtain the source files and any R reference
datasets through the project’s approved data-access process; do not assume a
fresh clone contains them.

## Requirements and environment

- Python 3 and the packages used by the selected scripts. The repository does
  not currently provide a root `requirements.txt` or Python lock file.
- For preprocessing, the main Python dependencies include `pandas`, `numpy`,
  and `openpyxl`. The optional R-data comparison helpers use `pyreadr`.
- The batch prediction bridge additionally requires R, `rpy2`, and the
  `predictv30r` R package included at `R/predict-v30-r/`.
- Performance and plotting scripts use packages including `lifelines`,
  `scikit-survival`, `scipy`, `matplotlib`, `seaborn`, and `missingno`.
- `R/renv.lock` records the R project library (R 4.3.3 in the lockfile).

Install only the dependencies needed for the workflow you plan to run. The
batch predictor requires `rpy2` to work with the same R installation and
library in which `predictv30r` is installed.

Restore the R project library and install the local PREDICT package:

```sh
cd R
Rscript -e 'renv::restore()'
cd ..
R CMD INSTALL R/predict-v30-r
```

Ensure the R installation is discoverable by `rpy2` in the Python environment
before running the batch prediction script.

## End-to-end workflow

### 1. Prepare the source data

Place the authorized Excel source files at the paths below. These are the
workbooks referenced by the table-building and NHS predictor-variable code:

```text
datasets/bcfnz/excel/surgery_primary.xlsx
datasets/bcfnz/excel/demographic.xlsx
datasets/bcfnz/excel/workup.xlsx
datasets/bcfnz/excel/biomarkers.xlsx
datasets/bcfnz/excel/followup.xlsx
datasets/bcfnz/excel/lesions.xlsx
datasets/bcfnz/excel/histopathology.xlsx
datasets/bcfnz/excel/metastatic_disease.xlsx
datasets/bcfnz/excel/therapy_chemo.xlsx
datasets/bcfnz/excel/therapy_biological.xlsx
datasets/bcfnz/excel/therapy_radio.xlsx
```

Some older or optional scripts refer to additional workbooks (for example,
`therapy_hormone.xlsx`). Check the input paths in the particular script before
running it.

### 2. Build the merged tidy registry table

Run the table transformations once to produce the merged table used by the
main preprocessing step:

```sh
python -c "from preprocessing.reproduce_strother_tables import generate_strother_files; generate_strother_files()"
```

The output is written to:

```text
datasets/bcfnz/pickle/processed/strother/
  merged_breast_tables.pickle
  merged_breast_tables.csv
  tidy_*.pickle
  tidy_*.csv
```

`generate_strother_files()` transforms the supported workbooks, combines their
tidy tables, and adds follow-up and locoregional surgery-completeness variables.
If the merged output already exists, the helper prompts before overwriting it.
The module’s direct script entry point also attempts to compare the generated
table with a reference R `.Rda` file; use the function command above if those
optional reference files are unavailable.

### 3. Add model variables and select the analysis cohort

```sh
python -m preprocessing.preprocessing_final
```

This step reads `merged_breast_tables.pickle`, derives the PREDICT input
variables, applies the cohort inclusion criteria, and writes:

```text
datasets/bcfnz/pickle/processed/
  unfiltered_with_nhs_vars.pickle
  filtered_cohort.pickle
  filtered_cohort.csv
  model_input.pickle
  model_input.csv
```

`model_input` is the prediction-ready subset, retaining the PREDICT inputs,
selected demographic and survival fields, and the treatment combination used
to select model output. The cohort filter currently includes recorded
diagnosis, female sex, first diagnosis, age 20–85, no neoadjuvant therapy, no
metastasis at baseline, non-DCIS diagnosis, primary surgery, complete
locoregional therapy, complete tumour details, valid ER, and exclusion of
`nodes.in == 999`.

**Portability caveat:** cohort-flowchart plotting currently uses a
machine-specific absolute output path in
`preprocessing/cohort_selection.py`. If running on another machine and that
path is unavailable, update the plot destination or invoke the cohort filter
with plotting disabled before running this step.

### 4. Run PREDICT 3.1 for the cohort

After setting up R and installing `predictv30r` as described above:

```sh
python predict_nhs/predict_v3_batch.py
```

The script reads `model_input.pickle`, sources
`predict_nhs/predict_wrapper.R`, calls the R package’s `benefits31` model for
each row, and writes:

```text
datasets/bcfnz/pickle/processed/
  predict_3_model_results.pickle
  predict_3_model_results.csv
```

The prediction columns contain all-cause, breast-cancer, and other-cause
predicted cumulative outcomes at years 5, 10, and 15. The single-row example
`predict_nhs/predict_v3_single_row.py` is a separate illustrative call; it is
not a prerequisite for batch prediction.

### 5. Evaluate and visualize predictions

These scripts consume `predict_3_model_results.pickle`; run them after the
batch prediction step:

| Script | Purpose |
| --- | --- |
| `validate_model_performance/c_index_brier_score.py` | Computes 5- and 10-year C-index and time-dependent Brier scores and saves milestone performance plots. |
| `validate_model_performance/actual_vs_predicted_survival.py` | Compares predicted and Kaplan–Meier observed survival overall and across selected subgroups. |
| `validate_model_performance/decile_performance.py` | Performs decile-based calibration/performance analysis. |
| `scripts/figures/survival_plots.py` | Generates Kaplan–Meier and survival visualizations. |
| `scripts/figures/exploratory_visualisations.py` | Generates distributions and subgroup descriptive plots. |

The missingness scripts instead consume the pre-cohort
`unfiltered_with_nhs_vars.pickle`:

```sh
python scripts/figures/assess_missingness.py
```

Other exploratory missingness scripts are in `exploratory_plots/`. Outputs are
generally written under `figures/` or the paths declared in each script.
Inspect each script before running it: some are analysis notebooks-in-script
form and execute their analysis at import/run time rather than exposing a
command-line interface.

## Repository guide

| Path | Contents |
| --- | --- |
| `preprocessing/reproduce_strother_tables.py` | Transforms source workbooks and assembles `merged_breast_tables`. |
| `preprocessing/preprocessing_final.py` | Primary cohort and PREDICT-input preparation entry point. |
| `preprocessing/cohort_selection.py` | Inclusion/exclusion flags and final cohort filter. |
| `preprocessing/derived_vars.py` | Derived clinical variables, follow-up, and PREDICT input mappings. |
| `preprocessing/surgical_completeness.py`, `preprocessing/reproduce_strother_surgical_completeness.py` | Surgery-completeness logic used in preprocessing. |
| `predict_nhs/` | Python-to-R batch and single-row prediction examples plus the R wrapper. |
| `R/predict-v30-r/` | R package exposing PREDICT versions including `benefits31`. |
| `R/` | R analyses, project configuration, and `renv` dependency lockfile. |
| `validate_model_performance/` | Model discrimination, calibration, and survival validation analyses. |
| `scripts/` | Data comparison, surgery pivoting, summary tables, and visualizations. |
| `utils/` | Shared analysis variables, plotting, summaries, and comparison helpers. |
| `datasets/` | Source and derived data location; most project data are excluded from Git. |
| `figures/`, `tables/` | Generated figures and LaTeX tables. |

Top-level scripts such as `exploratory.py`, `missing_data.py`,
`cox_regression.py`, `random_forest.py`, `svm.py`, and `ml_pipeline.py` are
exploratory or legacy analyses rather than steps in the main PREDICT validation
sequence. Check their input assumptions before use.

## Reproducing reference transformations

`scripts/compare_dataframes.py` compares a Python pickle with an R `.Rda`
dataset. For example:

```sh
python scripts/compare_dataframes.py \
  --py datasets/bcfnz/pickle/processed/surgery_primary_full.pickle \
  --r datasets/bcfnz/strother/tidy_surgery_new_strother.Rda
```

The command-line arguments must point to files available in the local
environment. Comparisons are optional and require the relevant reference R
datasets; the project’s Python table-generation and prediction stages do not
require those comparison datasets.

## Potential future work

The following are suggestions for people continuing this project, not
requirements for running the current workflow:

1. **Make the pipeline reproducible on a fresh machine.** Add a maintained
   Python dependency file with tested versions, document the supported
   Python/R/`rpy2` combination, and provide a single configurable entry point
   for the end-to-end run. Replace machine-specific absolute paths with paths
   derived from the project root or command-line configuration.
2. **Add automated tests and data-quality checks.** Test key transformations,
   cohort inclusion/exclusion rules, and prediction input/output shapes using
   small synthetic or appropriately de-identified fixtures. Add checks for
   required columns, allowed values, missingness, duplicate keys, and
   plausible date and survival-time ranges before proceeding between stages.
3. **Review and document clinical variable mappings.** Confirm mappings with
   appropriate domain experts and source documentation, including treatment
   coding and unknown values. In particular, review the current constant
   `bis.in` assignment and the smoking-status mapping before interpreting
   model results. Record the rationale and version of any mapping changes.
4. **Strengthen validation and uncertainty reporting.** Review the
   discrimination and calibration calculations, time horizons, censoring
   assumptions, and subgroup definitions. Consider reporting confidence
   intervals and documenting the analysis choices alongside generated
   tables and figures.
5. **Automate comparisons with the reference R workflow.** Where approved
   reference outputs are available, add repeatable checks for transformed
   tables, cohort counts, and predictions, so changes can be distinguished
   from unintended drift.
6. **Improve data and run provenance.** Record non-identifying run metadata
   such as code revision, model/package version, input file version or
   checksum, cohort criteria version, and execution date. Keep identifiable
   source and row-level data within the approved data environment.
7. **Separate and maintain exploratory analyses.** Label legacy or
   exploratory scripts, document their inputs and outputs, and promote
   analyses that remain in use into tested, reproducible workflow steps.

## Notes

- Run from the repository root so the relative input and output paths resolve.
- The preprocessing and prediction scripts overwrite their named output files
  when rerun; retain or back up outputs if needed.
- Pickle files are convenient internal intermediates, not a portable exchange
  format. Use CSV outputs when sharing permitted aggregate data.
- This repository is research/validation code; it is not a clinical decision
  support service.
