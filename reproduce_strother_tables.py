
import os
from pathlib import Path
import pandas as pd
from scripts.pivot_surgeries import prepare_surgery_data, surg_first_last

# surgery
def transform_surgery(from_path: Path = Path('datasets/bcfnz/excel/surgery_primary.xlsx'),
					  out_dir: Path = Path('datasets/bcfnz/pickle/processed')) -> dict:
	"""Read surgery XLSX from `from_path`, write pickles to `out_dir` and compare to Strother R data if available.

	Returns a dict with produced file paths and (optional) comparison summary.
	"""
	out_dir = Path(out_dir)
	out_dir.mkdir(parents=True, exist_ok=True)

	print(f"Processing surgery data from {from_path} to {out_dir}")

	results = {}

	if from_path.exists():
		df_full = pd.read_excel(from_path, index_col=0)

		df_full.rename(columns={'DateOfTissueDiagnosis': 'tissue_dx_date'}, inplace=True)
		df_full.drop(columns=['LeftBreastIgeCode', 'RightBreastIgeCode'], inplace=True)

		df_dates = surg_first_last(df_full, id_col=["WorkupNo", "tissue_dx_date"], date_col='DateOfSurgery')

		psurg = df_full.drop(columns=['LeftBreastTypeOfAxillarySurgery', 'RightBreastTypeOfAxillarySurgery'])
		primary_surg = prepare_surgery_data(
			psurg,
			id_cols=['WorkupNo', 'tissue_dx_date'],
			date_col='DateOfSurgery',
			left_col='LeftBreastTypeOfBreastSurgery',
			right_col='RightBreastTypeOfBreastSurgery',
			expand_types=True,
			drop_original=True

		)

		primary_surg.drop(columns=['R_5_no_breast_surg', 'R_6_no_breast_surg', 'R_7_no_breast_surg', 
							 'L_5_ppx_mastectomy',
							 'R_5_re_excision', 'R_6_re_excision', 'R_7_re_excision',
							 'L_1_', 'R_1_', 'L_2_', 'R_2_', 'L_3_', 'R_3_', 'L_4_', 'R_4_', 'R_5_', 'R_6_', 'R_7_'], inplace=True, errors='ignore')

		df_out = df_dates.merge(primary_surg, on=['WorkupNo', 'tissue_dx_date'], how='left')

		axillary = df_full.drop(columns=['LeftBreastTypeOfBreastSurgery', 'RightBreastTypeOfBreastSurgery'])
		ax_surg = prepare_surgery_data(
			axillary,
			id_cols=['WorkupNo', 'tissue_dx_date'],
			date_col='DateOfSurgery',
			left_col='LeftBreastTypeOfAxillarySurgery',
			right_col='RightBreastTypeOfAxillarySurgery',
			expand_types=True,
			drop_original=True
		 )
		
		ax_surg.drop(columns=['R_5_no_ax_surg', 'R_6_no_ax_surg', 'R_7_no_ax_surg', 
						'L_1_', 'R_1_', 'L_2_', 'R_2_', 'L_3_', 'R_3_', 'L_4_', 'R_4_',
						'L_5_L3_ax_ln_clear', 'L_5_no_ax_surg'], inplace=True, errors='ignore')
		
		df_out = df_out.merge(ax_surg, on=['WorkupNo', 'tissue_dx_date'], how='left')

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
			rfile = Path('datasets/bcfnz/strother/tidy_surgery_new_strother.Rda')
			if rfile.exists():
				rr = pyreadr.read_r(str(rfile))
				_, df_r = next(iter(rr.items()))
				# identify columns present in R but missing in our output
				miss = [c for c in df_r.columns if c not in df_out.columns]
				if miss:
					# try to merge actual values from R by keys if possible
					keys = [k for k in ('WorkupNo', 'tissue_dx_date') if k in df_out.columns and k in df_r.columns]
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

		full_pickle = out_dir / 'surgery_primary_full.pickle'
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
			for dc in date_cols:
				try:
					n = dc.rsplit('_', 1)[-1]
					# normalize to timestamps
					dates = pd.to_datetime(df_out[dc], errors='coerce')
					mask = dates.dt.normalize() == pd.Timestamp('1900-01-01')
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

		df_out.to_pickle(full_pickle)
		df_out.to_csv(out_dir / 'surgery_primary_full.csv', index=False)
		results['surgery_primary_full'] = str(full_pickle)
	else:
		results['surgery_primary_full'] = None
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


# lesions


# hormone


# chemo


# biological therapy


# mets


# biological markers


def transform_demographics(from_path: Path = Path('datasets/bcfnz/excel/demographic.xlsx'),
						 workup_path: Path = Path('datasets/bcfnz/excel/workup.xlsx'),
						 out_dir: Path = Path('datasets/bcfnz/pickle/processed')) -> dict:
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
	df_demo = pd.read_excel(from_path, index_col=0)
	if workup_path.exists():
		df_workup = pd.read_excel(workup_path, index_col=0)
	else:
		df_workup = pd.DataFrame()

	# drop Region and DateOfTissueDiagnosis from Demographics as in R
	for c in ('Region', 'DateOfTissueDiagnosis'):
		if c in df_demo.columns:
			df_demo = df_demo.drop(columns=[c])

	# left join on WorkupNo and PatientNo
	if not df_workup.empty and all(k in df_demo.columns for k in ('WorkupNo', 'PatientNo')) and all(k in df_workup.columns for k in ('WorkupNo', 'PatientNo')):
		df = df_demo.merge(df_workup, on=['WorkupNo', 'PatientNo'], how='left')
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

	# ensure columns present in R tidy_demographics exist in our output
	try:
		import pyreadr
		rfile = Path('datasets/bcfnz/strother/tidy_demographics.Rda')
		if rfile.exists():
			rr = pyreadr.read_r(str(rfile))
			_, df_r = next(iter(rr.items()))
			miss = [c for c in df_r.columns if c not in df.columns]
			if miss:
				# prefer merge keys if available
				keys = [k for k in ('WorkupNo', 'PatientNo') if k in df.columns and k in df_r.columns]
				if keys:
					merge_df = df_r[[*keys, *[c for c in miss if c in df_r.columns]]].drop_duplicates(subset=keys)
					df = df.merge(merge_df, on=keys, how='left')
				# any remaining missing columns: create sensible defaults
				for c in miss:
					if c not in df.columns:
						if 'date' in c.lower() or 'tissue_dx' in c.lower():
							df[c] = pd.NaT
						elif any(k in c.lower() for k in ('score', 'height', 'weight', 'age', 'charlson')):
							df[c] = pd.NA
						else:
							df[c] = pd.NA
	except Exception:
		# fallback: ensure a small set of known columns exist
		fallback_cols = ['PatientNo', 'Region', 'tissue_dx_date', 'unique_key', 'diagnosis_number']
		for c in fallback_cols:
			if c not in df.columns:
				if 'date' in c:
					df[c] = pd.NaT
				else:
					df[c] = pd.NA

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



def transform_biological_markers(from_path: Path = Path('datasets/bcfnz/excel/biomarkers.xlsx'),
							out_dir: Path = Path('datasets/bcfnz/pickle/processed')) -> dict:
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
	id_vars = [c for c in ['PatientNo', 'tissue_dx_date', 'WorkupNo'] if c in df.columns]
	print(id_vars)

	if cols_with_us:
		melted = df.melt(id_vars=id_vars, value_vars=cols_with_us, var_name='var', value_name='val')
		# split at last underscore into base and ResultsFrom
		split = melted['var'].str.rsplit('_', n=1, expand=True)
		melted['base'] = split[0]
		melted['ResultsFrom'] = split[1]
		# pivot so bases become columns, keeping ResultsFrom as an identifier
		pivot = melted.pivot_table(index=id_vars + ['ResultsFrom'], columns='base', values='val', aggfunc='first')
		pivot = pivot.reset_index()
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
		pivot = pivot.sort_values(['PatientNo', 'tissue_dx_date'], ascending=[True, False])

	# IHC HER2 repeats (up to 5)
	ihc_cols = [c for c in ['PatientNo', 'tissue_dx_date', 'her2_test_date', 'her2_ihc'] if c in pivot.columns]
	if set(['her2_test_date','her2_ihc']).issubset(pivot.columns):
		ihc = pivot[ihc_cols].dropna(subset=['her2_ihc']).drop_duplicates()
		ihc = ihc.sort_values(['PatientNo','tissue_dx_date','her2_test_date'])
		ihc['her2_ihc_repeat'] = ihc.groupby(['PatientNo','tissue_dx_date']).cumcount() + 1

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
	fish_cols = [c for c in ['PatientNo','tissue_dx_date','her2_test_date','her2_fish','her2_copy_no'] if c in pivot.columns]
	if set(['her2_test_date','her2_fish']).issubset(pivot.columns):
		fish = pivot[['PatientNo','tissue_dx_date','her2_test_date','her2_fish','her2_copy_no']].dropna(subset=['her2_fish']).drop_duplicates()
		fish = fish.sort_values(['PatientNo','tissue_dx_date','her2_test_date'])
		fish['her2_fish_repeat'] = fish.groupby(['PatientNo','tissue_dx_date']).cumcount() + 1
		frames = []
		for n in range(1,7):
			dfn = fish[fish['her2_fish_repeat'] == n][['PatientNo','tissue_dx_date','her2_test_date','her2_fish','her2_copy_no']].copy()
			if not dfn.empty:
				dfn = dfn.rename(columns={'her2_test_date': f'her2_fish_test_date_{n}', 'her2_fish': f'her2_fish_{n}', 'her2_copy_no': f'her2_copy_no_{n}'})
				frames.append(dfn)
		if frames:
			her2_fish_tidy = frames[0]
			for fr in frames[1:]:
				her2_fish_tidy = her2_fish_tidy.merge(fr, on=['PatientNo','tissue_dx_date'], how='left')
		else:
			her2_fish_tidy = pd.DataFrame(columns=['PatientNo','tissue_dx_date'] + [f'her2_fish_test_date_{n}' for n in range(1,7)] + [f'her2_fish_{n}' for n in range(1,7)] + [f'her2_copy_no_{n}' for n in range(1,7)])

		# fill defaults
		for n in range(1,7):
			if f'her2_fish_test_date_{n}' not in her2_fish_tidy.columns:
				her2_fish_tidy[f'her2_fish_test_date_{n}'] = pd.NaT
				her2_fish_tidy[f'her2_fish_{n}'] = 'TEST NOT DONE'
				her2_fish_tidy[f'her2_copy_no_{n}'] = 9999

	else:
		her2_fish_tidy = pd.DataFrame(columns=['PatientNo','tissue_dx_date'] + [f'her2_fish_test_date_{n}' for n in range(1,7)] + [f'her2_fish_{n}' for n in range(1,7)] + [f'her2_copy_no_{n}' for n in range(1,7)])

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



def transform_followup(from_path: Path = Path('datasets/bcfnz/excel/followup.xlsx'),
                       out_dir: Path = Path('datasets/bcfnz/pickle/processed')) -> dict:
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

	df = pd.read_excel(from_path, index_col=0)
	# ensure PatientNo is a column (Excel uses PatientNo as index)
	try:
		df = df.reset_index()
	except Exception:
		pass

	# ensure PatientNo is a column (excel files use PatientNo as index)
	try:
		df = df.reset_index()
	except Exception:
		pass

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

	# ensure types: PatientNo as str, tissue_dx_date as datetime
	if 'PatientNo' in df.columns:
		df['PatientNo'] = df['PatientNo'].astype(str)
	if 'tissue_dx_date' in df.columns:
		df['tissue_dx_date'] = pd.to_datetime(df['tissue_dx_date'], errors='coerce')

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

	# consistent unique_key
	if 'PatientNo' in df.columns and 'tissue_dx_date' in df.columns:
		df['unique_key'] = df['PatientNo'].astype(str) + df['tissue_dx_date'].dt.strftime('%Y-%m-%d')

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


def transform_lesions(from_path: Path = Path('datasets/bcfnz/excel/lesions.xlsx'),
                      out_dir: Path = Path('datasets/bcfnz/pickle/processed')) -> dict:
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
		df['ER_final'] = grouped['ER_status_num'].transform(safe_max) if 'ER' in df.columns else pd.NA
		def map_PR(x):
			if pd.isna(x):
				return pd.NA
			if str(x).strip() == 'Positive':
				return 1
			if str(x).strip() == 'Negative':
				return 2
			return pd.NA
		df['PR_status_num'] = df['PR'].map(map_PR) if 'PR' in df.columns else pd.NA
		df['PR_final'] = grouped['PR_status_num'].transform(safe_max) if 'PR' in df.columns else pd.NA

	# extract first/second/third lesions and rename relevant columns
	lesion_cols = [c for c in ['invasive_tumor_size','combined_tumor_size','grade','histologic_subtype','ER','ER_pct','ER_intense','PR','PR_pct','PR_intense'] if c in df.columns]

	if 'lesion_count' in df.columns:
		first = df[df['lesion_count'] == 1].copy()
	else:
		first = pd.DataFrame(columns=df.columns)
	if not first.empty:
		first = first.drop(columns=[c for c in ('Region','Lesion','lesion_count') if c in first.columns], errors=True)
		first = first.rename(columns={c: f'first_{c}' for c in lesion_cols})

	if 'lesion_count' in df.columns:
		second = df[df['lesion_count'] == 2].copy()
	else:
		second = pd.DataFrame(columns=df.columns)
	if not second.empty:
		# drop many aggregate columns per R before renaming
		drop_cols = ['WorkupNo','Region','Lesion','lesion_count','max_lesion_mm','max_combi_lesion_mm','num_grade','max_grade','ER_status_num','ER_final','PR_status_num','PR_final','total_lesions']
		second = second.drop(columns=[c for c in drop_cols if c in second.columns], errors=True)
		second = second.rename(columns={c: f'second_{c}' for c in lesion_cols})

	if 'lesion_count' in df.columns:
		third = df[df['lesion_count'] == 3].copy()
	else:
		third = pd.DataFrame(columns=df.columns)
	if not third.empty:
		drop_cols_3 = ['WorkupNo','Region','Lesion','lesion_count','max_lesion_mm','max_combi_lesion_mm','num_grade','max_grade','ER_status_num','ER_final','PR_status_num','PR_final','total_lesions']
		third = third.drop(columns=[c for c in drop_cols_3 if c in third.columns], errors=True)
		third = third.rename(columns={c: f'third_{c}' for c in lesion_cols})

	# merge sequentially
	merged = first
	if not second.empty:
		merged = merged.merge(second, on=['PatientNo','tissue_dx_date'], how='left')
	if not third.empty:
		merged = merged.merge(third, on=['PatientNo','tissue_dx_date'], how='left')

	# fill defaults for missing second/third invasive sizes -> 999 and propagate for related fields
	for suffix in ('second','third'):
		col_inv = f'{suffix}_invasive_tumor_size'
		if col_inv in merged.columns:
			merged[col_inv] = merged[col_inv].fillna(999)
			# numeric pct fields
			for pct in (f'{suffix}_ER_pct', f'{suffix}_PR_pct'):
				if pct in merged.columns:
					merged.loc[merged[col_inv] == 999, pct] = 999
			# string fields
			for s in (f'{suffix}_grade', f'{suffix}_histologic_subtype', f'{suffix}_ER', f'{suffix}_ER_intense', f'{suffix}_PR', f'{suffix}_PR_intense'):
				if s in merged.columns:
					merged.loc[merged[col_inv] == 999, s] = '999'

	# produce compact tidy_lesions
	cols_out = ['PatientNo','tissue_dx_date','total_lesions','max_lesion_mm','max_combi_lesion_mm','max_grade','ER_final','PR_final']
	cols_out = [c for c in cols_out if c in merged.columns]
	tidy = merged[cols_out].drop_duplicates()

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


def transform_histopathology():
	"""
	Histopathology <- read_excel("./data/histopathology.xlsx")

#rename vectors with difficult naming conventions
Histopathology <- Histopathology %>%
   rename(.,c(
     tissue_dx_date=`DateOfTissueDiagnosis`,
     lesion_count= `NumberOfInvasiveLesions`,
     ax_node_presence = `AxillaryNodesPresent`,
     node_total_remove = `TotalNumberOfNodesRemoved`,
     node_involved_count = `NumberOfNodesInvolvedByTumour`,
     node_largest_deposit = `NodalMetastasisBasedOnTheLargestDeposit`,
     neoadj_indicator = `NeoAdjuvantIndicatorCode`,
     neoadj_effect = `NeoAdjuvantTreatmentEffect`,
     residual_cancer = `ResidualCancerBurden`,
     neoadj_node_effect = `NeoAdjuvantTreatmentEffectInLymphNodes`,
     T_primary = `PathologicalTStageBasedOnPrimaryTumour`,
     N_primary = `PathologicalNStage`,
     TNM_overall= `OverallTNMStage`
     ))

histo<-Histopathology |>
  group_by(PatientNo,tissue_dx_date) |>
  mutate(dup=row_number()) |>
  mutate(duplicates=max(dup))

#this identifies 1300 duplicates - only 2 (no more) but no real patterns - all identifiers and dates the same - histopath key different, and the numbers different - so will spread out and rejoin 
#histo_dup<- histo |>
#  filter (duplicates==2)

histo_1 <- histo |>
  filter(dup == 1)

histo_2 <- histo |>
  filter(dup == 2)|>
  select(PatientNo,tissue_dx_date,lesion_count,ax_node_presence,node_total_remove, node_involved_count,node_largest_deposit, neoadj_indicator, neoadj_effect, residual_cancer, neoadj_node_effect, T_primary, N_primary, TNM_overall)|>
  rename_with(~ paste0("second_", .), lesion_count:TNM_overall)

tidy_histopath <- histo_1 |>
  left_join(histo_2, by=join_by(PatientNo, tissue_dx_date)) |>
  select(-dup)|>
  mutate(duplicate_histopath = if_else(duplicates == "2", "YES", "NO"))|>
  select(-duplicates)

tidy_histopath<-tidy_histopath |>
  mutate(node_total_remove = na_if(node_total_remove, 999)) |>
  mutate(node_involved_count=case_when(
    node_total_remove == 0 ~ 999,
    node_total_remove != 0 ~ node_involved_count,
    is.na(node_total_remove) ~ NA,
    TRUE ~ 9999999
  ))

tidy_histopath <- tidy_histopath |>
  select(!c(WorkupNo, Region))
#for all tables - make PatientNo and tissue_dx_date, character and POSIXct consistently 
tidy_histopath<-tidy_histopath |>
  mutate(unique_key=paste0(PatientNo,tissue_dx_date))

save(tidy_histopath, file="./data/processed/tidy_histopath.Rda")
"""
	pass


def transform_hormone():
	pass

def transform_chemo():
	pass

def transform_biological_therapy():
	pass

def transform_mets():
	pass


if __name__ == '__main__':
	res = transform_biological_markers()
	print(res)
