"""
This file contains functions which read in the original Excel files and then 
apply transformations to produce tidy datasets matching the R pipeline used by Strother in their project
The output files are written as pickles and CSVs to `datasets/bcfnz/pickle/processed/strother` and can be compared to the R .Rda files if available.
"""
import os
from pathlib import Path
import pandas as pd
import numpy as np
from scripts.pivot_surgeries import prepare_surgery_data, surg_first_last, surg_dates_by_side
import tabulate
from scripts.compare_dataframes import load_py, load_r, compare
from scripts.compare_tables import compare_tables, align_dtypes


def surgical_completeness(from_path: Path = Path('datasets/bcfnz/excel/surgery_primary.xlsx'),
					  out_dir: Path = Path('datasets/bcfnz/pickle/processed/strother/completeness')) -> dict:
	"""Read surgery XLSX from `from_path`, write pickles to `out_dir` and compare to Strother R data if available.

	Returns a dict with produced file paths and (optional) comparison summary.
	"""
	out_dir = Path(out_dir)
	out_dir.mkdir(parents=True, exist_ok=True)

	print(f"Processing surgery data from {from_path} to {out_dir}")

	results = {}

	if from_path.exists():
		df_full = pd.read_excel(from_path)

		df_full.rename(columns={'DateOfTissueDiagnosis': 'tissue_dx_date'}, inplace=True)
		df_full.drop(columns=['LeftBreastIgeCode', 'RightBreastIgeCode'], inplace=True)


		id_columns = ['PatientNo', 'WorkupNo', 'tissue_dx_date']

		left_cols = [id_cols] + ['DateOfSurgery', 'LeftBreastTypeOfAxillarySurgery', 'LeftBreastTypeOfBreastSurgery']

		df_left = df_full[left_cols]

		# unique key
		if 'PatientNo' in df_out.columns and 'tissue_dx_date' in df_out.columns:
			df_out['unique_key'] = df_out['PatientNo'].astype(str) + df_out['tissue_dx_date'].dt.strftime('%Y-%m-%d')

		print('df out cols', df_out.columns)

		full_pickle = out_dir / 'tidy_surgery.pickle'
		df_out.to_pickle(full_pickle)
		df_out.to_csv(out_dir / 'tidy_surgery.csv', index=False)
		results['tidy_surgery'] = str(full_pickle)
	else:
		results['tidy_surgery'] = None
		print(f'Path does not exist: {from_path}')

	# attempt a light comparison to R .Rda if pyreadr is available
	try:
		import pyreadr
	except Exception:
		results['r_compare'] = 'pyreadr not installed; skip R comparison'
		return results

	rfile = Path('datasets/bcfnz/strother/tidy_surgery_new_strother.Rda')
	if not rfile.exists():
		results['r_compare'] = 'R file not found: ' + str(rfile)
		return results

	try:
		rr = pyreadr.read_r(str(rfile))
		# take first dataframe object inside
		df_name, df_r = next(iter(rr.items()))
		compare = {}
		if from_path.exists():
			compare['full_rows_match'] = int(df_r.shape[0]) == int(df_out.shape[0])
			compare['full_cols_diff'] = list(sorted(set(df_r.columns) ^ set(df_out.columns)))

		results['r_compare'] = compare
	except Exception as e:
		results['r_compare'] = f'error reading R file: {e}'

	return results



def surgical_completeness_by_side(df):
    """
    Inputs: surgical data, adjuvant radiotherapy data

    Rules:
    Prophylactic Mastectomy  | Mastectomy     |  Lumpectomy    |    Radiation Therapy | Completion Code

    NO                       |  YES           |  X             |    X                 | COMPLETE   
    NO                       |  NO            |  YES           |    YES               | COMPLETE  
    NO                       |  NONE RECORDED |  NONE RECORDED |    YES               | NO_SURGICAL_DATA
    NO                       |  NO            |  YES           |    NO                | INCOMPLETE
    NO                       |  NA            |  NA            |    X                 | NA
    YES                      |  NO            |  NO            |    NO                | PPX_MAST
    """

    # if a mastectomy was done on a breast side, mark side complete with completion date as mastectomy date

    # if ppx mastectomy done, mark ppx_mast with completion date as ppx_mast date
	pass


if __name__ == '__main__':
	# working: biomarkers (1 diff), mets, demographics, followup, lesions
	# still to do: surgery, histopathology, hormone, chemo, biological therapy
	#transform_followup()
	#transform_lesions()
	#transform_surgery()
	tidy_filename = "tidy_surgery"
	strother_dir = Path("./datasets/bcfnz/strother/")
	out_dir = Path("./datasets/bcfnz/pickle/processed/strother/")
	compare_dir = Path(f"./datasets/bcfnz/compare/{tidy_filename}/")
	compare_dir.mkdir(parents=True, exist_ok=True)

	strother = load_r(strother_dir / f'{tidy_filename}_updated.Rda')
	lou = load_py(out_dir / f'{tidy_filename}.pickle')

	strother, lou = align_dtypes(strother, lou)

	# just select the date columns to compare at first
	id_cols = ['unique_key']
	strother_dates = strother[[c for c in strother.columns if 'date' in c or c in id_cols]]
	lou_dates = lou[[c for c in lou.columns if 'date' in c or c in id_cols]]
	
	res = compare_tables(lou_dates, strother_dates, key='unique_key', save_dir=compare_dir)
	#res = biomarkers_lou.compare(biomarkers_strother, keep_shape=True, keep_equal=True)
	print(res)

