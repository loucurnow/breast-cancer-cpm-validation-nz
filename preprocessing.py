from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from tabulate import tabulate
import numpy as np
import os

from derived_vars import tumour_size_group_path_stage_groupings, brca_result, her2_result, her2_priority_agg


def load_followup_bcfnz():
    if not os.path.isfile(Path('datasets/bcfnz/pickle/processed/followup.pickle')):
        cols = ['patient_no', 'workup_no', 'followup_lrr', 'followup_mets', 'followup_surv',
                'has_second_primary', 'rectime']

        followup = pd.read_pickle(Path('datasets/bcfnz/pickle/unprocessed/followup.pickle'))

        followup.rename(columns={"PatientNo": "patient_no",
                                 "WorkupNo": "workup_no"}, inplace=True)

        def add_disease_status(df: pd.DataFrame) -> pd.DataFrame:
            """
            prefer metastatic,
            """
            col = 'Evidence of disease: type'
            df = df.copy()

            df.loc[df[col].str.contains('Loco-regional recurrence', na=False), 'followup_lrr'] \
                = 1

            df.loc[df[col].str.contains('Metastatic', na=False), 'followup_mets'] \
                = 1

            return df

        followup = add_disease_status(followup)

        followup['followup_surv'] = (
            followup['PatientStatus']
            .map({'Alive': 1, 'Deceased': 0})
            .fillna(9)
        )

        followup['has_second_primary'] = followup['SecondPrimaryCarcinoma'].notna().astype(int)

        cleaned = followup['DateOfDefinitiveDiagnosisOfNewPrimary'].replace(
            r'\s00:00:00$',  # exclude some invalid dates in the data
            pd.NA,
            regex=True
        )

        followup['rectime'] = (
                pd.to_datetime(cleaned, errors='coerce') - followup[
            'DateOfTissueDiagnosis']).dt.days

        followup = followup[cols]

        followup.to_pickle('datasets/bcfnz/pickle/processed/followup.pickle')

    return pd.read_pickle('datasets/bcfnz/pickle/processed/followup.pickle')


def load_treatments_bcfnz():
    if not os.path.isfile(Path('datasets/bcfnz/pickle/processed/treatments.pickle')):
        treatments = load_workup_treatments()

        for t in ['hormone', 'biological', 'chemo', 'radio']:
            therapy_df = pd.read_pickle(Path(f'datasets/bcfnz/pickle/unprocessed/therapy_{t}.pickle'))
            therapy_df = clean_therapy_df(therapy_df, t)

            treatments = treatments.merge(therapy_df, on=['patient_no', 'workup_no'], how='outer')

        treatments.to_pickle('datasets/bcfnz/pickle/processed/treatments.pickle')

    return pd.read_pickle('datasets/bcfnz/pickle/processed/treatments.pickle')


def load_surgery():
    if not os.path.isfile(Path('datasets/bcfnz/pickle/processed/surgery.pickle')):
        surgery = pd.read_pickle(Path('datasets/bcfnz/pickle/unprocessed/surgery_primary.pickle'))

        surgery.rename(columns={"PatientNo": "patient_no",
                                "WorkupNo": "workup_no",
                                "DateOfSurgery": "date_of_primary_surgery",
                                "DateOfTissueDiagnosis": "date_of_tissue_diagnosis"
                                }, inplace=True)

        surgery['date_of_primary_surgery'] = pd.to_datetime(surgery['date_of_primary_surgery'], errors='coerce')
        surgery['date_of_tissue_diagnosis'] = pd.to_datetime(surgery['date_of_tissue_diagnosis'], errors='coerce')

        # time from diagnosis until surgery
        surgery['surgtime'] = (surgery['date_of_primary_surgery'] - surgery['date_of_tissue_diagnosis']).dt.days

        # check duplicates of id cols
        id_cols = ["patient_no", "workup_no", "date_of_primary_surgery", "date_of_tissue_diagnosis"]
        value_cols = [
            "LeftBreastTypeOfAxillarySurgery",
            "RightBreastTypeOfAxillarySurgery",
            "LeftBreastTypeOfBreastSurgery",
            "RightBreastTypeOfBreastSurgery",
            "LeftBreastIgeCode",
            "RightBreastIgeCode"
        ]

        # pivot wide to long to a
        # split side + variable
        ids = surgery[id_cols]
        surg = surgery[value_cols].copy()
        col_split = surg.columns.str.extract(
            r'^(Left|Right)Breast(.*)'
        )

        surg.columns = pd.MultiIndex.from_arrays(
            [col_split[0].str.lower(), col_split[1]],
            names=["breast_side", "variable"]
        )

        # reshape
        long = (
            surg.stack("breast_side")
                .reset_index()
                .rename(columns={"level_0": "row_id"})
        )

        # add IDs back
        long = long.join(ids, on="row_id")

        # reorder columns
        long = long[
            id_cols
            + ["breast_side", "TypeOfBreastSurgery", "TypeOfAxillarySurgery", "IgeCode"]
        ]

        long.rename(columns={"TypeOfBreastSurgery": "surgery_type",
                             "TypeOfAxillarySurgery": "axillary_surgery_type",
                             "IgeCode": "ige_code"}, 
                             inplace=True)

        long.dropna(subset=['surgery_type', 'axillary_surgery_type', 'ige_code'], how='all', inplace=True)

        long['mastectomy'] = np.where(long['surgery_type'] == 'Mastectomy', 1, 0)
        long['mastectomy_prophylactic'] = np.where(long['surgery_type'] == 'Prophylactic mastectomy', 1, 0)
        long['lumpectomy'] = np.where(long['surgery_type'] == 'Lumpectomy / excision biopsy', 1, 0)
        long['wle'] = np.where(long['surgery_type'] == 'WLE / partial mastectomy', 1, 0)
        long['hookwire'] = np.where(long['surgery_type'] == 'Hookwire localisation excision', 1, 0)
        long['reexcision'] = np.where(long['surgery_type'] == 'Re-excision', 1, 0)

        long['sentinel_node_biopsy'] = np.where(long['axillary_surgery_type'] == 'Sentinel node biopsy', 1, 0)
        long['ax_level_1'] = np.where(long['axillary_surgery_type'] == 'Level 1 (axillary node sample)', 1, 0)
        long['ax_level_2'] = np.where(long['axillary_surgery_type'] == 'Level 2 (axillary node dissection)', 1, 0)
        long['ax_level_3'] = np.where(long['axillary_surgery_type'] == 'Level 3 (axillary node clearance)', 1, 0)

        long['diagnosis_to_surgery'] = (long['date_of_primary_surgery'] - long['date_of_tissue_diagnosis']).dt.days
        long['diagnosis_to_first_surgery'] = long.groupby(['patient_no', 'workup_no', 'breast_side'])['diagnosis_to_surgery'].transform('min')

        # save full surgery information
        long.drop(columns=['surgery_type',
                           'axillary_surgery_type'], inplace=True)
        long.to_pickle('datasets/bcfnz/pickle/processed/surgery_primary_full.pickle')

        # aggregate to one workup per row for model input. show if each surgery type happened, ignore dates
        long.drop(columns=['date_of_tissue_diagnosis',
                           'date_of_primary_surgery'], inplace=True)
        columns_to_max = [
            'mastectomy', 'mastectomy_prophylactic', 'lumpectomy', 'wle',
            'hookwire', 'reexcision', 'sentinel_node_biopsy',
            'ax_level_1', 'ax_level_2', 'ax_level_3', 'diagnosis_to_first_surgery'
        ]
        aggregated_df = long.groupby(['patient_no', 'workup_no', 'breast_side'])[columns_to_max].max().reset_index()

        aggregated_df.drop_duplicates(inplace=True)

        aggregated_df.to_pickle('datasets/bcfnz/pickle/processed/surgery.pickle')
        aggregated_df.to_csv('datasets/bcfnz/excel/surgery_primary_agg.csv')

    return pd.read_pickle(Path('datasets/bcfnz/pickle/processed/surgery.pickle'))


def load_workup_treatments():
    cols = ['workup_no', 'patient_no',
            'neoadj_radiation', 'neoadj_chemo', 'neoadj_biological', 'neoadj_hormone',
            'adj_radiation', 'adj_chemo', 'adj_biological', 'adj_hormone',
            'ovarian_ablation']

    df = pd.read_pickle(Path('datasets/bcfnz/pickle/unprocessed/workup.pickle'))

    df.rename(columns={"PatientNo": "patient_no",
                       "WorkupNo": "workup_no",
                       "AnyCancerTreatment": "had_treatment"}, inplace=True)

    # neo-adjuvant therapies
    df['neoadj_radiation'] = df['PrimaryOrNeoAdjuvantRadiationTherapy'].apply(
        lambda x: workup_therapy_map(x)
    )

    df['neoadj_chemo'] = df['NeoAdjuvantChemotherapy'].apply(
        lambda x: workup_therapy_map(x)
    )
    df['neoadj_biological'] = df['NeoAdjuvantBiologicalTherapy'].apply(
        lambda x: workup_therapy_map(x)
    )
    df['neoadj_hormone'] = df['PrimaryOrNeoAdjuvantHormoneTherapy'].apply(
        lambda x: workup_therapy_map(x)
    )
    # adjuvant therapies
    df['adj_radiation'] = df['AdjuvantRadiationTherapy'].apply(
        lambda x: workup_therapy_map(x)
    )
    df['adj_chemo'] = df['AdjuvantChemotherapy'].apply(
        lambda x: workup_therapy_map(x)
    )
    df['adj_biological'] = df['AdjuvantBiologicalTherapy'].apply(
        lambda x: workup_therapy_map(x)
    )
    df['adj_hormone'] = df['AdjuvantHormoneTherapy'].apply(
        lambda x: workup_therapy_map(x)
    )
    df['ovarian_ablation'] = df['OvarianAblation'].apply(
        lambda x: workup_therapy_map(x)
    )

    df = df[cols]

    return df


def clean_therapy_df(df, therapy_type: str):
    therapy_type = therapy_type.lower()

    if therapy_type not in ('biological', 'hormone', 'radio', 'chemo'):
        raise ValueError("therapy_type must be one of 'biological', 'hormone', 'radio', 'chemo'")

    rename_map = {
        r'PatientNo': 'patient_no',
        r'WorkupNo': 'workup_no',
        r'StartDateBiologicalTherapy': 'start_date_bio',
        r'StopDateBiologicalTherapy': 'stop_date_bio',
        r'TimingOfBiologicalTherapy': 'timing_bio',
        r'BiologicalTherapy': 'therapy_name_bio',
        r'StartDateOfChemotherapy': 'start_date_chemo',
        r'TimingOfChemotherapy': 'timing_chemo',
        r'TypeOfChemotherapy': 'type_chemo',
        r'TypeOfChemotherapyRegimen': 'regimen_type_chemo',
        r'CompletedAsPlannedChemotherapy': 'completed_chemo',
        r'NumberOfCycles': 'cycles_chemo',
        r'StartDateOfHormoneTherapy': 'start_date_hormone',
        r'StopDateHormoneTherapy': 'stop_date_hormone',
        r'TimingOfHormoneTherapy': 'timing_hormone',
        r'HormoneTherapy': 'therapy_name_hormone',
        r'DiscontinuedHormoneTherapy': 'discontinued_hormone'
    }

    df = df.rename(columns=rename_map)

    df['DateOfTissueDiagnosis'] = pd.to_datetime(df['DateOfTissueDiagnosis'], errors='coerce')

    if therapy_type == 'biological':
        df['bio_in'] = 1
        df['start_date_bio'] = pd.to_datetime(df['start_date_bio'], errors='coerce')
        df['diagnosis_to_treatment_bio'] = (df['start_date_bio'] - df['DateOfTissueDiagnosis']).dt.days

    elif therapy_type == 'hormone':
        df["hormone_in"] = 1
        df['start_date_hormone'] = pd.to_datetime(df['start_date_hormone'], errors='coerce')
        df['diagnosis_to_treatment_hormone'] = (df['start_date_hormone'] - df['DateOfTissueDiagnosis']).dt.days

    elif therapy_type == 'chemo':
        df["chemo_in"] = 1
        df['start_date_chemo'] = pd.to_datetime(df['start_date_chemo'], errors='coerce')
        df['diagnosis_to_treatment_chemo'] = (df['start_date_chemo'] - df['DateOfTissueDiagnosis']).dt.days

        # update the completed_chemo column
        df['completed_chemo'] = df['completed_chemo'].astype(str).str.lower().str.strip()

        # YES
        df['completed_chemo_yes'] = df['completed_chemo'].str.contains(r'\byes\b', na=False)

        # NO - DISEASE PROGRESSION
        df['completed_chemo_no_disease_progression'] = df['completed_chemo'].str.contains('disease progression', na=False)

        # NO - PATIENT REQUEST
        df['completed_chemo_no_patient_request'] = df['completed_chemo'].str.contains('patient’s request|patient request', na=False)

        # NO - TOXICITY (Includes Hospitalisation OR Stopped for Toxicity OR the paclitaxel/peripheral neuropathy note)
        df['completed_chemo_no_toxicity'] = df['completed_chemo'].str.contains(
            'toxicity|hospitalisation|neuropathy|peripheral|toxicity|reaction', na=False
        )

        # NO - PATIENT DEATH
        df['completed_chemo_no_patient_death'] = df['completed_chemo'].str.contains('died|death|deceased', na=False)

        # DOSE ADJUSTED
        df['completed_chemo_dose_adjusted'] = df['completed_chemo'].str.contains('dose adjusted', na=False)

        # 3. Create an 'OTHER' flag for the ones that don't fit any of the above (like the abscess note)
        # This finds rows that aren't NaN/None but didn't trigger any of our specific flags
        known_columns = [
            'completed_chemo_yes', 'completed_chemo_no_disease_progression',
            'completed_chemo_no_patient_request', 'completed_chemo_no_toxicity',
            'completed_chemo_no_patient_death', 'completed_chemo_dose_adjusted'
        ]

        # If none of the flags are True AND the original value wasn't 'nan'
        df['completed_chemo_other'] = (~df[known_columns].any(axis=1)) & (df['completed_chemo'] != 'nan')

        # 4. Optional: Convert True/False to 1/0 for cleaner pivoting later
        df[known_columns + ['completed_chemo_other']] = df[known_columns + ['completed_chemo_other']].astype(int)

        # drop the original completed_chemo column
        df = df.drop(columns=["completed_chemo"])

        df = add_chemo_generations(df)
        # drop the original column now
        df = df.drop(columns=['type_chemo'])

    elif therapy_type == 'radio':
        df.columns = (
            df.columns
                .str.replace(r"Timing Of Radiation Therapy.*", "timing_radio", regex=True)
                .str.replace(r"Total Dose.*", "total_dose_radio", regex=True)
                .str.replace(r"Radiation Type.*", "type_radio", regex=True)
        )
        df["radio_in"] = 1

    # drop the region and dateoftissuediagnosis columns
    df = df.drop(columns=["DateOfTissueDiagnosis", "Region"])

    return df


def add_chemo_generations(df):
    df = df.copy()

    # 1. Standardize the column to lowercase for robust matching
    df['type_chemo'] = df['type_chemo'].astype(str).str.lower()

    # 2. Define the Generation Mappings using Regex
    # Generation 1: CMF variants
    gen1_pattern = 'cmf|cyclophosphamide \(cp\) - oral'

    # Generation 2: Anthracyclines (A/E drugs)
    gen2_pattern = 'ac and/or ec|doxorubicin|epirubicin|fac|fec|^fe$|pld|lipsomal'

    # Generation 3: Taxanes & Platinums (T/C drugs)
    gen3_pattern = 'docetaxel|paclitaxel|carboplatin|nabpaclitaxel|^at$|tc|tch'

    # Other/Salvage:
    gen_other_pattern = 'capecitabine|gemcitabine|vinorelbine|eribulin|other'

    # 3. Create the flags
    df['type_chemo_gen_1'] = df['type_chemo'].str.contains(gen1_pattern, na=False).astype(int)
    df['type_chemo_gen_2'] = df['type_chemo'].str.contains(gen2_pattern, na=False).astype(int)
    df['type_chemo_gen_3'] = df['type_chemo'].str.contains(gen3_pattern, na=False).astype(int)
    df['type_chemo_gen_other'] = df['type_chemo'].str.contains(gen_other_pattern, na=False).astype(int)

    # 4. Handle 'Unknown' specifically
    df['type_chemo_unknown'] = df['type_chemo'].str.contains('unknown', na=False).astype(int)

    return df


def process_demographics():
    cols = ['patient_no', 'workup_no',
            'ethnicity', 'gender', 'region', 'diagnosis_age',
            'brca', 'diagnosis_year', 'surv', 'survtime',
            'death_cause', 'death_cause_verified', 'death_icd_code']

    if not os.path.isfile(Path('datasets/bcfnz/pickle/processed/demographics.pickle')):
        demographics = pd.read_pickle(f"datasets/bcfnz/pickle/unprocessed/demographics.pickle")

        demographics.rename(columns={"PatientNo": "patient_no",
                                     "WorkupNo": "workup_no",
                                     "Ethnicity (Level 1)": "ethnicity",
                                     "Gender": "gender",
                                     "Region": "region",
                                     "Age At Diagnosis": "diagnosis_age"}, inplace=True)

        demographics['brca'] = demographics.apply(brca_result, axis=1).astype("category")
        # print(demographics["brca"].value_counts())
        # 43009 = unknown or not tested
        # 1647 = tested & negative
        # 459 = tested & positive

        demographics['diagnosis_year'] = demographics['DateOfTissueDiagnosis'].dt.year
        demographics['surv'] = demographics["Current Patient Status"].apply(
            lambda x:
            1 if x == 'Alive' else
            0 if x == "Dead"
            else 9)

        demographics['survtime'] = (demographics['Date Of Death'] - demographics['DateOfTissueDiagnosis']).dt.days

        demographics['death_cause'] = demographics['Cause Of Death'].apply(
            lambda x:
            1 if x == 'Breast cancer' else
            2 if x == 'Other' else
            9 if x == 'Unknown' else
            None
        )
        demographics['death_cause_verified'] = demographics['Cause Of Death Verified By MOH'].apply(
            lambda x:
            1 if x == 'Yes' else
            0 if x == 'No' else
            None
        )
        demographics['death_icd_code'] = demographics['ICDCodeOfTheCauseOfDeath'].str.lower()

        demographics = demographics[cols]

        demographics.to_pickle("datasets/bcfnz/pickle/processed/demographics.pickle")

    return pd.read_pickle("datasets/bcfnz/pickle/processed/demographics.pickle")


def process_workup():
    if not os.path.isfile(Path('datasets/bcfnz/pickle/processed/workup.pickle')):
        cols = ['patient_no', 'workup_no', 'invasive',
                'metastatic', 'primary_surgery', 'symptomatic',
                'referral_source', 'pregnancy_current_or_recent', 'post_menopausal',
                'previous_surgery_breast_cancer',
                'smoker', 'height', 'weight',
                'ecog', 'charlson_comorbidities', 'charlson_comorbidity_score']

        workup = pd.read_pickle(Path('datasets/bcfnz/pickle/unprocessed/workup.pickle'))

        workup.rename(columns={"PatientNo": "patient_no",
                               "WorkupNo": "workup_no",
                               "CharlsonComorbidityScore": 'charlson_comorbidity_score',
                               "CharlsonComorbidities": "charlson_comorbidities"}, inplace=True)

        """
        DiagnosisType
        Invasive & in situ    19161
        Invasive              17329
        In situ                 494
        Unknown                  66
        """
        workup['invasive'] = workup['DiagnosisType'].apply(lambda x:
                                                           1 if x == 'Invasive & in situ' or x == 'Invasive'
                                                           else 0)

        workup['metastatic'] = workup['MetastaticDisease'].apply(lambda x:
                                                                 1 if x == 'Yes'
                                                                 else 0 if x == 'No'
                                                                 else 9)

        workup['primary_surgery'] = workup['PrimarySurgery'].apply(lambda x:
                                                                   1 if x == 'Yes'
                                                                   else 0 if x == 'No'
                                                                   else 9)

        workup['symptomatic'] = workup['DidThePatientPresentWithSymptomsAtTimeOfReferral'].apply(lambda x:
                                                                                                 1 if x == 'Yes'
                                                                                                 else 0 if x == 'No'
                                                                                                 else 9)

        workup['referral_source'] = workup['SourceOfReferral'].apply(
            lambda x:
            0 if x == 'BreastScreen Aotearoa' or x == 'Screen detected - non BSA'
            else 1 if x == 'GP (symptomatic)'
            else 9 if x == 'Unknown'
            else 3
        )

        workup['previous_surgery_breast_cancer'] = workup['PreviousBreastCancerSurgery'].apply(
            lambda x:
            1 if x == 'Same breast' or x == 'Both breasts'
            else 2 if x == 'Contralateral breast'
            else None
        )

        workup['ECOGStatus'] = workup.ECOGStatus.str.extract(r"(\d+)")
        workup['ecog'] = workup.ECOGStatus.apply(lambda x: 9 if x == 99 else x).fillna(9)

        workup['height'] = workup['HeightAtDiagnosis'].apply(lambda x:
                                                             None if x >= 999 else x)

        workup['weight'] = workup['WeightAtDiagnosis'].apply(lambda x:
                                                             None if x >= 999 or x < 25 else x)

        workup['post_menopausal'] = workup['MenopausalStatus'].apply(
            lambda x:
            1 if x == 'Post-menopausal'
            else 0 if x == 'Pre-menopausal' or x == 'Peri-menopausal'
            else 9
        )

        workup['pregnancy_current_or_recent'] = workup['GestationalStatusAtDiagnosis'].apply(
            lambda x:
            1 if x == 'Currently pregnant' or x == 'Recently pregnant'
            else 0
        )

        workup['smoker'] = workup['SmokingStatus'].apply(
            lambda x:
            1 if x == 'Current smoker' or x == 'Ex-smoker < 12 months'
            else 0 if x == 'Never smoked' or x == 'Ex-smoker > 12 months'
            else 9
        )

        workup = workup[cols]

        workup.to_pickle(Path('datasets/bcfnz/pickle/processed/workup.pickle'))

    return pd.read_pickle("datasets/bcfnz/pickle/processed/workup.pickle")


def process_biomarkers():
    if not os.path.isfile(Path('datasets/bcfnz/pickle/processed/biomarkers.pickle')):
        biomarkers = pd.read_pickle(Path('datasets/bcfnz/pickle/unprocessed/biomarkers.pickle'))

        cols = ['patient_no', 'workup_no',
                'her2_result', 'ki67_result', 'oncotypedx_result'
                ]

        biomarkers.rename(columns={"PatientNo": "patient_no",
                                   "WorkupNo": "workup_no"}, inplace=True)

        # her2 result chosen based off histopathology if available, then core biopsy, then FNA, then other
        biomarkers['her2_result_ihc'] = biomarkers['ResultOfIHCHer2Testing_Histopathology']. \
            fillna(biomarkers['ResultOfIHCHer2Testing_CoreBiopsy']). \
            fillna(biomarkers['ResultOfIHCHer2Testing_FNA']).fillna(biomarkers['ResultOfIHCHer2Testing_Other'])

        biomarkers['her2_result_fish'] = biomarkers['ResultOfFishHer2Testing_Histopathology']. \
            fillna(biomarkers['ResultOfFishHer2Testing_CoreBiopsy']). \
            fillna(biomarkers['ResultOfFishHer2Testing_FNA']).fillna(biomarkers['ResultOfFishHer2Testing_Other'])

        biomarkers['her2_result_per_test'] = biomarkers.apply(her2_result, axis=1)
        biomarkers['her2_result'] = biomarkers.groupby(['patient_no', 'workup_no'])['her2_result_per_test'].transform(her2_priority_agg)

        biomarkers['her2_copies'] = biomarkers['NumberOfCopiesOfHer2_Histopathology']. \
            fillna(biomarkers['NumberOfCopiesOfHer2_CoreBiopsy']). \
            fillna(biomarkers['NumberOfCopiesOfHer2_FNA']).fillna(biomarkers['NumberOfCopiesOfHer2_Other'])

        biomarkers['ki67_result_per_test'] = biomarkers['Ki67Result_Histopathology']. \
            fillna(biomarkers['Ki67Result_CoreBiopsy']). \
            fillna(biomarkers['Ki67Result_FNA']).fillna(biomarkers['Ki67Tested_Other'])
        biomarkers['ki67_result'] = biomarkers.groupby(['patient_no', 'workup_no'])['ki67_result_per_test'].transform('max')


        biomarkers['oncotypedx_result'] = biomarkers['OncotypeDx_Histopathology']. \
            fillna(biomarkers['OncotypeDx_CoreBiopsy']). \
            fillna(biomarkers['OncotypeDx_FNA']).fillna(biomarkers['OncotypeDx_Other'])

        biomarkers = biomarkers[cols]
        biomarkers = biomarkers.drop_duplicates()
        biomarkers.to_csv(Path('datasets/bcfnz/excel/biomarkers_partial.csv'))

        biomarkers.to_pickle(Path('datasets/bcfnz/pickle/processed/biomarkers.pickle'))
    return pd.read_pickle(Path('datasets/bcfnz/pickle/processed/biomarkers.pickle'))


def process_lesions():
    if not os.path.isfile(Path('datasets/bcfnz/pickle/processed/lesions.pickle')):
        cols = ['patient_no', 'workup_no', 'bilateral_synchronous',
                'invasive_tumour_size', 'combined_tumour_size',
                'histological_grade', 'er_status_histopathology', 'pr_status_histopathology']

        lesions = pd.read_pickle(Path('datasets/bcfnz/pickle/unprocessed/lesions.pickle'))

        lesions.rename(columns={"PatientNo": "patient_no",
                                "WorkupNo": "workup_no"}, inplace=True)

        lesions['bilateral_synchronous'] = lesions['BilateralSynchronousBreastCancer'].apply(
            lambda x:
            1 if x == 'Yes'
            else 0 if x == 'No'
            else 9
        )
        lesions['invasive_tumour_size'] = lesions['InvasiveTumourSize']
        lesions['combined_tumour_size'] = lesions['CombinedTumourSize']
        lesions['histological_grade'] = lesions['HistologicalInvasiveCancerGrade'].apply(
            lambda x:
            9 if x == 'Unknown / not assessable'
            else x
        )

        lesions['er_status_histopathology'] = lesions['HP Oestrogen Result'].apply(
            lambda x:
            1 if x == 'Positive'
            else 0 if x == 'Negative'
            else 9
        )

        lesions['pr_status_histopathology'] = lesions['HP Progesterone result'].apply(
            lambda x:
            1 if x == 'Positive'
            else 0 if x == 'Negative'
            else 9
        )

        lesions = lesions[cols]
        lesions = lesions.drop_duplicates()

        lesions.to_pickle(Path('datasets/bcfnz/pickle/processed/lesions.pickle'))
    return pd.read_pickle(Path('datasets/bcfnz/pickle/processed/lesions.pickle'))


def process_mets():
    if not os.path.isfile(Path('datasets/bcfnz/pickle/processed/metastatic_disease.pickle')):
        cols = ['patient_no', 'workup_no', 'metstime']

        mets = pd.read_pickle(Path('datasets/bcfnz/pickle/unprocessed/metastatic_disease.pickle'))

        mets.rename(columns={"PatientNo": "patient_no",
                             "WorkupNo": "workup_no",
                             "DateOfMetastaticDisease": "date_mets",
                             "DateOfTissueDiagnosis": "date_of_tissue_diagnosis"}, inplace=True)

        mets['metstime'] = (mets['date_mets'] - mets['date_of_tissue_diagnosis']).dt.days

        # keep only the first mets record per workup
        mets_sorted = mets.sort_values(by=['workup_no', 'date_mets'])
        mets_first = mets_sorted.groupby('workup_no').first().reset_index()

        mets_first = mets_first[cols]

        mets_first.to_pickle(Path('datasets/bcfnz/pickle/processed/metastatic_disease.pickle'))
    return pd.read_pickle(Path('datasets/bcfnz/pickle/processed/metastatic_disease.pickle'))


def treatments_one_row_per_workup():
    df = load_treatments_bcfnz()

    # 1. Identify Categorical Columns
    standard_cat_cols = [
        'timing_hormone', 'therapy_name_hormone', 'discontinued_hormone',
        'timing_bio', 'therapy_name_bio', 'timing_chemo',
        'regimen_type_chemo', 'timing_radio', 'type_radio'
    ]

    # 2. Process Standard Categorical Columns
    df_standard_bins = pd.get_dummies(df[standard_cat_cols], prefix=standard_cat_cols)


    # 4. Identify Numeric Columns
    min_cols = [col for col in df.columns if 'diagnosis_to_treatment' in col]
    max_cols = [col for col in df.columns if any(x in col for x in ['neoadj_', 'adj_', '_in', 'ovarian_ablation', 'completed_chemo',
                                                                    'type_chemo'])]

    # 5. Combine and Defragment
    df_processed = pd.concat([
        df[['workup_no'] + min_cols + max_cols],
        df_standard_bins,
    ], axis=1).copy()  # .copy() fixes the PerformanceWarning fragmentaton

    # 6. Construct Aggregation Dictionary
    # All binary columns (standard and multi-val) + max_cols get 'max'
    binary_cols = df_standard_bins.columns.tolist()
    agg_dict = {col: 'max' for col in binary_cols + max_cols}
    agg_dict.update({col: 'min' for col in min_cols})

    # 7. Group and aggregate
    summary_df = df_processed.groupby('workup_no', sort=False).agg(agg_dict).reset_index()
    return summary_df

def load_diagnosis_bcfnz():
    if not os.path.isfile(Path('datasets/bcfnz/pickle/processed/diagnosis.pickle')):
        demographics = process_demographics()
        workup = process_workup()
        biomarkers = process_biomarkers()
        lesions = process_lesions()
        mets = process_mets()
        followup = load_followup_bcfnz()

        diagnosis = demographics.merge(workup, on=['patient_no', 'workup_no'], how='outer')
        print(diagnosis.shape)
        diagnosis = diagnosis.merge(biomarkers, on=['patient_no', 'workup_no'], how='outer')
        print(diagnosis.shape)

        diagnosis = diagnosis.merge(lesions, on=['patient_no', 'workup_no'], how='outer')
        print(diagnosis.shape)
        diagnosis = diagnosis.merge(mets, on=['patient_no', 'workup_no'], how='outer')
        print(diagnosis.shape)
        diagnosis = diagnosis.merge(followup, on=['patient_no', 'workup_no'], how='outer')

        diagnosis.to_pickle('datasets/bcfnz/pickle/processed/diagnosis.pickle')

    return pd.read_pickle('datasets/bcfnz/pickle/processed/diagnosis.pickle')


def load_bcfnz():
    """
    predict R 3.1:
    Calculate benefits of continuing endocrine therapy assuming survival to 5 years

    adds the PREDICT variables
        numeric:
            age.start.in Patient age in years
            size.in Tumour size mm
            heart.gy.in Number of grays radiation to the heart

        categorical:
            screen.in Clinically detected = 0, screen detected = 1
            smoker.in Never/ex = 0, current = 1

            er.in ER+ = 1, ER- = 0 , ER+ if .... , ER- if ...., excluded otherwise (required input)

            pr.in progesterone status PR+ = 1 PR- = 0 ; PR+ if ... , PR - if ...., unknown otherwise

            her2.in HER2+ = 1, HER2- = 0, missing = 9
            ki67.in KI67+ = 1, KI67- = 0, missing = 9


    grade.in Tumour grade
    nodes.in Number positive nodes



    generation.in Chemo generation 0, 2 or 3 only
    horm.in Hormone therapy Yes = 1, no = 0
    traz.in Trastuzumab therapy Yes = 1, no = 0
    bis.in Bisphosphonate therapy Yes = 1, no = 0
    radio.in Radiotherapy Yes = 1, no = 0


    """

    if not os.path.isfile(Path('datasets/bcfnz/pickle/processed/combined_one_row_per_workup.pickle')):

        tables = ("demographics", "workup", "followup", "histopathology",
                  "lesions", "biomarkers", "metastatic_disease", "surgery_primary",
                  "therapy_biological", "therapy_chemo", "therapy_hormone", "therapy_radio"
                  )

        for table in tables:
            if not os.path.isfile(f"datasets/bcfnz/pickle/unprocessed/{table}.pickle"):
                df = pd.read_excel(Path(f'datasets/bcfnz/excel/{table}.xlsx'))
                df.to_pickle(f"datasets/bcfnz/pickle/unprocessed/{table}.pickle")

        diagnosis = load_diagnosis_bcfnz()
        # from surgery, need to extract: did they have surgery?
        # need to refer to matthew's work here,don't have med knowledge req to understand his filtering
        surgery = load_surgery()
        treatments = treatments_one_row_per_workup()


        final_df = diagnosis.merge(surgery, on='workup_no', how='left')
        final_df = final_df.merge(treatments, on='workup_no', how='left')

        del diagnosis
        del surgery
        del treatments

        print(final_df.describe(include="all"))
        #print(final_df.info(verbose=True))

        final_df.to_pickle('datasets/bcfnz/pickle/processed/combined_one_row_per_workup.pickle')
    else:
        final_df = pd.read_pickle('datasets/bcfnz/pickle/processed/combined_one_row_per_workup.pickle')

    return final_df


def workup_therapy_map(x):
    if x == 'Not referred - deemed not necessary' or x == 'Referred - deemed not necessary':
        val = 0
    elif x == 'Yes':
        val = 1
    elif x == 'Referred - patient unfit' or x == 'Not referred - patient unfit':
        val = 2
    elif x == 'Referred - patient declined' or x == 'Not referred - patient declined':
        val = 3
    elif x == 'n/a - treatment for metastatic disease':
        val = 99
    else:
        val = 9
    return val


def load_bcfnz_filter_cohort():
    """
        processed_path = Path('datasets/gbcsCS_processed.csv')


    :return:
    """
    df = load_bcfnz()

    # filter to gender == female
    # total female = 44810/45115
    # print(df[['gender']].value_counts())
    demographics = df[df['gender'] == 'Female']

    # first diagnosis only

    return df


def shuffle_and_split_data(data, test_ratio):
    shuffled_indices = np.random.permutation(len(data))
    test_set_size = int(len(data) * test_ratio)
    test_indices = shuffled_indices[:test_set_size]
    train_indices = shuffled_indices[test_set_size:]
    return data.iloc[train_indices], data.iloc[test_indices]


if __name__ == '__main__':
    data = load_bcfnz()
    print(data.columns)
    print(tabulate(data, headers='keys', tablefmt='plain'))
