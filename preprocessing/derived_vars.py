import pandas as pd
import numpy as np
import sys
from pathlib import Path

def tumour_size_group_path_stage_groupings(size):
    if pd.isna(size):
        return None
    
    if size <= 20:
        return 1  # corresponds to pT1
    elif size <= 50:
        return 2  # corresponds to pT2
    elif size > 50:
        return 3  # corresponds to pT3
    


def brca_result(row):
    brca_map = {
        'Negative for specific known mutation': 0,
        'Next generation sequencing negative on screening': 0,
        'BRCA2 - positive': 1,
        'BRCA1 - positive': 1,
        'BRCA1 - variant of unknown clinical significance': 9,
        'BRCA2 - variant of unknown clinical significance': 9,
        'Referred - not tested': 9,
        'Referred - result unknown': 9,
        'Unknown': 9,
        'Uninformative result': 9,
        'Not referred': 9
    }

    brca_1 = brca_map.get(row['brca1_result'])
    brca_2 = brca_map.get(row['brca2_result'])

    if brca_1 == 1 or brca_2 == 1:
        result = 1
    elif brca_1 == 0 and brca_2 == 0:
        result = 0
    else:
        result = 9

    return result


def her2_priority_agg(series):
    # Convert to set for fast lookup
    vals = set(series)
    if 1 in vals: return 1
    if 2 in vals: return 2
    if 0 in vals: return 0
    if 9 in vals: return 9
    return None # Or a default value


def her2_result(row):
    """
    0 = negative
    1 = positive
    2 = equivocal
    9 = unknown

    :param row:
    :return:
    """
    fish = row['her2_result_fish']
    ihc = row['her2_result_ihc']

    # positive if:
    # ihc her2 3+
    # or ihc her2 2+ and fish her2 = positive or equivocal?
    # or ihc her2 1+ and fish her2 = positive ?
    if (ihc == 'IHC HER2 3+' and fish != 'FISH HER2 No Amplification (negative)')\
            or (ihc == 'IHC HER2 2+' and fish == 'FISH HER2 Amplified (positive)') \
            or (ihc == 'IHC HER2 2+' and fish == 'FISH HER2 (equivocal)') \
            or (ihc == 'IHC HER2 1+' and fish == 'FISH HER2 Amplified (positive)')\
            or (pd.isna(ihc) and fish == 'FISH HER2 Amplified (positive)') \
            or (ihc == 'IHC HER2 0' and fish == 'FISH HER2 Amplified (positive)'):
        return 1

    # equivocal if:
    # ihc her2 3+ or 2+ and fish negative?
    if (ihc == 'IHC HER2 2+' and fish == 'FISH HER2 No Amplification (negative)')\
            or (ihc == 'IHC HER2 3+' and fish == 'FISH HER2 No Amplification (negative)')\
            or (pd.isna(ihc) and fish == 'FISH HER2 (equivocal)'):
        return 2

    # negative if:
    # ihc her2 1+ and fish negative
    # ihc her2 0 and fish negative
    if (ihc == 'IHC HER2 1+' and fish == 'FISH HER2 No Amplification (negative)')\
            or (ihc == 'IHC HER2 0' and fish == 'FISH HER2 No Amplification (negative)')\
            or (pd.isna(ihc) and fish == 'FISH HER2 No Amplification (negative)')\
            or (ihc == 'IHC HER2 1+' and fish == 'FISH HER2 (equivocal)')\
            or (ihc == 'IHC HER2 0' and fish == 'FISH HER2 (equivocal)'):
        return 0

    if pd.isna(fish):  # when fish her2 result is not known
        if ihc == 'IHC HER2 0':
            return 0
        if ihc == 'IHC HER2 1+' or ihc == 'IHC HER2 2+':
            return 9

    else:
        print(fish, ihc)
        return 99


def binary_neoadj_adj(df):
    df = df.copy()

    value_map = {
        'Not referred - deemed not necessary': False,
        'Yes': True,
        'n/a - treatment for metastatic disease': False,
        'Not referred - patient unfit': False,
        'Other (specify)': False,
        'Referred - deemed not necessary': False,
        'Referred - patient declined': False,
        'Not referred - patient declined': False,
        'Unknown': None,
        'Referred - patient unfit': False,
        'Not yet': False,
    }

    for col in ['neo_rad', 'neo_hormone', 'neo_chemo', 'neo_mab', 'adj_rad']:
        df[f'{col}_binary'] = df[col].map(value_map)

    #df['no_neoadj'] = (df[['neo_rad_binary', 'neo_hormone_binary', 'neo_chemo_binary', 'neo_mab_binary']] == False).all(axis=1)

    return df


def dcis(df):
    """
    T_primary == "is (DCIS)"~ "DCIS", 
    T_primary == "is (LCIS)"~ "DCIS",
    T_primary == "is (Paget's)"~ "DCIS",
    is.na(T_primary) ~ NA,
    TRUE ~ "NOT DCIS")
    """

    conditions = [
    df['T_primary'].isin(["is (DCIS)", "is (LCIS)", "is (Paget's)"]),
    df['T_primary'].isna()
    ]

    # Define the corresponding choices
    choices = [
        "DCIS",
        None
    ]

    # Apply the logic
    # The 'default' argument handles the "TRUE ~" (the catch-all)
    df['dcis'] = np.select(conditions, choices, default="NOT DCIS")

    return df


def days_to_mets(df):
    df = df.copy()

    df['tissue_dx_date'] = pd.to_datetime(df['tissue_dx_date'], errors='coerce')
    df['met_date_1'] = pd.to_datetime(df['met_date_1'], errors='coerce')

    df['days_to_mets'] = (df['met_date_1'] - df['tissue_dx_date']).dt.days

    return df


def lost_to_followup(df):
    df = df.copy()

    # 1. Select columns
    ltfu_1 = df[['PatientNo', 'tissue_dx_date', 'last_fu_date', 'dod']].copy()

    # Ensure dates are datetime objects
    date_cols = ['last_fu_date', 'dod']
    for col in date_cols:
        ltfu_1[col] = pd.to_datetime(ltfu_1[col])

    # 2. LTFU Alive logic
    # Define 2055-01-01 (the "alive" marker)
    alive_marker = pd.Timestamp("2055-01-01")
    final_sweep = pd.Timestamp("2023-06-01")

    ltfu_alive = ltfu_1[ltfu_1['dod'] == alive_marker].copy()
    ltfu_alive['final_sweep'] = final_sweep

    # Calculate difference in days
    ltfu_alive['sweep_to_lastFU'] = (ltfu_alive['final_sweep'] - ltfu_alive['last_fu_date']).dt.days

    # LTFU condition using np.select
    conditions = [
        ltfu_alive['sweep_to_lastFU'] > 1100,
        ltfu_alive['sweep_to_lastFU'] <= 1100,
        ltfu_alive['last_fu_date'].isna()
    ]
    choices = ["YES", "NO", "YES"]
    ltfu_alive['LTFU'] = np.select(conditions, choices, default="PPPP")

    # Final survival sweep condition
    ltfu_alive['final_survival_sweep'] = np.where(ltfu_alive['last_fu_date'].notna(), final_sweep, pd.NaT) # type: ignore

    # 3. LTFU Dead logic
    ltfu_dead = ltfu_1[ltfu_1['dod'] != alive_marker].copy()
    ltfu_dead['LTFU'] = "NO"
    ltfu_dead['final_survival_sweep'] = ltfu_dead['dod']

    # 4. Join and "Unite"
    # In R, unite() merges columns. In Pandas, we can use combine_first 
    # or fillna since the join results in non-overlapping columns.
    ltfu_2 = pd.concat([ltfu_dead, ltfu_alive])
    lftu_final = ltfu_2[['PatientNo', 'tissue_dx_date', 'LTFU', 'final_survival_sweep']]

    final_df = df.merge(lftu_final, on=['PatientNo', 'tissue_dx_date'], how='left')

    return final_df


def nhs_predict_model_vars(df):
    """
    predict R 3.1:
    Calculate benefits of continuing endocrine therapy assuming survival to 5 years

    #' @param age.start.in Patient age in years
    #' @param screen.in Clinically detected = 0, screen detected = 1, unknown = 9
    #' @param size.in Tumour size mm
    #' @param grade.in Tumour grade
    #' @param nodes.in Number positive nodes
    #' @param er.in ER+ = 1, ER- = 0
    #' @param her2.in HER2+ = 1, HER2- = 0, missing = 9
    #' @param ki67.in KI67+ = 1, KI67- = 0, missing = 9
    #' @param pr.in ptogesterone satus PR+ = 1 PR- = 0
    #' @param generation.in Chemo generation 0, 2 or 3 only
    #' @param horm.in Hormone therapy Yes = 1, no = 0
    #' @param traz.in Trastuzumab therapy Yes = 1, no = 0
    #' @param bis.in Bisphosphonate therapy Yes = 1, no = 0
    #' @param radio.in Radiotherapy Yes = 1, no = 0
    #' @param heart.gy.in Number of grays radiation to the heart
    #' @param smoker.in Never/ex = 0, current = 1
    """

    df = df.copy()

    therapy_map = {
        'Yes': 1,
        'Referred - deemed not necessary': 0,
        'Referred - patient declined': 0,
        'Referred - patient unfit': 0,
        'Not referred - deemed not necessary': 0,
        'Not referred - patient declined': 0,
        'Not referred - patient unfit': 0,
        'Not yet': 0,
        'n/a - treatment for metastatic disease': 0,
        'Other (specify)': 0,
        'Unknown': 0,
    }

    smoking_map = {
        'Never smoked': 0,
        'Ex-smoker > 12 months': 0,
        'Current smoker': 1,
        'Ex-smoker < 12 months': 0,
        'Non-smoker exposed to tobacco smoke': 1,  # unsure about this one?
        'Unknown': 0,  # also this one?
    }

    df['age.start.in'] = df['dx_age']

    def screen_detected(referral_source):
        if referral_source == 'BreastScreen Aotearoa' or referral_source == 'Screen detected - non BSA':
            return 1
        elif referral_source in ['A&E after hours', 'Emergency department', 'GP (symptomatic)']:
            return 0
        else:
            return 9
        
    df['screen.in'] = df['referral_source'].apply(screen_detected)
    df['smoker.in'] = df['SmokingStatus'].map(smoking_map).fillna(0)

    print(df['smoker.in'].describe())
          
    df['size.in'] = df['max_lesion_mm']
    df['grade.in'] = df['max_grade']
    df['nodes.in'] = df['node_involved_count']
    df['er.in'] = df['ER_final'].map({1: 1, 2: 0})
    df['pr.in'] = df['PR_final'].map({1: 1, 2: 0})

    def add_her2(df):
        fish_cols = [col for col in df.columns if col.startswith('her2_fish_')]
        fish_map = {
            "FISH HER2 Amplified (positive)": 2,
            "FISH HER2 No Amplification (negative)": 1,
            "FISH HER2 (equivocal)": 3,
        }

        for col in fish_cols:
            df[col] = df[col].map(fish_map, default=9)
        
        ihc_cols = [col for col in df.columns if col.startswith('her2_ihc_')]

        ihc_map = {
            "IHC HER2 0": 1,
            "IHC HER2 1+": 2,
            "IHC HER2 2+": 3,
            "IHC HER2 3+": 4,
        }

        for col in ihc_cols:
            df[col] = df[col].map(ihc_map, default=9)

        df['her2_result_fish'] = df[fish_cols].max(axis=1)
        df['her2_result_ihc'] = df[ihc_cols].max(axis=1)

        def final_her2(row):
            fish = row['her2_result_fish']
            ihc = row['her2_result_ihc']

            if fish == 4 or (fish == 3 and ihc == 2) or (ihc == 2):
                return 1  # positive
            elif fish > 0 or ihc > 0:
                return 0  # negative
            else:
                return 9  # unknown

        df['her2_status'] = df.apply(final_her2, axis=1)
        
        return df


    df = add_her2(df)
    df['her2.in'] = df['her2_status']

    # set all to unknown, as we have very few ki67 results in the dataset
    df['ki67.in'] = 9

    df['horm.in'] = df['adj_hormone'].map(therapy_map, default=9)
    df['radio.in'] = df['adj_rad'].map(therapy_map, default=9)

    def classify_gen(chemo_str):
        if pd.isna(chemo_str):
            return 0
        
        # Normalize string for easier matching
        s = chemo_str.upper()
        
        # 3rd Gen: Any regimen containing BOTH an Anthracycline (A/E/Dox/Epi) AND a Taxane (Pacli/Docetaxel)
        anthracyclines = ['AC', 'EC', 'DOXORUBICIN', 'EPIRUBICIN', 'FEC', 'FAC']
        taxanes = ['PACLITAXEL', 'DOCETAXEL', 'NABPACLITAXEL']
        
        has_anthra = any(drug in s for drug in anthracyclines)
        has_taxane = any(drug in s for drug in taxanes)
        
        if has_anthra and has_taxane:
            return 3
        elif has_anthra:
            return 2
        elif 'TC' in s and 'DOCETAXEL' in s:
            # TC is often grouped separately or as a specific 2nd gen alternative
            return 2
        else:
            return 0

    # Apply to your dataframe
    df['generation.in'] = df['chemo_type'].apply(classify_gen)

    print('size of df', df.shape)

    # for traztusumab and bisphosphonate status, we need to look at hormone and biological therapy records
    def add_traz_and_bisph_status(df):
        df = df.copy()

        bio = pd.read_excel(Path('datasets/bcfnz/excel/therapy_biological.xlsx'))
        bio = bio.assign(
        adj_traz = (bio['TimingOfBiologicalTherapy'] == 'Adjuvant') & (bio['BiologicalTherapy'] == 'Trastuzumab (Herceptin)'),
        ) 

        bio = bio.rename(columns={'DateOfTissueDiagnosis': 'tissue_dx_date'})

        bio = bio[['PatientNo', 'tissue_dx_date', 'adj_traz']]

        adj_traz_per_diag = bio.groupby(['PatientNo', 'tissue_dx_date'])['adj_traz'].any().reset_index()

        df = df.merge(adj_traz_per_diag, on=['PatientNo', 'tissue_dx_date'], how='left')

        df['adj_traz'] = df['adj_traz'].fillna(0)
        
        return df

    df = add_traz_and_bisph_status(df)

    df['traz.in'] = df['adj_traz'].map({True: 1, False: 0}, default=9)
    df['bis.in'] = 0  # i don't think we have this?
    
    print('size of df', df.shape)


    def add_heart_greys_in(df):
        df = df.copy()

        rad = pd.read_excel(Path('datasets/bcfnz/excel/therapy_radio.xlsx'))

        rad = rad.rename(columns={'DateOfTissueDiagnosis': 'tissue_dx_date', 
                                  'Timing Of Radiation Therapy (Neo-adjuvant / Primary / Adjuvant / LRR)': 'timing',
                                  'Total Dose (Neo-adjuvant / Primary / Adjuvant / LRR)': 'dose'})
        
        # replace dose value with NA if 999
        rad['dose'] = np.where(rad['dose'] == 999, 0, rad['dose']) 
        rad['adj_dose'] = np.where(rad['timing'] == 'Adjuvant', rad['dose'], 0)

        # just one per individual case is required
        dose_sums = rad.groupby(['PatientNo', 'tissue_dx_date'])['adj_dose'].sum().reset_index()
        df = df.merge(dose_sums, on=['PatientNo', 'tissue_dx_date'], how='left')

        df['adj_dose'] = df['adj_dose'].fillna(0)

        return df
    
    df = add_heart_greys_in(df)
    df['heart.gy.in'] = df['adj_dose']
    
    # Add tumour size group and path stage group
    df['size_group'] = df['size.in'].apply(tumour_size_group_path_stage_groupings)

    # Add BRCA result
    df['brca_result'] = df.apply(brca_result, axis=1)


    df["dod"] = pd.to_datetime(df["dod"])
    df["tissue_dx_date"] = pd.to_datetime(df["tissue_dx_date"])

    df["days.to.censor"] = (df["final_survival_sweep"]  - df["tissue_dx_date"]).dt.days
    df["days.to.death"] = (df["dod"]  - df["tissue_dx_date"]).dt.days

    df["surv.time.actual"] = df[["days.to.censor", "days.to.death"]].min(axis=1)

    target_date = pd.to_datetime("2055-01-01")
    df["surv.actual"] = np.where(df["dod"] == target_date, 1, 0)

    def add_treatments_given(row):

        result = ''

        if row['radio.in'] == 1:
            result += 'r'

        if row['horm.in'] == 1:
            result += 'h'

        if row['generation.in'] != 0:
            result += 'c'

        if row['traz.in'] == 1:
            result += 't'
        
        if row['bis.in'] == 1:
            result += 'b'

        if result == '':
            result = 's'
    
        return result

    df['treatments.given'] = df.apply(add_treatments_given, axis=1)

    df['tissue_dx_date'] = pd.to_datetime(df['tissue_dx_date'], errors='coerce')
    df['diag.year'] = df['tissue_dx_date'].dt.year


    return df   