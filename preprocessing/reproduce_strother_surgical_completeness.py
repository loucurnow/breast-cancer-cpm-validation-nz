"""
This file contains functions which read in the original Excel files and then 
apply transformations to produce tidy datasets matching the R pipeline used by Strother in their project
The output files are written as pickles and CSVs to `datasets/bcfnz/pickle/processed/strother` and can be compared to the R .Rda files if available.
"""
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from scripts.compare_dataframes import load_py
from preprocessing.derived_vars import binary_neoadj_adj


def surgical_completeness_by_side(df):
	"""
	Inputs: surgical data, adjuvant radiotherapy data

	Rules:
	Prophylactic Mastectomy  | Mastectomy     |  Lumpectomy  (or WLE)   |    Radiation Therapy | Completion Code

	NO                       |  YES           |  X                      |    X                 | COMPLETE   
	NO                       |  NO            |  YES                    |    YES               | COMPLETE  
	NO                       |  NONE RECORDED |  NONE RECORDED          |    YES               | NO_SURG_DATA
	NO                       |  NO            |  YES                    |    NO                | INCOMPLETE
	NO                       |  NA            |  NA                     |    X                 | NA
	YES                      |  NO            |  NO                     |    NO                | PPX_MAST

	Calculate the outcome for each surgery number  (1-4) for each side. Overall status for each side is taken as best of:
	COMPLETE > PPX_MAST > NO_SURG_DATA > INCOMPLETE > NA
	"""
	
	for side in ["L", "R"]:
		mast_cols = []
		ppx_mast_cols = []
		wle_cols = []
		
		for n in range(1,5):
			mast_cols.append(f'{side}_{n}_mastectomy')
			ppx_mast_cols.append(f'{side}_{n}_ppx_mastectomy')
			wle_cols.append(f'{side}_{n}_wle_partial_matectomy')
			wle_cols.append(f'{side}_{n}_lumpectomy_ex_biopsy')

		for maybe_missing in mast_cols + ppx_mast_cols + wle_cols:
			if maybe_missing not in df.columns:
				df[maybe_missing] = 0
			
		completeness_col = f'{side}_breast_final_completion_status'

		df = df.assign(
        any_mastectomy = ((df[mast_cols] == 1).any(axis=1)),
		any_ppx_mastectomy = ((df[ppx_mast_cols] == 1).any(axis=1)),
        any_wle_with_rt = ((df[mast_cols] == 1).any(axis=1) & ((df['adj_rad_binary'] == True))),
		any_wle_no_rt = ((df[mast_cols] == 1).any(axis=1) & ((df['adj_rad_binary'] != True))),
		any_surg_data_excl_ppx_mast = ((df[mast_cols] == 1).any(axis=1) | (df[wle_cols] == 1).any(axis=1))
	    )

		def overall_completeness(row):
			if row['any_mastectomy'] or row['any_wle_with_rt']:
				return "COMPLETE"
			elif not row['any_surg_data_excl_ppx_mast']:
				if row['any_ppx_mastectomy']:
					return "PPX_MAST"
				elif row['adj_rad_binary']:
					return "NO_SURG_DATA"
				elif row['any_wle_no_rt']:
					return "INCOMPLETE"
				else:
					return None
				
		df[completeness_col] = df.apply(overall_completeness, axis=1)

	return df


def surgical_completeness_overall(df):
	"""
	Breast surgery data marked insufficient if:
		- no surgery data
		OR
		- ppx mast on one side but nothing else

		
	Rules based node completeness for nodes used if breast surgery data is insufficient:
		- Complete if total lesions > 0 and adjuvant radiotherapy occurred
		- No breast radiation if total lesions > 0 and adjuvant radiotherapy did not occur
		- Missing breast radiation data if total lesions > 0 and adjuvant radiotherapy = NA
		- Insufficient breast data if total lesions < 1
	"""

	df = df.assign(
		insufficient_breast_surg_data = (
			(df['L_breast_final_completion_status'].isna() | 
			df['L_breast_final_completion_status'].isin(['NO_SURG_DATA', 'PPX_MAST'])) 
			& 
			(df['R_breast_final_completion_status'].isna() | 
			df['R_breast_final_completion_status'].isin(['NO_SURG_DATA', 'PPX_MAST']))
		)
	)
	
	def calc_rule_based_completeness(row):
		if row['insufficient_breast_surg_data'] == True:
			if row['total_lesions'] < 1:
				return "INSUFFICIENT BREAST DATA"
			else:
				if row['adj_rad_binary'] == True:
					return "COMPLETE"
				elif row['adj_rad_binary'] == False:
					return "NO BREAST RADIATION"
				else:
					return "MISSING BREAST RADIATION DATA"
		else:
			return "NOT NEEDED"
		
	df['rules_based_surgical_completion_breast'] = df.apply(calc_rule_based_completeness, axis=1)
	return df


def node_surgery_completeness(df):
	"""
	| L2 OR L3      | SNB &/OR L1 SAMPLE | >2 LNs positive | more than 4 LNs resected | Coding for Completion       |
	| NONE RECORDED | NONE RECORDED      | X               | X                        | NO_SURG_DATA                |
	| NO			| YES 				 | NO 			   | NO						  | INSUFFICIENT_PATH_NODE_INFO |
	| NO            | YES                | YES 			   | X                        | INCOMPLETE_DISSECTION       |
	| NO            | YES                | X               | NO                       | INCOMPLETE_SNB              |
	| NO            | YES                | YES             | YES                      | COMPLETE                    |
	| YES           | X                  | X               | X                        | COMPLETE                    |
	| NA            | NA                 | X               | X                        | NA                          |

	Rules (rewritten for clarity)
	Complete if:
		- L2 or L3 dissection done 
		OR
		- L1 dissection or SNB done, AND total nodes removed >= 4 AND total positive nodes <= 2
	No surg data if:
		- No L1, L2, L3 dissection or SNB recorded
	Incomplete SNB if:
		- L1 dissection or SNB done, AND total nodes removed < 4
	Incomplete dissection if:
		- L1 dissection or SNB done, AND total positive (involved) nodes > 2
	Insufficient path node info if:
		- L1 dissection or SNB done, but NOT(total nodes removed >= 4 and total positive nodes <= 2)
	NA otherwise

	Across all surgeries, the overall status is taken as best of:
	Aggregates all L1/SNB flags simultaneously across all surgeries for each breast side
		Complete > Incomplete dissection > Incomplete SNB > Insufficient path node info > No surgical data > NA
		

	Node surgery data marked insufficient if:
		All values are either no surg data or NA


	Rules based node completeness for nodes used if node surgery data is insufficient:
		- Complete if total nodes removed >= 4 and nodes involved <= 2
		- Incomplete SNB if total nodes removed < 4
		- Incomplete dissection if nodes involved > 2
		- Insufficient node data if total nodes removed is NA
	"""
	for side in ["L", "R"]:
		completeness_col = f'{side}_node_final_completion_status'

		l2_l3_dissection_cols = []
		l1_dissection_snb_cols = []
		
		for n in range(1,5):
			l2_l3_dissection_cols.append(f'{side}_{n}_L2_ax_ln_dissect')
			l2_l3_dissection_cols.append(f'{side}_{n}_L3_ax_ln_clear')
			l1_dissection_snb_cols.append(f'{side}_{n}_L1_ax_ln_samp')
			l1_dissection_snb_cols.append(f'{side}_{n}_snb')

		for maybe_missing in l2_l3_dissection_cols + l1_dissection_snb_cols:
			if maybe_missing not in df.columns:
				df = df.copy()
				df[maybe_missing] = 0

		df = df.assign(
			any_l2_l3 = ((df[l2_l3_dissection_cols] == 1).any(axis=1)),
			any_l1_snb = ((df[l1_dissection_snb_cols] == 1).any(axis=1))
			)
		
		def overall_completeness(row):
			if row['any_l2_l3']:
				return "COMPLETE"
			elif row['any_l1_snb']:
				involved = row['node_involved_count']
				total = row['node_total_remove']
				if total >= 4 and involved <= 2:
					return "COMPLETE"
				elif involved > 2:
					return "INCOMPLETE DISSECTION"
				elif total < 4:
					return "INCOMPLETE_SNB"
				elif not total:
					return "INSUFFICIENT_NODE_DATA"
				else:
					return None
			else:
				return "NO_SURG_DATA"
			
		df[completeness_col] = df.apply(overall_completeness, axis=1)

	df = df.assign(
		insufficient_node_surg_data = (
			(df['L_node_final_completion_status'].isna() | 
			df['L_node_final_completion_status'] == 'NO_SURG_DATA') 
			& 
			(df['R_node_final_completion_status'].isna() | 
			df['R_node_final_completion_status'] == 'NO_SURG_DATA')
		)
	)

	def calc_rule_based_completeness(row):
		if row['insufficient_node_surg_data'] == True:
			removed = row['node_total_remove']
			involved = row['node_involved_count']
			if involved <= 2 and removed >= 4:
				return "COMPLETE"
			elif removed < 4:
				return "INCOMPLETE_SNB"
			elif involved > 2:
				return "INCOMPLETE_DISSECTION"
			elif not removed:
				return "INSUFFICIENT_NODE_DATA"
			return None
		else:
			return "NOT NEEDED"
		
	df['rules_based_surgical_completion_node'] = df.apply(calc_rule_based_completeness, axis=1)

	return df


def add_surgical_data_sufficient(row):
	r_breast = row['R_breast_final_completion_status']
	r_node = row['R_node_final_completion_status']
	l_breast = row['L_breast_final_completion_status']
	l_node = row['L_node_final_completion_status']

	if (r_breast in ['NO_SURG_DATA', 'PPX_MAST'] or pd.isna(r_breast)) and (l_breast in ['NO_SURG_DATA', 'PPX_MAST'] or pd.isna(l_breast)):
		if (r_node == 'NO_SURG_DATA' or pd.isna(r_node)) and (l_node == 'NO_SURG_DATA' or pd.isna(l_node)):
			return 'BREAST AND NODE SURGERY DATA INSUFFICIENT'
		return 'INSUFFICIENT_BREAST_DATA'
	elif (r_node == 'NO_SURG_DATA' or pd.isna(r_node)) and (l_node == 'NO_SURG_DATA' or pd.isna(l_node)):
		return 'INSUFFICIENT_NODE_DATA'
	else:
		return True



def add_surgical_completeness(df, out_dir: Path=Path('datasets/bcfnz/pickle/processed/strother/')):
	df = df.copy()
	df = binary_neoadj_adj(df)

	df = surgical_completeness_by_side(df)
	df = surgical_completeness_overall(df)
	df = node_surgery_completeness(df)

	df['R_locoregional_complete'] = df['R_breast_final_completion_status'] + "," + df['R_node_final_completion_status']
	df['L_locoregional_complete'] = df['L_breast_final_completion_status'] + "," + df['L_node_final_completion_status']
	df['bilat_locoregional_complete'] = df['R_locoregional_complete'] + "," + df['L_locoregional_complete']

	df['surgical_data_sufficient'] = df.apply(add_surgical_data_sufficient, axis=1)

	def primary_locoregional_completion(df):
		# Define the mapping dictionary
		mapping = {
			# Group 1: COMPLETE
			**{val: "COMPLETE" for val in [
				"COMPLETE,COMPLETE,COMPLETE,COMPLETE", "COMPLETE,COMPLETE,COMPLETE,INCOMPLETE_DISSECTION",
				"COMPLETE,COMPLETE,COMPLETE,INCOMPLETE_SNB", "COMPLETE,COMPLETE,COMPLETE,NO_SURG_DATA",
				"COMPLETE,COMPLETE,INCOMPLETE,NO_SURG_DATA", "COMPLETE,COMPLETE,NO_SURG_DATA,NO_SURG_DATA",
				"COMPLETE,COMPLETE,PPX_MAST,COMPLETE", "COMPLETE,COMPLETE,PPX_MAST,NO_SURG_DATA",
				"PPX_MAST,NO_SURG_DATA,COMPLETE,COMPLETE", "PPX_MAST,INCOMPLETE_DISSECTION,COMPLETE,COMPLETE",
				"COMPLETE,NO_SURG_DATA,COMPLETE,COMPLETE", "NO_SURG_DATA,NO_SURG_DATA,COMPLETE,COMPLETE",
				"PPX_MAST,COMPLETE,COMPLETE,COMPLETE", "INCOMPLETE,NO_SURG_DATA,COMPLETE,COMPLETE",
				"PPX_MAST,NO_SURG_DATA,PPX_MAST,COMPLETE", "PPX_MAST,COMPLETE,NO_SURG_DATA,NO_SURG_DATA",
				"PPX_MAST,COMPLETE,COMPLETE,INCOMPLETE_SNB", "PPX_MAST,COMPLETE,PPX_MAST,NO_SURG_DATA"
			]},
			
			# Group 2: INCOMPLETE DISSECTION OR SNB
			**{val: "INCOMPLETE DISSECTION OR SNB" for val in [
				"COMPLETE,INCOMPLETE_DISSECTION,INCOMPLETE,NO_SURG_DATA", "COMPLETE,INCOMPLETE_DISSECTION,NO_SURG_DATA,NO_SURG_DATA",
				"COMPLETE,INCOMPLETE_DISSECTION,PPX_MAST,NO_SURG_DATA", "NO_SURG_DATA,NO_SURG_DATA,COMPLETE,INCOMPLETE_DISSECTION",
				"INCOMPLETE,NO_SURG_DATA,COMPLETE,INCOMPLETE_DISSECTION", "PPX_MAST,NO_SURG_DATA,COMPLETE,INCOMPLETE_DISSECTION",
				"COMPLETE,INCOMPLETE_SNB,COMPLETE,INCOMPLETE_SNB", "COMPLETE,INCOMPLETE_SNB,COMPLETE,NO_SURG_DATA",
				"COMPLETE,INCOMPLETE_SNB,INCOMPLETE,NO_SURG_DATA", "COMPLETE,INCOMPLETE_SNB,NO_SURG_DATA,NO_SURG_DATA",
				"COMPLETE,INCOMPLETE_SNB,PPX_MAST,INCOMPLETE_SNB", "COMPLETE,INCOMPLETE_SNB,PPX_MAST,NO_SURG_DATA",
				"COMPLETE,NO_SURG_DATA,COMPLETE,INCOMPLETE_SNB", "NO_SURG_DATA,NO_SURG_DATA,COMPLETE,INCOMPLETE_SNB",
				"INCOMPLETE,NO_SURG_DATA,COMPLETE,INCOMPLETE_SNB", "PPX_MAST,NO_SURG_DATA,COMPLETE,INCOMPLETE_SNB",
				"PPX_MAST,INCOMPLETE_SNB,INCOMPLETE,NO_SURG_DATA"
			]},
			
			# Group 3: NO RADIATION
			**{val: "NO RADIATION" for val in [
				"INCOMPLETE,COMPLETE,INCOMPLETE,COMPLETE", "INCOMPLETE,COMPLETE,INCOMPLETE,NO_SURG_DATA",
				"INCOMPLETE,COMPLETE,PPX_MAST,NO_SURG_DATA", "INCOMPLETE,NO_SURG_DATA,INCOMPLETE,COMPLETE",
				"PPX_MAST,NO_SURG_DATA,INCOMPLETE,COMPLETE"
			]},
			
			# Group 4: NO RADIATION & INCOMPLETE DISSECTION OR SNB
			**{val: "NO RADIATION & INCOMPLETE DISSECTION OR SNB" for val in [
				"INCOMPLETE,INCOMPLETE_SNB,INCOMPLETE,INCOMPLETE_SNB", "INCOMPLETE,INCOMPLETE_SNB,INCOMPLETE,NO_SURG_DATA",
				"INCOMPLETE,INCOMPLETE_SNB,PPX_MAST,NO_SURG_DATA", "INCOMPLETE,NO_SURG_DATA,INCOMPLETE,INCOMPLETE_DISSECTION",
				"INCOMPLETE,NO_SURG_DATA,INCOMPLETE,INCOMPLETE_SNB"
			]}
		}
		
		# Apply mapping
		df['primary_data_locoregional_completion'] = df['bilat_locoregional_complete'].map(mapping).fillna("REFER TO RULE BASED LOCOREGIONAL COMPLETION")
		
		return df

	def rules_based_locoregional_completion(df):
		# 1. Logic for rules_based_surgical_completion_node
		node_conditions = [
			(df['surgical_data_sufficient'].isin(["INSUFFICIENT_BREAST_DATA", "INSUFFICIENT_NODE_DATA"])) & (df['node_total_remove'] > 3) & (df['node_involved_count'] < 3),
			(df['surgical_data_sufficient'].isin(["INSUFFICIENT_BREAST_DATA", "INSUFFICIENT_NODE_DATA"])) & (df['node_total_remove'] < 4),
			(df['surgical_data_sufficient'].isin(["INSUFFICIENT_BREAST_DATA", "INSUFFICIENT_NODE_DATA"])) & (df['node_total_remove'] < 4) & (df['node_involved_count'] > 2),
			(df['surgical_data_sufficient'].isin(["INSUFFICIENT_BREAST_DATA", "INSUFFICIENT_NODE_DATA"])) & (df['node_total_remove'].isna())
		]

		node_choices = ["COMPLETE", "INCOMPLETE_SNB", "INCOMPLETE_DISSECTION", "INSUFFICIENT_NODE_DATA"]

		df['rules_based_surgical_completion_node'] = np.select(node_conditions, node_choices, default="RULES BASED NOT NEEDED")


		# 2. Logic for rules_based_surgical_completion_breast
		breast_conditions = [
			(df['surgical_data_sufficient'].isin(["INSUFFICIENT_BREAST_DATA", "INSUFFICIENT_NODE_DATA"])) & (df['total_lesions'] > 0) & (df['adj_rad_binary'] == 1),
			(df['surgical_data_sufficient'].isin(["INSUFFICIENT_BREAST_DATA", "INSUFFICIENT_NODE_DATA"])) & (df['total_lesions'] < 1),
			(df['surgical_data_sufficient'].isin(["INSUFFICIENT_BREAST_DATA", "INSUFFICIENT_NODE_DATA"])) & (df['total_lesions'] > 0) & (df['adj_rad_binary'] == 0),
			(df['surgical_data_sufficient'].isin(["INSUFFICIENT_BREAST_DATA", "INSUFFICIENT_NODE_DATA"])) & (df['adj_rad_binary'].isna()) & (df['total_lesions'] > 0)
		]

		breast_choices = ["COMPLETE", "INSUFFICIENT BREAST DATA", "NO BREAST RADIATION", "MISSING BREAST RADIATION DATA"]

		df['rules_based_surgical_completion_breast'] = np.select(breast_conditions, breast_choices, default="RULES BASED NOT NEEDED")


		# 1. Helper masks for the most common list-based checks
		# These represent the repeated 'bilat_locoregional_complete' lists
		list_A = ["NO_SURG_DATA,COMPLETE,NO_SURG_DATA,NO_SURG_DATA", 
				"NO_SURG_DATA,NO_SURG_DATA,NO_SURG_DATA,COMPLETE", 
				"PPX_MAST,NO_SURG_DATA,NO_SURG_DATA,COMPLETE"]
		
		list_B = ["NO_SURG_DATA,INCOMPLETE_SNB,NO_SURG_DATA,NO_SURG_DATA", 
				"NO_SURG_DATA,NO_SURG_DATA,NO_SURG_DATA,INCOMPLETE_SNB"]
		
		list_C = ["COMPLETE,NO_SURG_DATA,INCOMPLETE,NO_SURG_DATA", "COMPLETE,NO_SURG_DATA,NO_SURG_DATA,NO_SURG_DATA",
				"COMPLETE,NO_SURG_DATA,PPX_MAST,NO_SURG_DATA", "INCOMPLETE,NO_SURG_DATA,COMPLETE,NO_SURG_DATA",
				"NO_SURG_DATA,NO_SURG_DATA,COMPLETE,NO_SURG_DATA", "PPX_MAST,NO_SURG_DATA,COMPLETE,NO_SURG_DATA"]
		
		list_D = ["INCOMPLETE,NO_SURG_DATA,INCOMPLETE,NO_SURG_DATA"]

		# 2. Define conditions
		conds = [
			# BREAST SURGERY INSUFFICIENT logic
			(df['surgical_data_sufficient'] == "INSUFFICIENT_BREAST_DATA") & (df['rules_based_surgical_completion_breast'] == "COMPLETE") & (df['bilat_locoregional_complete'].isin(list_A)),
			(df['surgical_data_sufficient'] == "INSUFFICIENT_BREAST_DATA") & (df['rules_based_surgical_completion_breast'] == "COMPLETE") & (df['bilat_locoregional_complete'].isin(list_B)),
			(df['surgical_data_sufficient'] == "INSUFFICIENT_BREAST_DATA") & (df['rules_based_surgical_completion_breast'] == "NO BREAST RADIATION") & (df['bilat_locoregional_complete'].isin(list_A)),
			(df['surgical_data_sufficient'] == "INSUFFICIENT_BREAST_DATA") & (df['rules_based_surgical_completion_breast'] == "NO BREAST RADIATION") & (df['bilat_locoregional_complete'].isin(list_B)),
			(df['surgical_data_sufficient'] == "INSUFFICIENT_BREAST_DATA") & (df['rules_based_surgical_completion_breast'] == "MISSING BREAST RADIATION DATA") & (df['bilat_locoregional_complete'].isin(list_B)),
			
			# NODE SURGERY INSUFFICIENT logic
			(df['surgical_data_sufficient'] == "INSUFFICIENT_NODE_DATA") & (df['rules_based_surgical_completion_node'] == "COMPLETE") & (df['bilat_locoregional_complete'].isin(list_C)),
			(df['surgical_data_sufficient'] == "INSUFFICIENT_NODE_DATA") & (df['rules_based_surgical_completion_node'] == "COMPLETE") & (df['bilat_locoregional_complete'].isin(list_D)),
			(df['surgical_data_sufficient'] == "INSUFFICIENT_NODE_DATA") & (df['rules_based_surgical_completion_node'].isin(["INCOMPLETE_DISSECTION", "INCOMPLETE_SNB"])) & (df['bilat_locoregional_complete'].isin(list_C)),
			(df['surgical_data_sufficient'] == "INSUFFICIENT_NODE_DATA") & (df['rules_based_surgical_completion_node'].isin(["INCOMPLETE_DISSECTION", "INCOMPLETE_SNB"])) & (df['bilat_locoregional_complete'].isin(list_D)),
			(df['surgical_data_sufficient'] == "INSUFFICIENT_NODE_DATA") & (df['rules_based_surgical_completion_node'] == "INSUFFICIENT_NODE_DATA") & (df['bilat_locoregional_complete'].isin(list_C + list_D)),
			
			# BREAST AND NODE INSUFFICIENT logic
			(df['surgical_data_sufficient'] == "BREAST AND NODE SURGERY DATA INSUFFICIENT") & (df['rules_based_surgical_completion_breast'] == "COMPLETE") & (df['rules_based_surgical_completion_node'] == "COMPLETE"),
			(df['surgical_data_sufficient'] == "BREAST AND NODE SURGERY DATA INSUFFICIENT") & (df['rules_based_surgical_completion_breast'] == "COMPLETE") & (df['rules_based_surgical_completion_node'].isin(["INCOMPLETE_DISSECTION", "INCOMPLETE_SNB"])),
			(df['surgical_data_sufficient'] == "BREAST AND NODE SURGERY DATA INSUFFICIENT") & ((df['rules_based_surgical_completion_breast'] == "MISSING BREAST RADIATION DATA") | (df['rules_based_surgical_completion_node'] == "INSUFFICIENT NODE DATA")),
			(df['surgical_data_sufficient'] == "BREAST AND NODE SURGERY DATA INSUFFICIENT") & ((df['rules_based_surgical_completion_breast'] == "NO BREAST RADIATION") | (df['rules_based_surgical_completion_node'] == "COMPLETE")),
			(df['surgical_data_sufficient'] == "BREAST AND NODE SURGERY DATA INSUFFICIENT") & (df['rules_based_surgical_completion_breast'] == "NO BREAST RADIATION") & (df['rules_based_surgical_completion_node'].isin(["INCOMPLETE_DISSECTION", "INCOMPLETE_SNB"])),
			(df['surgical_data_sufficient'] == "INSUFFICIENT NODE PATH TO CLASSIFY")
		]

		# 3. Corresponding results
		results = [
			"COMPLETE", "INCOMPLETE DISSECTION OR SNB", "NO RADIATION", "NO RADIATION & INCOMPLETE DISSECTION OR SNB", "MISSING BREAST RADIATION DATA",
			"COMPLETE", "NO RADIATION", "INCOMPLETE DISSECTION OR SNB", "NO RADIATION & INCOMPLETE DISSECTION OR SNB", "MISSING TOO MUCH DATA FOR LOCOREGIONAL COMPLETION STATUS",
			"COMPLETE", "INCOMPLETE DISSECTION OR SNB", "MISSING TOO MUCH DATA FOR LOCOREGIONAL COMPLETION STATUS", "NO RADIATION", "NO RADIATION & INCOMPLETE DISSECTION OR SNB",
			"MISSING TOO MUCH DATA FOR LOCOREGIONAL COMPLETION STATUS"
		]

		df['rules_based_locoregional_completion'] = np.select(conds, results, default="PPPP")

		return df

	def final_locoregional_completion(df):
		# Define primary conditions as boolean masks for readability
		is_complete = df['primary_data_locoregional_completion'].isin(["COMPLETE", "REFER TO RULE BASED LOCOREGIONAL COMPLETION"])
		is_inc_node = df['primary_data_locoregional_completion'].isin(["INCOMPLETE DISSECTION OR SNB", "REFER TO RULE BASED LOCOREGIONAL COMPLETION"])
		is_inc_rad_node = df['primary_data_locoregional_completion'].isin(["NO RADIATION & INCOMPLETE DISSECTION OR SNB", "REFER TO RULE BASED LOCOREGIONAL COMPLETION"])
		is_inc_rad = df['primary_data_locoregional_completion'].isin(["NO RADIATION", "REFER TO RULE BASED LOCOREGIONAL COMPLETION"])

		# Define rules_based sets
		rb_complete = df['rules_based_locoregional_completion'].isin(["COMPLETE", "PPPP"])
		rb_inc_node = df['rules_based_locoregional_completion'].isin(["INCOMPLETE DISSECTION OR SNB", "PPPP"])
		rb_inc_rad_node = df['rules_based_locoregional_completion'].isin(["NO RADIATION & INCOMPLETE DISSECTION OR SNB", "PPPP"])
		rb_inc_rad = df['rules_based_locoregional_completion'].isin(["NO RADIATION", "PPPP"])

		# Define all conditions
		conditions = [
			is_complete & rb_complete,
			is_inc_node & rb_inc_node,
			is_inc_rad_node & rb_inc_rad_node,
			is_inc_rad & rb_inc_rad,
			(df['primary_data_locoregional_completion'] == "REFER TO RULE BASED LOCOREGIONAL COMPLETION") & 
			(df['rules_based_locoregional_completion'] == "MISSING TOO MUCH DATA FOR LOCOREGIONAL COMPLETION STATUS")
		]

		# Define corresponding choices
		choices = [
			"COMPLETE LOCOREGIONAL THERAPY",
			"INCOMPLETE NODE LOCOREGIONAL THERAPY",
			"INCOMPLETE RADIATION & NODE LOCOREGIONAL THERAPY",
			"INCOMPLETE RADIATION LOCOREGIONAL THERAPY",
			"MISSING TOO MUCH DATA FOR LOCOREGIONAL COMPLETION STATUS"
		]

		# Apply selection
		df['final_locoregional_completion'] = np.select(conditions, choices, default="PPPP")
		
		return df

	df = primary_locoregional_completion(df)
	df = rules_based_locoregional_completion(df)
	df = final_locoregional_completion(df)
	
	return df


if __name__ == '__main__':
	out_dir = Path("./datasets/bcfnz/pickle/processed/strother/")
	combined_df = load_py(out_dir / f'merged_breast_tables.pickle')

	res = add_surgical_completeness(combined_df)
	print(res)
	
