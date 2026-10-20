import os
import pandas as pd

# Dictionary mapping file paths to their formatted report titles
files_and_titles = {
    "datasets/bcfnz/excel/biomarkers.xlsx": "Biomarkers",
    "datasets/bcfnz/excel/demographic.xlsx": "Demographics",
    "datasets/bcfnz/excel/followup.xlsx": "Follow-up",
    "datasets/bcfnz/excel/histopathology.xlsx": "Histopathology",
    "datasets/bcfnz/excel/lesions.xlsx": "Lesions",
    "datasets/bcfnz/excel/metastatic_disease.xlsx": "Metastatic Disease",
    "datasets/bcfnz/excel/surgery_primary.xlsx": "Primary Surgery",
    "datasets/bcfnz/excel/therapy_biological.xlsx": "Biological Therapy",
    "datasets/bcfnz/excel/therapy_chemo.xlsx": "Chemotherapy",
    "datasets/bcfnz/excel/therapy_hormone.xlsx": "Hormonal Therapy",
    "datasets/bcfnz/excel/therapy_radio.xlsx": "Radiation Therapy",
    "datasets/bcfnz/excel/workup.xlsx": "Diagnostic Workup",
}


def make_overleaf_file(filepath, latex_content):
  """Writes the generated LaTeX string into a .tex file,

  creating directories if they don't exist.
  """
  os.makedirs(os.path.dirname(filepath), exist_ok=True)
  with open(filepath, "w", encoding="utf-8") as f:
    f.write(latex_content)

def reshape_biomarkers(df):
  """
  Data format that BCF provided in extract provided to Louie Curnow differs slightly to 
  the one provided to Matthew Strother. This function returns the data format to the 
one provided to Matthew Strother, which is more suitable for summary tables.
  """
   # --- OPTIONAL RESHAPING FOR WIDE SUFFIX DATASETS ---
  # If the file contains multi-source suffixes, pivot/coalesce them cleanly:
  suffixes = ["_CoreBiopsy", "_FNA", "_Histopathology", "_Other"]
  has_suffixes = any(
      any(col.endswith(s) for s in suffixes) for col in df.columns
  )

  if has_suffixes and "WorkupNo" in df.columns:
    # Identify unique base features by stripping the suffixes
    base_features = set()
    for col in df.columns:
      for s in suffixes:
        if col.endswith(s):
          base_features.add(col[: -len(s)])

    id_vars = [c for c in df.columns if not any(c.endswith(s) for s in suffixes)]

    melted_frames = []
    for base in base_features:
      # Find columns matching this base feature across different modalities
      val_vars = [f"{base}{s}" for s in suffixes if f"{base}{s}" in df.columns]
      if not val_vars:
        continue

      sub_melt = df[id_vars + val_vars].melt(
          id_vars=id_vars,
          value_vars=val_vars,
          var_name="ResultsFrom",
          value_name=base,
      )
      # Clean up the ResultsFrom string to just show the modality name (e.g. CoreBiopsy)
      sub_melt["ResultsFrom"] = (
          sub_melt["ResultsFrom"].str.replace(base, "").str.lstrip("_")
      )
      # Drop rows where the measurement is null due to cross-tab expansion
      sub_melt = sub_melt.dropna(subset=[base])
      melted_frames.append(sub_melt)

    # If we successfully flattened suffix-heavy columns, update df for analysis
    if melted_frames:
      # Combine or analyze the standardized long format structure
      # For a universal summary table across parameters, we concatenate or summarize cleanly:
      df = pd.concat(melted_frames, ignore_index=True)

  return df


# Loop through each file and create a summary table section
for file_path, title in files_and_titles.items():
  if not os.path.exists(file_path):
    print(f"Skipping {file_path} (File not found)")
    continue

  # Read the excel file into a pandas dataframe
  df = pd.read_excel(file_path)

  # convert datetime to string exluding time to avoid issues with LaTeX formatting
  for col in df.select_dtypes(include=["datetime64[ns]"]).columns:
        df[col] = df[col].dt.date.astype(str)

  if title == "Biomarkers":
    df = reshape_biomarkers(df)

  # Generate descriptive statistics for all columns (numeric and non-numeric)
  summary_table = df.describe(include="all").transpose()

  # Add custom columns for missing values, data type, and variable names
  summary_table["missing"] = df.isnull().sum()
  summary_table["dtype"] = df.dtypes.astype(str)
  summary_table["variable"] = summary_table.index

  # Ensure all expected columns exist (categorical columns lack mean/std/percentiles)
  expected_cols = [
      "variable",
      "dtype",
      "count",
      "mean",
      "std",
      "min",
      "max",
      "missing",
  ]
  for col in expected_cols:
    if col not in summary_table.columns:
      summary_table[col] = ""  # Fill missing statistical columns safely

  # Reorder the columns
  summary_table = summary_table[expected_cols]

  # Format output filename
  safe_filename = title.lower().replace(" ", "_").replace("-", "_")
  output_path = f"tables/tex/{safe_filename}_summary.tex"

  # Export to LaTeX string and save file
  latex_code = summary_table.to_latex(
      index=False,
      float_format="%.3f",
      na_rep="-",  # Represent NaN values cleanly with a dash in the table
      escape=True,  # Escape special LaTeX characters like underscores in variable names
  )

  make_overleaf_file(output_path, latex_code)
  print(f"Successfully generated: {output_path}")

print("All summary tables generated!")