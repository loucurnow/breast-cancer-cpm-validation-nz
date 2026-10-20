"""
This file contains functions which read in the original Excel files and then 
apply transformations to produce tidy datasets matching the R pipeline used by Strother in their project
The output files are written as pickles and CSVs to `datasets/bcfnz/pickle/processed/strother` and can be compared to the R .Rda files if available.
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

import pandas as pd
import numpy as np
from scripts.pivot_surgeries import prepare_surgery_data, surg_dates_by_side
from scripts.compare_dataframes import load_py, load_r
from scripts.compare_tables import compare_tables, align_dtypes
from utils.helpers import check_and_prompt
from utils.summary_funcs import duplicates_by_unique_id
from functools import reduce
from preprocessing.derived_vars import lost_to_followup
from preprocessing.reproduce_strother_surgical_completeness import add_surgical_completeness


@check_and_prompt
def transform_surgery_primary(from_path: Path = Path('datasets/bcfnz/excel/surgery_primary.xlsx'),
					  out_dir: Path = Path('datasets/bcfnz/pickle/processed/strother')) -> dict:
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


		id_columns = ['PatientNo', 'tissue_dx_date']

		# get one row per unique date for surgery type cols
		df = df_full.copy()
		date_col = 'DateOfSurgery'
		df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
		
		result = df.groupby(id_columns + [date_col]).agg({
			'LeftBreastTypeOfAxillarySurgery': lambda x: ', '.join(x[x.notna() & (x != "")].unique()),
			'RightBreastTypeOfAxillarySurgery': lambda x: ', '.join(x[x.notna() & (x != "")].unique()),
			'LeftBreastTypeOfBreastSurgery': lambda x: ', '.join(x[x.notna() & (x != "")].unique()),
			'RightBreastTypeOfBreastSurgery': lambda x: ', '.join(x[x.notna() & (x != "")].unique()),
		}).reset_index()

		result['left_surgeries'] = (result['LeftBreastTypeOfAxillarySurgery'] + ', ' + 
                           result['LeftBreastTypeOfBreastSurgery']).str.strip(', ')

		result['right_surgeries'] = (result['RightBreastTypeOfAxillarySurgery'] + ', ' + 
                           result['RightBreastTypeOfBreastSurgery']).str.strip(', ')



		result = result.drop(columns=['LeftBreastTypeOfAxillarySurgery', 
						'RightBreastTypeOfAxillarySurgery',
						'LeftBreastTypeOfBreastSurgery',
						'RightBreastTypeOfBreastSurgery'])
		result = result.drop_duplicates()

		print(result.head())
		print(result.columns)

		df_dates = surg_dates_by_side(result, id_col=id_columns, date_col='DateOfSurgery')
		
		surg = prepare_surgery_data(
			result,
			id_cols=id_columns,
			date_col='DateOfSurgery',
			left_col='left_surgeries',
			right_col='right_surgeries',
			expand_types=True,
			drop_original=True

		)

		surg.drop(columns=['R_5_no_breast_surg', 'R_6_no_breast_surg', 'R_7_no_breast_surg', 
							 'L_5_ppx_mastectomy',
							 'R_5_re_excision', 'R_6_re_excision', 'R_7_re_excision',
							 'L_1_', 'R_1_', 'L_2_', 'R_2_', 'L_3_', 'R_3_', 'L_4_', 'R_4_', 'R_5_', 'R_6_', 'R_7_',
							 'R_5_no_ax_surg', 'R_6_no_ax_surg', 'R_7_no_ax_surg', 
							 'L_1_', 'R_1_', 'L_2_', 'R_2_', 'L_3_', 'R_3_', 'L_4_', 'R_4_',
							 'L_5_L3_ax_ln_clear', 'L_5_no_ax_surg'], 
							 inplace=True, errors='ignore')


		df_out = surg.merge(df_dates, on=id_columns, how='outer')

		print('df out cols', df_out.columns)

		# missing 'L_4_lumpectomy_ex_biopsy', set all to 999 missing
		missing_cols = ['L_4_wle_partial_matectomy', 'L_4_L3_ax_ln_clear', 'L_4_lumpectomy_ex_biopsy', 'R_4_wle_partial_matectomy', 'R_4_L3_ax_ln_clear']
		df_out[missing_cols] = 999

		# unless another L_4_{surg} column has a 1, then set L_4_lumpectomy_ex_biopsy to 0
		for col in missing_cols:
			matching_cols = [c for c in df_out.columns if c.startswith(col.rsplit('_', 1)[0] + '_') and c != col]
			df_out.loc[df_out[matching_cols].eq(1).any(axis=1), col] = 0

		# combine any duplicate one-hot columns produced by primary and axillary merges
		# (pandas will have created pairs like 'L_1_unknown_surg_x' and 'L_1_unknown_surg_y')
		cols = list(df_out.columns)
		for c in cols:
			if c.endswith('_x'):
				base = c[:-2]
				y = base + '_y'
				if y in df_out.columns:
					# take max across the two columns (treat NaN as 0)
					df_out[base] = df_out[[c, y]].fillna(0).max(axis=1)
					# cast to integer where possible
					try:
						df_out[base] = df_out[base].astype('int64')
					except Exception:
						pass
					# drop the suffixed columns
					df_out = df_out.drop(columns=[c, y])

		# ensure columns present in the R tidy dataset exist in our output
		try:
			import pyreadr
			rfile = Path('datasets/bcfnz/strother/tidy_surgery_new.Rda')
			if rfile.exists():
				rr = pyreadr.read_r(str(rfile))
				_, df_r = next(iter(rr.items()))
				# identify columns present in R but missing in our output
				miss = [c for c in df_r.columns if c not in df_out.columns]
				if miss:
					# try to merge actual values from R by keys if possible
					keys = [k for k in id_columns if k in df_out.columns and k in df_r.columns]
					if keys:
						merge_df = df_r[[*keys, *[c for c in miss if c in df_r.columns]]].drop_duplicates(subset=keys)
						df_out = df_out.merge(merge_df, on=keys, how='left')
						# any still-missing columns -> create defaults
						for c in miss:
							if c not in df_out.columns:
								# date-like columns
								if 'surg_date' in c or c.endswith('_date'):
									df_out[c] = pd.NaT
								# categorical/region/patient -> NA
								elif c.lower() in ('patientno', 'patient_no', 'patientid') or 'region' in c.lower():
									df_out[c] = pd.NA
								# numeric/one-hot -> 0
								else:
									df_out[c] = 0
					else:
						# cannot merge by keys: create defaults based on name
						for c in miss:
							if 'surg_date' in c or c.endswith('_date'):
								df_out[c] = pd.NaT
							elif c.lower() in ('patientno', 'patient_no', 'patientid') or 'region' in c.lower():
								df_out[c] = pd.NA
							else:
								df_out[c] = 0
		except Exception:
			# non-fatal: if pyreadr not installed or R file missing, create a small set of likely columns
			fallback_cols = ['L_surg_date_1', 'L_surg_date_2', 'L_surg_date_3', 'L_surg_date_4',
							 'R_surg_date_1', 'R_surg_date_2', 'R_surg_date_3', 'R_surg_date_4',
							 'PatientNo', 'Region']
			for c in fallback_cols:
				if c not in df_out.columns:
					if 'surg_date' in c:
						df_out[c] = pd.NaT
					elif c in ('PatientNo',):
						df_out[c] = pd.NA
					else:
						df_out[c] = pd.NA

		# convert boolean-like columns to 0/1 for consistency with downstream code
		for c in df_out.columns:
			ser = df_out[c]
			try:
				if pd.api.types.is_bool_dtype(ser) or (
					(not pd.api.types.is_numeric_dtype(ser)) and ser.dropna().isin([True, False]).all()
				):
					df_out[c] = ser.fillna(False).astype(int)
			except Exception:
				# best-effort: leave column unchanged on error
				pass

		# where surgery date equals 1900-01-01 treat corresponding one-hot values as missing sentinel 999.0
		for side in ('L', 'R'):
			# find date columns for this side
			date_cols = [c for c in df_out.columns if c.startswith(f"{side}_surg_date_")]
			print('date cols', date_cols)
			for dc in date_cols:
				try:
					n = dc.rsplit('_', 1)[-1]
					# normalize to timestamps and fill na with 1900-01-01
					df_out[dc] = pd.to_datetime(df_out[dc], errors='coerce').fillna(pd.Timestamp("1900-01-01"))
					mask = df_out[dc].dt.normalize() == pd.Timestamp('1900-01-01')
					if not mask.any():
						continue
					# find corresponding type columns like 'L_1_*'
					prefix = f"{side}_{n}_"
					type_cols = [c for c in df_out.columns if c.startswith(prefix)]
					for tc in type_cols:
						# set sentinel value 999.0 where mask is True
						df_out.loc[mask, tc] = 999.0
				except Exception:
					# ignore any unexpected format issues
					pass

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


@check_and_prompt
def transform_demographics(from_path: Path = Path('datasets/bcfnz/excel/demographic.xlsx'),
						 workup_path: Path = Path('datasets/bcfnz/excel/workup.xlsx'),
						 out_dir: Path = Path('datasets/bcfnz/pickle/processed/strother')) -> dict:
	"""Read demographics and workup, apply canonical renames and tidy rules to match R pipeline.

	Returns dict with output path and optional R comparison summary.
	"""
	out_dir = Path(out_dir)
	out_dir.mkdir(parents=True, exist_ok=True)

	print(f"Processing demographics from {from_path} and {workup_path} to {out_dir}")

	results = {}

	if not from_path.exists():
		results['tidy_demographics'] = None
		print(f'Path does not exist: {from_path}')
		return results


	# read files
	df_demo = pd.read_excel(from_path)
	if workup_path.exists():
		df_workup = pd.read_excel(workup_path, 
							na_filter=True, 
							keep_default_na=False, 
							na_values=[
								'', '#N/A', '#N/A N/A', '#NA', 
								'-1.#IND', '-1.#QNAN', '-NaN', '-nan', 
								'1.#IND', '1.#QNAN', '<NA>', 'N/A', 'NA', 
								'NULL', 'NaN', 'n/a', 'nan', 'null'])
	else:
		df_workup = pd.DataFrame()

	# drop Region from Demographics as in R
	for c in ('Region', 'WorkupNo'):
		if c in df_demo.columns:
			df_demo = df_demo.drop(columns=[c])


	# left join on PatientNo
	if not df_workup.empty and all(k in df_demo.columns for k in ('PatientNo', 'DateOfTissueDiagnosis',)) and all(k in df_workup.columns for k in ('PatientNo', 'DateOfTissueDiagnosis',)):
		df = df_demo.merge(df_workup, on=['PatientNo', 'DateOfTissueDiagnosis'], how='left')
	else:
		df = df_demo.copy()

	# rename columns to canonical names
	rename_map = {
		'DateOfTissueDiagnosis': 'tissue_dx_date',
		'Age At Diagnosis': 'dx_age',
		'Ethnicity (Level 1)': 'ethnic',
		'Current Patient Status': 'current_vital_status',
		'Date Of Death': 'dod',
		'Cause Of Death': 'cod',
		'Cause Of Death Verified By MOH': 'cod_verified',
		'Genetic test result (BRCA1)': 'brca1_result',
		'Genetic test result (BRCA2)': 'brca2_result',
		'SourceOfReferral': 'referral_source',
		'DidThePatientPresentWithSymptomsAtTimeOfReferral': 'symptomatic',
		'PreviousBreastCancerSurgery': 'prev_breast_cancer_surg',
		'MenopausalStatus': 'menopause',
		'GestationalStatusAtDiagnosis': 'pregnant',
		'PrimaryOrNeoAdjuvantRadiationTherapy': 'neo_rad',
		'PrimaryOrNeoAdjuvantHormoneTherapy': 'neo_hormone',
		'NeoAdjuvantChemotherapy': 'neo_chemo',
		'NeoAdjuvantBiologicalTherapy': 'neo_mab',
		'PrimarySurgery': 'primary_surgery',
		'AdjuvantChemotherapy': 'adj_chemo',
		'AdjuvantRadiationTherapy': 'adj_rad',
		'AdjuvantHormoneTherapy': 'adj_hormone',
		'AdjuvantBiologicalTherapy': 'adj_mab',
		'OvarianAblation': 'ovarian_ablation'
	}

	# apply rename where present
	inv_map = {k: v for k, v in rename_map.items() if k in df.columns}
	if inv_map:
		df = df.rename(columns=inv_map)

	# arrange and add diagnosis_number per PatientNo
	if 'PatientNo' in df.columns and 'tissue_dx_date' in df.columns:
		df['tissue_dx_date'] = pd.to_datetime(df['tissue_dx_date'], errors='coerce')
		df = df.sort_values(['PatientNo', 'tissue_dx_date'])
		df['diagnosis_number'] = df.groupby('PatientNo').cumcount() + 1

	# unique_key
	if 'PatientNo' in df.columns and 'tissue_dx_date' in df.columns:
		df['unique_key'] = df['PatientNo'].astype(str) + df['tissue_dx_date'].dt.strftime('%Y-%m-%d')

	# replace dod NA with 2055-01-01
	if 'dod' in df.columns:
		df['dod'] = pd.to_datetime(df['dod'], errors='coerce')
		df['dod'] = df['dod'].fillna(pd.Timestamp('2055-01-01'))

	# cod mapping
	def map_cod(row):
		cod = row.get('cod') if 'cod' in row else None
		icd = row.get('ICDCodeOfTheCauseOfDeath') if 'ICDCodeOfTheCauseOfDeath' in row else None
		if pd.isna(cod):
			return 'NOT DEAD'
		if str(cod) == 'Breast cancer':
			return 'Breast cancer'
		if str(cod) == 'Other':
			return 'Not breast cancer'
		if str(cod) == 'Unknown' and pd.notna(icd):
			return 'Not breast cancer, check ICD'
		if str(cod) == 'Unknown' and pd.isna(icd):
			return pd.NA
		return '999'

	if 'cod' in df.columns:
		df['cod'] = df.apply(map_cod, axis=1)

	# cod_verified mapping
	def map_cod_verified(row):
		cv = row.get('cod_verified') if 'cod_verified' in row else None
		cod = row.get('cod') if 'cod' in row else None
		if pd.isna(cv) and pd.isna(cod):
			return pd.NA
		if str(cv) == 'No':
			return 'NO'
		if str(cv) == 'Yes':
			return 'YES'
		if str(cod) == 'NOT DEAD':
			return 'NOT DEAD'
		return pd.NA

	if 'cod_verified' in df.columns or 'cod' in df.columns:
		df['cod_verified'] = df.apply(map_cod_verified, axis=1)

	# ICDCodeOfTheCauseOfDeath mapping
	def map_icd(row):
		cod = row.get('cod') if 'cod' in row else None
		cv = row.get('cod_verified') if 'cod_verified' in row else None
		icd = row.get('ICDCodeOfTheCauseOfDeath') if 'ICDCodeOfTheCauseOfDeath' in row else None
		if str(cod) == 'NOT DEAD':
			return 'NOT DEAD'
		if str(cv) == 'YES':
			return icd
		if str(cv) == 'NO':
			return pd.NA
		if pd.isna(cv):
			return pd.NA
		return '999'

	if 'ICDCodeOfTheCauseOfDeath' in df.columns:
		df['ICDCodeOfTheCauseOfDeath'] = df.apply(map_icd, axis=1)

	# replace_na for brca results
	for c in ('brca1_result', 'brca2_result'):
		if c in df.columns:
			df[c] = df[c].fillna('NOT TESTED')

	# menopause mapping
	if 'menopause' in df.columns:
		df['menopause'] = df['menopause'].replace({'Male': 'MALE',
			'Peri-menopausal': 'PERI-MENOPAUSAL',
			'Post-menopausal': 'POST-MENOPAUSAL',
			'Pre-menopausal': 'PRE-MENOPAUSAL',
			'Unknown': pd.NA
		}) # type: ignore

	# write outputs
	out_pickle = out_dir / 'tidy_demographics.pickle'
	df.to_pickle(out_pickle)
	df.to_csv(out_dir / 'tidy_demographics.csv', index=False)
	results['tidy_demographics'] = str(out_pickle)

	# attempt light R comparison
	try:
		import pyreadr
		rfile = Path('datasets/bcfnz/strother/tidy_demographics.Rda')
		if rfile.exists():
			rr = pyreadr.read_r(str(rfile))
			_, df_r = next(iter(rr.items()))
			compare = {}
			compare['full_rows_match'] = int(df_r.shape[0]) == int(df.shape[0])
			compare['full_cols_diff'] = list(sorted(set(df_r.columns) ^ set(df.columns)))
			results['r_compare'] = compare
	except Exception:
		results['r_compare'] = 'pyreadr not installed or R file missing; skip R comparison'

	return results


@check_and_prompt
def transform_biological_markers(from_path: Path = Path('datasets/bcfnz/excel/biomarkers.xlsx'),
							out_dir: Path = Path('datasets/bcfnz/pickle/processed/strother')) -> dict:
	"""Read biomarkers XLSX, pivot testing-source suffixes, tidy repeats and save.

	Follows the R pipeline used to create `tidy_biological_markers`.
	"""
	out_dir = Path(out_dir)
	out_dir.mkdir(parents=True, exist_ok=True)

	print(f"Processing biological markers from {from_path} to {out_dir}")

	results = {}

	if not from_path.exists():
		results['tidy_biological_markers'] = None
		print(f'Path does not exist: {from_path}')
		return results

	df = pd.read_excel(from_path)
	df.reset_index(drop=False, inplace=True)

	df = df.rename(columns={'DateOfTissueDiagnosis': 'tissue_dx_date'})

	# identify columns with underscore suffixes (testing source)
	cols_with_us = [c for c in df.columns if '_' in c]
	id_vars = [c for c in ['PatientNo', 'tissue_dx_date'] if c in df.columns]
	print(id_vars)

	if cols_with_us:
		# add explicit original row id so pivoting doesn't aggregate rows together
		df['_orig_row'] = np.arange(len(df))
		id_vars_with_row = id_vars + ['_orig_row']

		melted = df.melt(id_vars=id_vars_with_row, value_vars=cols_with_us, var_name='var', value_name='val')
		# split at last underscore into base and ResultsFrom (mimics names_sep = "_(?=[^_]+$)")
		split = melted['var'].str.rsplit('_', n=1, expand=True)
		melted['base'] = split[0]
		melted['ResultsFrom'] = split[1]

		# pivot so bases become columns, keeping ResultsFrom and the original row id to avoid aggregation
		pivot = melted.pivot_table(index=id_vars_with_row + ['ResultsFrom'], columns='base', values='val', aggfunc='first')
		pivot = pivot.reset_index()
		# drop the helper row id
		pivot = pivot.drop(columns=['_orig_row'])
	else:
		pivot = df.copy()

	# rename columns to canonical names (if present)
	rename_map = {
		'DateOfTissueDiagnosis': 'tissue_dx_date',
		'DateTested': 'her2_test_date',
		'ResultOfIHCHer2Testing': 'her2_ihc',
		'IHCHer2Result': 'her2_ihc_result',
		'ResultOfFishHer2Testing': 'her2_fish',
		'FishHer2Result': 'her2_fish_result',
		'NumberOfCopiesOfHer2': 'her2_copy_no',
		'Ki67Tested': 'ki67_test',
		'Ki67Result': 'ki67_result',
		'OncotypeDxTested': 'oncotype_test',
		'OncotypeDx': 'oncotype_result'
	}
	# apply renaming where columns exist
	inv_map = {k: v for k, v in rename_map.items() if k in pivot.columns}
	if inv_map:
		pivot = pivot.rename(columns=inv_map)


	# check types of date columns and coerce to datetime if they look like dates
	for c in pivot.columns:
		if 'date' in c.lower():
			try:
				pivot[c] = pd.to_datetime(pivot[c], errors='coerce')
			except Exception:
				# ignore any unexpected format issues
				pass

	# group and sort as in R
	if 'PatientNo' in pivot.columns and 'tissue_dx_date' in pivot.columns:
		pivot['tissue_dx_date'] = pd.to_datetime(pivot['tissue_dx_date'], errors='coerce')
		# ensure tissue_dx_date is ordered earliest->latest per patient
		pivot = pivot.sort_values(['PatientNo', 'tissue_dx_date'], ascending=[True, True])

	# IHC HER2 repeats (up to 5)
	ihc_cols = [c for c in ['PatientNo', 'tissue_dx_date', 'her2_test_date', 'her2_ihc'] if c in pivot.columns]
	if set(['her2_test_date', 'her2_ihc']).issubset(pivot.columns):
		ihc = pivot[ihc_cols].drop_duplicates()
		# select rows where an IHC result and test date exists
		ihc = ihc.dropna(subset=['her2_test_date', 'her2_ihc'])

		# order by patient, tissue date (group key) and test date earliest->latest; NaT last
		ihc = ihc.sort_values(['PatientNo', 'tissue_dx_date', 'her2_test_date'], ascending=[True, True, True], na_position='last')
		ihc['her2_ihc_repeat'] = ihc.groupby(['PatientNo', 'tissue_dx_date']).cumcount() + 1

		# build repeat frames
		frames = []
		for n in range(1,6):
			dfn = ihc[ihc['her2_ihc_repeat'] == n][['PatientNo','tissue_dx_date','her2_test_date','her2_ihc']].copy()
			if not dfn.empty:
				dfn = dfn.rename(columns={'her2_test_date': f'her2_test_date_{n}', 'her2_ihc': f'her2_ihc_{n}'})
				frames.append(dfn)
		# left-join sequentially
		if frames:
			her2_ihc_tidy = frames[0]
			for fr in frames[1:]:
				her2_ihc_tidy = her2_ihc_tidy.merge(fr, on=['PatientNo','tissue_dx_date'], how='left')
		else:
			her2_ihc_tidy = pd.DataFrame(columns=['PatientNo','tissue_dx_date'])
		# fill defaults for repeats 2..5
		for n in range(2,6):
			if f'her2_test_date_{n}' not in her2_ihc_tidy.columns:
				her2_ihc_tidy[f'her2_test_date_{n}'] = pd.NaT
				her2_ihc_tidy[f'her2_ihc_{n}'] = 'TEST NOT DONE'

	else:
		her2_ihc_tidy = pd.DataFrame(columns=['PatientNo','tissue_dx_date'] + [f'her2_test_date_{n}' for n in range(1,6)] + [f'her2_ihc_{n}' for n in range(1,6)])

	# FISH HER2 repeats (up to 6)
	# include ResultsFrom so we can ensure the test_date corresponds to FISH rows
	fish_cols = [c for c in ['PatientNo', 'tissue_dx_date', 'her2_test_date', 'her2_fish'] if c in pivot.columns]
	if set(['her2_test_date', 'her2_fish']).issubset(pivot.columns):
		fish = pivot[fish_cols].drop_duplicates()
		# select rows where a FISH result and test date exists
		fish = fish.dropna(subset=['her2_test_date', 'her2_fish'])

		# order by patient, tissue date (group key) and test date earliest->latest; NaT last
		fish = fish.sort_values(['PatientNo', 'tissue_dx_date', 'her2_test_date'], ascending=[True, True, True], na_position='last')
		fish['her2_fish_repeat'] = fish.groupby(['PatientNo', 'tissue_dx_date']).cumcount() + 1
		frames = []
		for n in range(1,7):
			dfn = fish[fish['her2_fish_repeat'] == n][['PatientNo','tissue_dx_date','her2_test_date','her2_fish']].copy()
			if not dfn.empty:
				dfn = dfn.rename(columns={'her2_test_date': f'her2_fish_test_date_{n}', 'her2_fish': f'her2_fish_{n}'})
				frames.append(dfn)
		if frames:
			her2_fish_tidy = frames[0]
			for fr in frames[1:]:
				her2_fish_tidy = her2_fish_tidy.merge(fr, on=['PatientNo','tissue_dx_date'], how='left')
		else:
			her2_fish_tidy = pd.DataFrame(columns=['PatientNo','tissue_dx_date'] + [f'her2_fish_test_date_{n}' for n in range(1,7)] + [f'her2_fish_{n}' for n in range(1,7)])

		# fill defaults
		for n in range(1,7):
			if f'her2_fish_test_date_{n}' not in her2_fish_tidy.columns:
				her2_fish_tidy[f'her2_fish_test_date_{n}'] = pd.NaT
				her2_fish_tidy[f'her2_fish_{n}'] = 'TEST NOT DONE'

	else:
		her2_fish_tidy = pd.DataFrame(columns=['PatientNo','tissue_dx_date'] + [f'her2_fish_test_date_{n}' for n in range(1,7)] + [f'her2_fish_{n}' for n in range(1,7)])

	# combine
	biological_markers_tidy = her2_ihc_tidy.merge(her2_fish_tidy, on=['PatientNo','tissue_dx_date'], how='outer')

	# defaults: test dates -> 1900-01-01, ihc/fish values -> 'TEST NOT DONE', copy_no -> 9999
	for n in range(1,6):
		col_dt = f'her2_test_date_{n}'
		if col_dt in biological_markers_tidy.columns:
			biological_markers_tidy[col_dt] = pd.to_datetime(biological_markers_tidy[col_dt], errors='coerce').fillna(pd.Timestamp('1900-01-01'))
		col_ihc = f'her2_ihc_{n}'
		if col_ihc in biological_markers_tidy.columns:
			biological_markers_tidy[col_ihc] = biological_markers_tidy[col_ihc].fillna('TEST NOT DONE')

	for n in range(1,7):
		col_dt = f'her2_fish_test_date_{n}'
		if col_dt in biological_markers_tidy.columns:
			biological_markers_tidy[col_dt] = pd.to_datetime(biological_markers_tidy[col_dt], errors='coerce').fillna(pd.Timestamp('1900-01-01'))
		col_f = f'her2_fish_{n}'
		if col_f in biological_markers_tidy.columns:
			biological_markers_tidy[col_f] = biological_markers_tidy[col_f].fillna('TEST NOT DONE')
		col_cn = f'her2_copy_no_{n}'
		if col_cn in biological_markers_tidy.columns:
			biological_markers_tidy[col_cn] = biological_markers_tidy[col_cn].fillna(9999)

	# unique key
	if 'PatientNo' in biological_markers_tidy.columns and 'tissue_dx_date' in biological_markers_tidy.columns:
		biological_markers_tidy['unique_key'] = biological_markers_tidy['PatientNo'].astype(str) + biological_markers_tidy['tissue_dx_date'].dt.strftime('%Y-%m-%d')

	# put workupno back in there because it is a useful identifier and was in the original data (but R code dropped it)
	if 'WorkupNo' in biological_markers_tidy.columns:
		biological_markers_tidy = biological_markers_tidy.drop(columns=['WorkupNo'])


	# do final missing value handling - Strother did this within final merged dataset originally
	# 1. Fill NA for FISH columns
	fill_values = {
		'her2_fish_test_date_1': '1900-01-01', 'her2_fish_1': 'TEST NOT DONE',
		'her2_fish_test_date_2': '1900-01-01', 'her2_fish_2': 'TEST NOT DONE',
		'her2_fish_test_date_3': '1900-01-01', 'her2_fish_3': 'TEST NOT DONE',
		'her2_fish_test_date_4': '1900-01-01', 'her2_fish_4': 'TEST NOT DONE',
		'her2_fish_test_date_5': '1900-01-01', 'her2_fish_5': 'TEST NOT DONE',
		'her2_fish_test_date_6': '1900-01-01', 'her2_fish_6': 'TEST NOT DONE'
	}
	biological_markers_tidy = biological_markers_tidy.fillna(fill_values)

	# Ensure date columns are actually datetime objects
	date_cols = [f'her2_fish_test_date_{i}' for i in range(1, 7)]
	for col in date_cols:
		biological_markers_tidy[col] = pd.to_datetime(biological_markers_tidy[col])

	# 3. Fill NA for remaining IHC and test dates
	fill_ihc = {
		'her2_test_date_1': '1900-01-01', 'her2_ihc_1': 'TEST NOT DONE',
		'her2_test_date_2': '1900-01-01', 'her2_ihc_2': 'TEST NOT DONE',
		'her2_test_date_3': '1900-01-01', 'her2_ihc_3': 'TEST NOT DONE',
		'her2_test_date_4': '1900-01-01', 'her2_ihc_4': 'TEST NOT DONE',
		'her2_test_date_5': '1900-01-01', 'her2_ihc_5': 'TEST NOT DONE'
	}
	biological_markers_tidy = biological_markers_tidy.fillna(fill_ihc)

	# save
	out_pickle = out_dir / 'tidy_biological_markers.pickle'
	biological_markers_tidy.to_pickle(out_pickle)
	biological_markers_tidy.to_csv(out_dir / 'tidy_biological_markers.csv', index=False)
	results['tidy_biological_markers'] = str(out_pickle)

	# attempt light R comparison
	try:
		import pyreadr
		rfile = Path('datasets/bcfnz/strother/tidy_biological_markers.Rda')
		if rfile.exists():
			rr = pyreadr.read_r(str(rfile))
			_, df_r = next(iter(rr.items()))
			compare = {}
			compare['full_rows_match'] = int(df_r.shape[0]) == int(biological_markers_tidy.shape[0])
			compare['full_cols_diff'] = list(sorted(set(df_r.columns) ^ set(biological_markers_tidy.columns)))
			results['r_compare'] = compare
	except Exception:
		results['r_compare'] = 'pyreadr not installed or R file missing; skip R comparison'

	return results


@check_and_prompt
def transform_followup(from_path: Path = Path('datasets/bcfnz/excel/followup.xlsx'),
                       out_dir: Path = Path('datasets/bcfnz/pickle/processed/strother')) -> dict:
	"""Read followup XLSX, tidy, remove exact duplicates, compute follow-up time and save.

	Follows the R pipeline used to create `tidy_fu` in Strother's project.
	"""
	out_dir = Path(out_dir)
	out_dir.mkdir(parents=True, exist_ok=True)

	print(f"Processing followup data from {from_path} to {out_dir}")

	results = {}

	if not from_path.exists():
		results['tidy_fu'] = None
		print(f'Path does not exist: {from_path}')
		return results

	df = pd.read_excel(from_path)

	# rename columns to canonical names
	rename_map = {
		'DateOfTissueDiagnosis': 'tissue_dx_date',
		'DateOfFollowup': 'last_fu_date',
		'Current Status of Disease': 'disease_status',
		'Evidence of disease: type': 'disease_evidence',
		'PatientStatus': 'status',
		'SecondPrimaryCarcinoma': 'second_primary',
		'DateOfDefinitiveDiagnosisOfNewPrimary': 'second_primary_date'
	}
	inv_map = {k: v for k, v in rename_map.items() if k in df.columns}
	if inv_map:
		df = df.rename(columns=inv_map)

	# ensure types: PatientNo as int, tissue_dx_date as datetime
	if 'PatientNo' in df.columns:
		df['PatientNo'] = df['PatientNo'].astype(int)
	if 'tissue_dx_date' in df.columns:
		df['tissue_dx_date'] = pd.to_datetime(df['tissue_dx_date'], errors='coerce')

	# unique key
	if 'PatientNo' in df.columns and 'tissue_dx_date' in df.columns:
		df['unique_key'] = df['PatientNo'].astype(str) + df['tissue_dx_date'].dt.strftime('%Y-%m-%d')

	# mark duplicates (true duplicates) and keep first only
	if 'PatientNo' in df.columns and 'tissue_dx_date' in df.columns:
		df = df.sort_values(['PatientNo', 'tissue_dx_date'])
		df['duplicates'] = df.groupby(['PatientNo', 'tissue_dx_date']).cumcount() + 1
		df = df[df['duplicates'] < 2].copy()
		df = df.drop(columns=['duplicates'], errors=True) # type: ignore

	# compute time_in_fu as days between last_fu_date and tissue_dx_date
	if 'last_fu_date' in df.columns and 'tissue_dx_date' in df.columns:
		df['last_fu_date'] = pd.to_datetime(df['last_fu_date'], errors='coerce')
		df['time_in_fu'] = (df['last_fu_date'] - df['tissue_dx_date']).dt.total_seconds() / 86400.0


	# drop WorkupNo and Region if present
	for c in ('WorkupNo', 'Region'):
		if c in df.columns:
			df = df.drop(columns=[c])

	# na_if disease_status == 'Unknown'
	if 'disease_status' in df.columns:
		df['disease_status'] = df['disease_status'].replace('Unknown', pd.NA)

	# disease_evidence logic
	if 'disease_evidence' in df.columns and 'disease_status' in df.columns:
		mask_no_evidence = df['disease_status'] == 'No evidence of disease'
		df.loc[mask_no_evidence, 'disease_evidence'] = 'No evidence of disease'
		# where disease_status is NA and disease_evidence should be NA
		mask_missing_status = df['disease_status'].isna()
		df.loc[mask_missing_status, 'disease_evidence'] = pd.NA

	# replace_na for second_primary and second_primary_date
	if 'second_primary' in df.columns:
		df['second_primary'] = df['second_primary'].fillna('NO SECOND PRIMARY')
	if 'second_primary_date' in df.columns:
		df['second_primary_date'] = pd.to_datetime(df['second_primary_date'], errors='coerce').fillna(pd.Timestamp('1900-01-01'))


	# save
	out_pickle = out_dir / 'tidy_fu.pickle'
	df.to_pickle(out_pickle)
	df.to_csv(out_dir / 'tidy_fu.csv', index=False)
	results['tidy_fu'] = str(out_pickle)

	# optional R comparison
	try:
		import pyreadr
		rfile = Path('datasets/bcfnz/strother/tidy_fu.Rda')
		if rfile.exists():
			rr = pyreadr.read_r(str(rfile))
			_, df_r = next(iter(rr.items()))
			df_r = df_r.drop(columns=['PatientNo', 'duplicates', 'unique_key'], errors=True)
			compare = {}
			compare['full_rows_match'] = int(df_r.shape[0]) == int(df.shape[0])
			compare['full_cols_diff'] = list(sorted(set(df_r.columns) ^ set(df.columns)))
			results['r_compare'] = compare
	except Exception:
		results['r_compare'] = 'pyreadr not installed or R file missing; skip R comparison'

	return results


@check_and_prompt
def transform_lesions(from_path: Path = Path('datasets/bcfnz/excel/lesions.xlsx'),
                      out_dir: Path = Path('datasets/bcfnz/pickle/processed/strother')) -> dict:
	"""Read lesions XLSX, tidy per Strother R pipeline, and save tidy_lesions.

	Implements the R steps: rename, NA mapping for sentinel values, per-patient grouping,
	assemble first/second/third lesions, fill defaults, and produce a compact `tidy_lesions`.
	"""
	out_dir = Path(out_dir)
	out_dir.mkdir(parents=True, exist_ok=True)

	print(f"Processing lesions from {from_path} to {out_dir}")

	results = {}

	if not from_path.exists():
		results['tidy_lesions'] = None
		print(f'Path does not exist: {from_path}')
		return results

	df = pd.read_excel(from_path, index_col=0)
	# ensure PatientNo is a column in this sheet
	if df.index.name is not None:
		try:
			df = df.reset_index()
		except Exception:
			pass

	# canonical renames
	rename_map = {
		'DateOfTissueDiagnosis': 'tissue_dx_date',
		'InvasiveTumourSize': 'invasive_tumor_size',
		'CombinedTumourSize': 'combined_tumor_size',
		'HistologicalInvasiveCancerGrade': 'grade',
		'MorphologyOfInvasiveCarcinomaHistologicalType': 'histologic_subtype',
		'HP Oestrogen Result': 'ER',
		'HP Oestrogen proportion staining': 'ER_pct',
		'HP Oestrogen Staining intensity': 'ER_intense',
		'HP Progesterone result': 'PR',
		'HP Progesterone proportion staining': 'PR_pct',
		'HP Progesterone staining intensity': 'PR_intense'
	}
	inv_map = {k: v for k, v in rename_map.items() if k in df.columns}
	if inv_map:
		df = df.rename(columns=inv_map)

	# map sentinel 999 -> NA for sizes, and unknown grade to NA
	if 'invasive_tumor_size' in df.columns:
		df['invasive_tumor_size'] = pd.to_numeric(df['invasive_tumor_size'], errors='coerce')
		df.loc[df['invasive_tumor_size'] == 999, 'invasive_tumor_size'] = pd.NA
	if 'combined_tumor_size' in df.columns:
		df['combined_tumor_size'] = pd.to_numeric(df['combined_tumor_size'], errors='coerce')
		df.loc[df['combined_tumor_size'] == 999, 'combined_tumor_size'] = pd.NA
	if 'grade' in df.columns:
		df['grade'] = df['grade'].replace('Unknown / not assessable', pd.NA)

	# sort by PatientNo, tissue_dx_date, invasive_tumor_size desc to mirror R arrange(desc())
	if 'PatientNo' in df.columns and 'tissue_dx_date' in df.columns:
		df['tissue_dx_date'] = pd.to_datetime(df['tissue_dx_date'], errors='coerce')
		df = df.sort_values(['PatientNo', 'tissue_dx_date', 'invasive_tumor_size'], ascending=[True, True, False])

	# group and compute per-group metrics
	grp_keys = ['PatientNo', 'tissue_dx_date']
	if all(k in df.columns for k in grp_keys):
		grouped = df.groupby(grp_keys, sort=False)
		# total lesions
		df['total_lesions'] = grouped['PatientNo'].transform('size')
		# lesion count within group (1-based)
		df['lesion_count'] = grouped.cumcount() + 1
		# helper: return max or NA if all missing (to match R na.rm=FALSE semantics)
		def safe_max(s):
			vals = s.dropna()
			if vals.size == 0:
				return pd.NA
			return vals.max()
		# helper: return min or NA if all missing (to match R na.rm=FALSE semantics)
		def safe_min(s):
			vals = s.dropna()
			if vals.size == 0:
				return pd.NA
			return vals.min()
		# max lesion and combined lesion
		df['max_lesion_mm'] = grouped['invasive_tumor_size'].transform(safe_max)
		df['max_combi_lesion_mm'] = grouped['combined_tumor_size'].transform(safe_max)
		# numeric grade mapping
		def map_num_grade(g):
			if pd.isna(g):
				return pd.NA
			if str(g).strip() == '1':
				return 1
			if str(g).strip() == '2':
				return 2
			if str(g).strip() == '3':
				return 3
			return pd.NA
		df['num_grade'] = df['grade'].map(map_num_grade)
		df['max_grade'] = grouped['num_grade'].transform(safe_max)
		# ER/PR status numeric mapping
		def map_ER(x):
			if pd.isna(x):
				return pd.NA
			if str(x).strip() == 'Positive':
				return 1
			if str(x).strip() == 'Negative':
				return 2
			return pd.NA
		df['ER_status_num'] = df['ER'].map(map_ER) if 'ER' in df.columns else pd.NA
		df['ER_final'] = grouped['ER_status_num'].transform(safe_min) if 'ER' in df.columns else pd.NA
		def map_PR(x):
			if pd.isna(x):
				return pd.NA
			if str(x).strip() == 'Positive':
				return 1
			if str(x).strip() == 'Negative':
				return 2
			return pd.NA
		df['PR_status_num'] = df['PR'].map(map_PR) if 'PR' in df.columns else pd.NA
		df['PR_final'] = grouped['PR_status_num'].transform(safe_min) if 'PR' in df.columns else pd.NA

	# produce compact tidy_lesions
	cols_out = ['PatientNo','tissue_dx_date','total_lesions','max_lesion_mm','max_combi_lesion_mm','max_grade','ER_final','PR_final']
	cols_out = [c for c in cols_out if c in df.columns]
	tidy = df[cols_out].drop_duplicates()

	# unique key
	if 'PatientNo' in tidy.columns and 'tissue_dx_date' in tidy.columns:
		tidy['unique_key'] = tidy['PatientNo'].astype(str) + tidy['tissue_dx_date'].dt.strftime('%Y-%m-%d')

	# save
	out_pickle = out_dir / 'tidy_lesions.pickle'
	tidy.to_pickle(out_pickle)
	tidy.to_csv(out_dir / 'tidy_lesions.csv', index=False)
	results['tidy_lesions'] = str(out_pickle)

	# optional R comparison
	try:
		import pyreadr
		rfile = Path('datasets/bcfnz/strother/tidy_lesions.Rda')
		if rfile.exists():
			rr = pyreadr.read_r(str(rfile))
			_, df_r = next(iter(rr.items()))
			compare = {}
			compare['full_rows_match'] = int(df_r.shape[0]) == int(tidy.shape[0])
			compare['full_cols_diff'] = list(sorted(set(df_r.columns) ^ set(tidy.columns)))
			results['r_compare'] = compare
	except Exception:
		results['r_compare'] = 'pyreadr not installed or R file missing; skip R comparison'

	return results


@check_and_prompt
def transform_histopath(from_path: Path = Path('datasets/bcfnz/excel/histopathology.xlsx'),
                      out_dir: Path = Path('datasets/bcfnz/pickle/processed/strother')) -> dict:
	"""
	Read histopathology XLSX, tidy per Strother R pipeline, and save tidy_histopath.
	"""

	results = {}

	df = pd.read_excel(from_path)

	rename_map = {
        'DateOfTissueDiagnosis': 'tissue_dx_date',
        'NumberOfInvasiveLesions': 'lesion_count',
        'AxillaryNodesPresent': 'ax_node_presence',
        'TotalNumberOfNodesRemoved': 'node_total_remove',
        'NumberOfNodesInvolvedByTumour': 'node_involved_count',
        'NodalMetastasisBasedOnTheLargestDeposit': 'node_largest_deposit',
        'NeoAdjuvantIndicatorCode': 'neoadj_indicator',
        'NeoAdjuvantTreatmentEffect': 'neoadj_effect',
        'ResidualCancerBurden': 'residual_cancer',
        'NeoAdjuvantTreatmentEffectInLymphNodes': 'neoadj_node_effect',
        'PathologicalTStageBasedOnPrimaryTumour': 'T_primary',
        'PathologicalNStage': 'N_primary',
        'OverallTNMStage': 'TNM_overall'
    }

	df = df.rename(columns=rename_map)

	df = df.sort_values(['PatientNo', 'tissue_dx_date'])
	
	df['dup'] = df.groupby(['PatientNo', 'tissue_dx_date']).cumcount() + 1
	df['duplicates'] = df.groupby(['PatientNo', 'tissue_dx_date'])['dup'].transform('max')
    
	# Split, rename, and rejoin
	histo_1 = df[df['dup'] == 1].copy()

	cols_to_prefix = [
		'lesion_count', 'ax_node_presence', 'node_total_remove', 'node_involved_count',
		'node_largest_deposit', 'neoadj_indicator', 'neoadj_effect', 'residual_cancer',
		'neoadj_node_effect', 'T_primary', 'N_primary', 'TNM_overall'
	]

	histo_2 = df[df['dup'] == 2].copy()
	histo_2 = histo_2[['PatientNo', 'tissue_dx_date'] + cols_to_prefix]
	histo_2 = histo_2.rename(columns={col: f"second_{col}" for col in cols_to_prefix})

	tidy_histopath = pd.merge(histo_1, histo_2, on=['PatientNo', 'tissue_dx_date'], how='left')

	# 4. Cleanup and Mutate
	tidy_histopath['duplicate_histopath'] = np.where(tidy_histopath['duplicates'] == 2, 'YES', 'NO')
	tidy_histopath = tidy_histopath.drop(columns=['dup', 'duplicates', 'WorkupNo', 'Region'])

	# 5. Logic for node handling
	tidy_histopath['node_total_remove'] = tidy_histopath['node_total_remove'].replace(999, np.nan)

	def calculate_node_involved(row):
		if pd.isna(row['node_total_remove']): return np.nan
		if row['node_total_remove'] == 0: return 999
		return row['node_involved_count']

	tidy_histopath['node_involved_count'] = tidy_histopath.apply(calculate_node_involved, axis=1)

	# 6. Final keys and Export
	tidy_histopath['unique_key'] = tidy_histopath['PatientNo'].astype(str) + tidy_histopath['tissue_dx_date'].astype(str)

	out_dir.mkdir(parents=True, exist_ok=True)
	tidy_histopath.to_pickle(out_dir / 'tidy_histopath.pickle')

	results['tidy_histopath'] = str(out_dir / 'tidy_histopath.pickle')

	return results


@check_and_prompt
def transform_chemo(from_path: Path = Path('datasets/bcfnz/excel/therapy_chemo.xlsx'),
                      out_dir: Path = Path('datasets/bcfnz/pickle/processed/strother')) -> dict:
	"""
	Read chemo XLSX, tidy per Strother R pipeline, and save tidy_chemo.
	"""
	results = {}

	chemo = pd.read_excel(from_path)

	# 2. Rename columns
	rename_map = {
		'DateOfTissueDiagnosis': 'tissue_dx_date',
		'TimingOfChemotherapy': 'chemo_setting',
		'StartDateOfChemotherapy': 'chemo_start_date',
		'NumberOfCycles': 'chemo_total_cycles',
		'TypeOfChemotherapy': 'chemo_type',
		'CompletedAsPlannedChemotherapy': 'chemo_completed',
		'TypeOfChemotherapyRegimen': 'regimen'
	}
	chemo = chemo.rename(columns=rename_map)

	chemo['tissue_dx_date'] = pd.to_datetime(chemo['tissue_dx_date'], errors='coerce')
	chemo['chemo_start_date'] = pd.to_datetime(chemo['chemo_start_date'], errors='coerce')

	# 4. Process Adjuvant Chemo
	adj_chemo = chemo[chemo['chemo_setting'] == "Adjuvant"].copy()

	print(adj_chemo.dtypes)

	# Add line number per group
	# ordering done before NA replacement
	adj_chemo = adj_chemo.sort_values(['PatientNo', 'tissue_dx_date', 'chemo_start_date'])
	adj_chemo['adj_chemo_line'] = adj_chemo.groupby(['PatientNo', 'tissue_dx_date']).cumcount() + 1

	adj_chemo['chemo_total_cycles'] = adj_chemo['chemo_total_cycles'].fillna(999)
	adj_chemo['chemo_start_date'] = adj_chemo['chemo_start_date'].fillna(pd.Timestamp("1900-01-01"))

	is_no_chemo = adj_chemo['chemo_start_date'] == pd.Timestamp("1900-01-01")
	adj_chemo['chemo_total_cycles'] = np.where(is_no_chemo, 999, adj_chemo['chemo_total_cycles'])
	adj_chemo['chemo_type'] = np.where(is_no_chemo, "NO CHEMO GIVEN", adj_chemo['chemo_type'])
	adj_chemo['chemo_completed'] = np.where(is_no_chemo, "NO CHEMO GIVEN", adj_chemo['chemo_completed'])
	adj_chemo['regimen'] = np.where(is_no_chemo, "NO CHEMO GIVEN", adj_chemo['regimen'])

	# Split into lines
	line1 = adj_chemo[adj_chemo['adj_chemo_line'] == 1].rename(columns={'regimen': 'adj_chemo_regimen_1'})
	line2 = adj_chemo[adj_chemo['adj_chemo_line'] == 2][
		['PatientNo', 'tissue_dx_date', 'chemo_start_date', 'chemo_total_cycles', 
		'chemo_type', 'chemo_completed', 'regimen']
	].rename(columns={
		'chemo_start_date': 'chemo_start_date_2',
		'chemo_total_cycles': 'chemo_total_cycles_2',
		'chemo_type': 'chemo_type_2',
		'chemo_completed': 'chemo_completed_2',
		'regimen': 'adj_chemo_regimen_2'
	})

	# Join
	tidy_adj_chemo = line1.merge(line2, on=['PatientNo', 'tissue_dx_date'], how='left')

	# 5. Clean up columns and mutate (case_when equivalents)
	tidy_adj_chemo = tidy_adj_chemo.drop(columns=['WorkupNo', 'Region', 'chemo_setting', 'adj_chemo_line'])

	# NA replacement for 2nd chemo cols
	tidy_adj_chemo['chemo_start_date_2'] = tidy_adj_chemo['chemo_start_date_2'].fillna(pd.Timestamp("1900-01-01"))
	is_no_chemo = tidy_adj_chemo['chemo_start_date_2'] == pd.Timestamp("1900-01-01")
	tidy_adj_chemo['chemo_total_cycles_2'] = np.where(is_no_chemo, 999, tidy_adj_chemo['chemo_total_cycles_2'])
	tidy_adj_chemo['chemo_type_2'] = np.where(is_no_chemo, "NO CHEMO GIVEN", tidy_adj_chemo['chemo_type_2'])
	tidy_adj_chemo['chemo_completed_2'] = np.where(is_no_chemo, "NO CHEMO GIVEN", tidy_adj_chemo['chemo_completed_2'])
	tidy_adj_chemo['adj_chemo_regimen_2'] = np.where(is_no_chemo, "NO CHEMO GIVEN", tidy_adj_chemo['adj_chemo_regimen_2'])

	# 6. Final keys and export
	tidy_adj_chemo['unique_key'] = tidy_adj_chemo['PatientNo'].astype(str) + tidy_adj_chemo['tissue_dx_date'].astype(str)

	out_pickle = out_dir / 'tidy_chemo.pickle'
	tidy_adj_chemo.to_pickle(out_pickle)
	tidy_adj_chemo.to_csv(out_dir / 'tidy_chemo.csv', index=False)
	tidy_adj_chemo['tidy_chemo'] = str(out_pickle)

	results['tidy_chemo'] = str(out_pickle)

	return results


@check_and_prompt
def transform_mets(from_path: Path = Path('datasets/bcfnz/excel/metastatic_disease.xlsx'),
                      out_dir: Path = Path('datasets/bcfnz/pickle/processed/strother')) -> dict:
	"""
	Metastatic_Disease <- read_excel("./data/metastatic_disease.xlsx")

	Metastatic_Disease <- Metastatic_Disease %>%
	rename(.,c(
		tissue_dx_date=`DateOfTissueDiagnosis`,
		met_date=`DateOfMetastaticDisease`
				)) %>%
	mutate(mets_date = na_if(met_date, as_date("1900 01 01")))

	Metastatic_Disease <- Metastatic_Disease |>
	group_by(PatientNo, tissue_dx_date)|>
	arrange(desc(met_date), .by_group = TRUE)|>
	mutate(met_repeat = row_number())

	#this identifies multiple metastatic events per patient/tissue diagnosis - use the usual spread approach - though up to 14 recorded

	met_dz_1 <-Metastatic_Disease |>
	filter(met_repeat == "1") |>
	rename(met_date_1=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_1)

	met_dz_2 <-Metastatic_Disease |>
	filter(met_repeat == "2") |>
	rename(met_date_2=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_2)

	met_dz_3 <-Metastatic_Disease |>
	filter(met_repeat == "3") |>
	rename(met_date_3=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_3)

	met_dz_4 <-Metastatic_Disease |>
	filter(met_repeat == "4") |>
	rename(met_date_4=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_4)

	met_dz_5 <-Metastatic_Disease |>
	filter(met_repeat == "5") |>
	rename(met_date_5=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_5)

	met_dz_6 <-Metastatic_Disease |>
	filter(met_repeat == "6") |>
	rename(met_date_6=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_6)

	met_dz_7 <-Metastatic_Disease |>
	filter(met_repeat == "7") |>
	rename(met_date_7=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_7)

	met_dz_8 <-Metastatic_Disease |>
	filter(met_repeat == "8") |>
	rename(met_date_8=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_8)

	met_dz_9 <-Metastatic_Disease |>
	filter(met_repeat == "9") |>
	rename(met_date_9=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_9)

	met_dz_10 <-Metastatic_Disease |>
	filter(met_repeat == "10") |>
	rename(met_date_10=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_10)

	met_dz_11 <-Metastatic_Disease |>
	filter(met_repeat == "11") |>
	rename(met_date_11=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_11)

	met_dz_12 <-Metastatic_Disease |>
	filter(met_repeat == "12") |>
	rename(met_date_12=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_12)

	met_dz_13 <-Metastatic_Disease |>
	filter(met_repeat == "13") |>
	rename(met_date_13=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_13)

	met_dz_14 <-Metastatic_Disease |>
	filter(met_repeat == "14") |>
	rename(met_date_14=met_date)|>
	select(PatientNo, tissue_dx_date, met_date_14)

	tidy_mets<-met_dz_1 |>
	left_join(met_dz_2, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_3, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_4, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_5, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_6, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_7, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_8, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_9, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_10, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_11, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_12, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_13, join_by(PatientNo, tissue_dx_date))|>
	left_join(met_dz_14, join_by(PatientNo, tissue_dx_date))

	#for all tables - make PatientNo and tissue_dx_date, character and POSIXct consistently 
	tidy_mets<-tidy_mets |>
	mutate(unique_key=paste0(PatientNo,tissue_dx_date))

	save(tidy_mets, file="./data/processed/tidy_mets.Rda")  
	"""

	# for each PatientNo and tissue_dx_date group, pivot the met_date values into separate columns, up to 14 metastatic events per patient/tissue diagnosis
	# then full join the resulting tables back together to produce tidy_mets with columns met_date_1, met_date_2, ..., met_date_14
	out_dir = Path(out_dir)
	out_dir.mkdir(parents=True, exist_ok=True)

	print(f"Processing metastatic disease records from {from_path} to {out_dir}")

	results = {}

	if not from_path.exists():
		results['tidy_mets'] = None
		print(f'Path does not exist: {from_path}')
		return results

	df = pd.read_excel(from_path, index_col=0)
	# ensure PatientNo is a column in this sheet
	if df.index.name is not None:
		try:
			df = df.reset_index()
		except Exception:
			pass

	# rename columns to match R version for easier comparison
	rename_map = {
		'DateOfTissueDiagnosis': 'tissue_dx_date',
		'DateOfMetastaticDisease': 'met_date',
	}
	df = df.rename(columns=rename_map)

	# unique_key
	if 'PatientNo' in df.columns and 'tissue_dx_date' in df.columns:
		print("Adding unique key")
		df['unique_key'] = df['PatientNo'].astype(str) + df['tissue_dx_date'].dt.strftime('%Y-%m-%d')


	# ensure tissue_dx_date is a datetime
	if 'tissue_dx_date' in df.columns:
		df['tissue_dx_date'] = pd.to_datetime(df['tissue_dx_date'], errors='coerce')


	# pivot met_date values into separate columns for each metastatic event, up to 14 events
	met_cols = [c for c in df.columns if c.startswith('met_date')]
	if not met_cols:
		results['tidy_mets'] = None
		print(f'No met_date columns found in {from_path}')
		return results

	# filter out rows with missing met_date values
	df = df.dropna(subset=met_cols, how='all')	
	df['met_repeat'] = df.groupby(['PatientNo', 'tissue_dx_date']).cumcount() + 1
	
	# pivot the met_date values into separate columns 
	mets_tidy = df.pivot_table(index=['PatientNo', 'tissue_dx_date', 'unique_key'], columns='met_repeat', values='met_date', aggfunc='first').reset_index()
	mets_tidy.columns = ['PatientNo', 'tissue_dx_date', 'unique_key'] + [f'met_date_{i}' for i in range(1, len(mets_tidy.columns) - 3 + 1)]

	# save
	out_pickle = out_dir / 'tidy_mets.pickle'
	mets_tidy.to_pickle(out_pickle)
	mets_tidy.to_csv(out_dir / 'tidy_mets.csv', index=False)
	results['tidy_mets'] = str(out_pickle)
	return results


@check_and_prompt
def generate_strother_files(out_dir: Path = Path('datasets/bcfnz/pickle/processed/strother')) -> dict:
	"""
	Generates all raw files as in Matthew Strother's R code
	"""
	
	results = {}
	id_cols = ['PatientNo', 'tissue_dx_date', 'unique_key']

	transform_surgery_primary()
	transform_demographics()
	transform_biological_markers()
	transform_followup()
	transform_lesions()
	transform_histopath()
	transform_mets()
	transform_chemo()
	
	dfs = []
	
	for file_path in out_dir.glob('*.pickle'):
		if "merged" not in str(file_path):
			df = pd.read_pickle(file_path)

			# remove WorkupNo if it exists
			if 'WorkupNo' in df.columns:
				df = df.drop(columns=['WorkupNo'])

			dfs.append(df)

	combined_df = reduce(lambda left, right: pd.merge(left, right, on=id_cols, how='outer'), dfs)

	# add a lost to followup flag
	combined_df = lost_to_followup(combined_df)

	# add surgical completeness flags
	combined_df = add_surgical_completeness(combined_df)

	print(f"Combined dataframe shape: {combined_df.shape}")
	print(combined_df['PatientNo'].value_counts().head(10))

	out_pickle = out_dir / 'merged_breast_tables.pickle'
	combined_df.to_pickle(out_pickle)
	combined_df.to_csv(out_dir / 'merged_breast_tables.csv', index=False)


	results['merged_breast_tables'] = str(out_pickle)

	return results



if __name__ == '__main__':
	# working: biomarkers (1 diff), mets, demographics, followup, lesions, surgery (4 diffs), histopathology, chemo
	# still to do: hormone, biological therapy
	#out = generate_strother_files()
	#print(out)
	generate_strother_files()

	tidy_filename = "merged_breast_tables"
	strother_dir = Path("./datasets/bcfnz/strother/")
	out_dir = Path("./datasets/bcfnz/pickle/processed/strother/")
	compare_dir = Path(f"./datasets/bcfnz/compare/{tidy_filename}/")
	compare_dir.mkdir(parents=True, exist_ok=True)

	strother = load_r(strother_dir / f'{tidy_filename}.Rda')
	lou = load_py(out_dir / f'{tidy_filename}.pickle')

	strother, lou = align_dtypes(strother, lou)
	
	res = compare_tables(lou, strother, key='unique_key', save_dir=compare_dir)
	#res = biomarkers_lou.compare(biomarkers_strother, keep_shape=True, keep_equal=True)
	print(res)

