from pathlib import Path
import pandas as pd
import tarfile
import urllib.request
import pyreadr
import matplotlib.pyplot as plt
from tabulate import tabulate

from derived_vars import tumour_size_group_path_stage_groupings, brca_result


def load_gbcscs():
    processed_path = Path('datasets/gbcsCS_processed.csv')

    if not processed_path.is_file():
        df = pd.read_csv('datasets/gbcsCS_raw.csv')

        # calculate hormone receptor thresholds
        df['er_status'] = df['estrg_recp'].apply(lambda x: x >= 20)
        df['pr_status'] = df['prog_recp'].apply(lambda x: x >= 20)

        df['size_group_t_stage'] = df['size'].apply(tumour_size_group_path_stage_groupings)

        df['size_group_quartiles'] = pd.qcut(df['size'], q=4)

        df['diagnosis_year'] = df['diagdateb'].dt.year

        # cols missing from this dataset, but in the BCFNR data:
        df['her2'] = None
        df['ki67'] = None

        df.to_csv(processed_path, index=False)
    else:
        df = pd.read_csv(processed_path, index_col='id')

        df.to_csv(processed_path)
    return


def load_treatments_bcfnz():
    surgery = pd.read_excel(Path('datasets/bcfnz/Primary Surgery_DeIdentified.xlsx'))

    therapy_radio = pd.read_excel(Path('datasets/bcfnz/Radiotherapy_DeIdentified.xlsx'))
    therapy_chemo = pd.read_excel(Path('datasets/bcfnz/Chemotherapy_DeIdentified.xlsx'))
    therapy_bio = pd.read_excel(Path('datasets/bcfnz/BiologicalTherapy_DeIdentified.xlsx'))
    therapy_hormone = pd.read_excel(Path('datasets/bcfnz/HormoneTherapy_DeIdentified.xlsx'))

    return


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

    demographics = pd.read_excel(Path('datasets/bcfnz/Demographic Data_DeIdentified.xlsx'))

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

    # drop unnecessary columns
    demographics = demographics.drop(columns=['DateOfTissueDiagnosis', "Date Of Death",
                                              'Genetic test result (BRCA1)',
                                              'Genetic test result (BRCA2)',
                                              'Current Patient Status',
                                              'Cause Of Death',
                                              'Cause Of Death Verified By MOH',
                                              'ICDCodeOfTheCauseOfDeath'])

    demographics.rename(columns={"Ethnicity (Level 1)": "ethnicity",
                                 "Gender": "gender",
                                 "Region": "region",
                                 "Age At Diagnosis": "diagnosis_age"}, inplace=True)

    print(demographics[['death_cause']].value_counts())
    print(demographics[['death_cause_verified']].value_counts())
    print(demographics[['death_icd_code']].value_counts())

    test = demographics[demographics['death_cause_verified'] == 0]
    print(test['death_cause'].value_counts())

    print(demographics.head().to_markdown())
    print(demographics.columns)
    del demographics

    workup = pd.read_excel(Path('datasets/bcfnz/Workup_DeIdentified.xlsx'))
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

    workup['primary_surgery'] = workup['PrimarySurgery'].apply(lambda x:
                                                               1 if x == 'Yes'
                                                               else 0 if x == 'No'
                                                               else 9)

    workup['symptomatic'] = workup['DidThePatientPresentWithSymptomsAtTimeOfReferral'].apply(lambda x:
                                                                                             1 if x == 'Yes'
                                                                                             else 0 if x == 'No'
                                                                                             else 9)
    print(workup['symptomatic', 'DidThePatientPresentWithSymptomsAtTimeOfReferral'].value_counts())

    workup['referral_source'] = workup['SourceOfReferral'].apply(
        lambda x:
        0 if x == 'BreastScreen Aotearoa' or x == 'Screen detected - non BSA'
        else 1 if x == 'GP (symptomatic)'
        else 9 if x == 'Unknown'
        else 3
    )

    print(workup['SourceOfReferral'].value_counts())
    print(workup['referral_source'].value_counts())

    workup['neoadj_radiation'] = workup['PrimaryOrNeoAdjuvantRadiationTherapy'].apply(
        lambda x:
        0 if x == 'Not referred - deemed not necessary' or x == 'Referred - deemed not necessary'
        else 1 if x == 'Yes'
        else 2 if x == 'Referred - patient unfit' or x == 'Not referred - patient unfit'
        else 3 if x == 'Referred - patient declined' or x == 'Not referred - patient declined'
        else 99 if x == 'n/a - treatment for metastatic disease'
        else 9
    )

    print(workup['neoadj_radiation'].value_counts())

    print(workup['invasive'].value_counts())

    print(workup['MetastaticDisease'].value_counts())
    print(workup['primary_surgery'].value_counts())

    workup = workup.drop(columns=['PrimarySurgery',
                                  "DidThePatientPresentWithSymptomsAtTimeOfReferral",
                                  'DiagnosisType'])

    print(workup.head().to_markdown())

    del workup

    biomarkers = pd.read_excel(Path('datasets/bcfnz/Biomarkers_DeIdentified.xlsx'))
    print(biomarkers.head().to_markdown())
    print(biomarkers.columns)
    del biomarkers

    lesions = pd.read_excel(Path('datasets/bcfnz/Lesions_DeIdentified.xlsx'))
    print(lesions.head().to_markdown())
    print(lesions.columns)
    del lesions

    # allow mets cases if they are diagnosed with mets > 1 mo ? after their primary surgery
    mets = pd.read_excel(Path('datasets/bcfnz/MetastaticDisease_DeIdentified.xlsx'))
    followup = Path('datasets/bcfnz/Followup_DeIdentified.xlsx')

    result = pd.DataFrame()

    return result


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

    return df


def shuffle_and_split_data(data, test_ratio):
    shuffled_indices = np.random.permutation(len(data))
    test_set_size = int(len(data) * test_ratio)
    test_indices = shuffled_indices[:test_set_size]
    train_indices = shuffled_indices[test_set_size:]
    return data.iloc[train_indices], data.iloc[test_indices]


if __name__ == '__main__':
    data = load_bcfnz()
    print(tabulate(data, headers='keys', tablefmt='plain'))
