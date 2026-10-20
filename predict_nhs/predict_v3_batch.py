import os
from pathlib import Path
import pandas as pd
import numpy as np

os.environ["RPY2_CFFI_MODE"] = "ABI"

import rpy2.robjects as ro
from rpy2.robjects import pandas2ri
from rpy2.robjects.conversion import localconverter
import io

out_dir = Path('./datasets/bcfnz/pickle/processed')

df = pd.read_pickle(Path('./datasets/bcfnz/pickle/processed/model_input.pickle'))

df['size.in'] = df['size.in'].astype(float)

# Source the R script
ro.r.source(str(Path('./predict_nhs/predict_wrapper.R'))) # type: ignore
process_predict_batch = ro.globalenv['process_predict_batch']

# Use localconverter to handle the conversion context
with localconverter(ro.default_converter + pandas2ri.converter):
    r_results = process_predict_batch(df)

    temp_df = ro.conversion.rpy2py(r_results)

r_results_clean = pd.DataFrame(temp_df)

for col in r_results_clean.select_dtypes(include=['object', 'category']).columns:
    r_results_clean[col] = r_results_clean[col].astype(str)

print(r_results_clean)
out_pickle = out_dir / 'predict_3_model_results.pickle'
r_results_clean.to_pickle(out_pickle)

out_csv = out_dir / 'predict_3_model_results.csv'
r_results_clean.to_csv(out_csv)