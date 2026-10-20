import sys
from pathlib import Path
import pandas as pd
import warnings 
warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered in cast")


project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from scripts.compare_dataframes import load_py, load_r
from preprocessing.derived_vars import binary_neoadj_adj, dcis, days_to_mets
from utils.summary_funcs import duplicates_by_unique_id
from utils.dataviz import cohort_flowchart


def add_cohort_vars(unfiltered_data: Path = Path('./datasets/bcfnz/pickle/processed/unfiltered_with_nhs_vars.pickle'),
                  out_dir: Path = Path('datasets/bcfnz/pickle/processed/')):
    """
    Input: The merged complete dataset with nhs variables added

    Creates boolean columns for inclusion (True) or exclusion (False) for each criterion:
        - valid recorded diagnosis date
        - gender = Female
        - diagnosis_number = 1 (first diagnosis for a patient)
        - diagnosed between 20 and 85
        - did not receive neoadj therapy
        - no metastasis at baseline (within 1 month of diagnosis or less)
        - not a DCIS diagnosis
        - local therapy complete / surgically complete

    Also:
        - valid values for: tumour size, tumour grade, positive node count, ER result

    Output: 
    - Final patient cohort
    - Latex formatted table summary of how many patients were excluded at each stage

    """
    df = load_py(unfiltered_data)

    df = df.copy()

    # add derived variables required for cohort selection
    df = binary_neoadj_adj(df)
    df = dcis(df)
    df = days_to_mets(df)

    df = df.assign(
        cohort_valid_diagnosis = df['tissue_dx_date'].notna(),
        cohort_female = df['Gender'] == 'Female',
        cohort_first_diagnosis = df['diagnosis_number'] == 1,
        cohort_dx_20_85 = df['dx_age'].between(20, 85),
        cohort_no_neoadj = (
            (df[['neo_rad_binary', 'neo_hormone_binary', 'neo_chemo_binary', 'neo_mab_binary']] == False)
            .all(axis=1)
        ),
        cohort_no_mets_baseline = (df['days_to_mets'].isna()) | ((df['days_to_mets'] > 30)),
        cohort_no_dcis = (df['dcis'] == 'NOT DCIS'),
        cohort_primary_surgery = (df['first_surg_date'].notna()),
        cohort_locoregional_complete = (df['final_locoregional_completion'] == 'COMPLETE LOCOREGIONAL THERAPY'),
        cohort_tumour_details = ~(df['size.in'].isna() | df['grade.in'].isna() | df['nodes.in'].isna()),
        cohort_er_valid = ~(df['er.in'].isna()),
        ) 

    return df



def filter_cohort(unfiltered_data: Path = Path('./datasets/bcfnz/pickle/processed/unfiltered_with_nhs_vars.pickle'),
                  out_dir: Path = Path('datasets/bcfnz/pickle/processed/'), plot=True):
    df = load_py(unfiltered_data)
    df = add_cohort_vars(unfiltered_data, out_dir)

    if plot:
        criteria_dict = {
            "Female": "cohort_female",
            "No Mets at Baseline": "cohort_no_mets_baseline",
            "No DCIS": "cohort_no_dcis",
            "Primary Surgery": "cohort_primary_surgery",
            "First Diagnosis": "cohort_first_diagnosis",
            "Age 20-85": "cohort_dx_20_85",
            "No Neoadjuvant": "cohort_no_neoadj",
            "Complete Locoregional Therapy": "cohort_locoregional_complete",
            "Tumour Info Complete (Size, Grade, Positive Nodes)": "cohort_tumour_details",
            "ER Result Complete": "cohort_er_valid"
        }

        cohort_flowchart(df, '/home/lou/coding/bcf/breast-cancer-cpm-validation-nz/figures/bcfnr/cohort_flowchart', criteria_dict)

    res = df[df['cohort_valid_diagnosis'] & df['cohort_female'] & df['cohort_first_diagnosis'] & 
             df['cohort_dx_20_85'] & df['cohort_no_neoadj'] & df['cohort_no_mets_baseline'] & 
             df['cohort_no_dcis'] & df['cohort_primary_surgery'] & df['cohort_locoregional_complete'] & 
             df['cohort_tumour_details'] & df['cohort_er_valid']]

    # also remove any entries with nodes.in = 999
    res = res[res['nodes.in'] != 999]
    
    out_pickle = out_dir / 'filtered_cohort.pickle'
    res.to_pickle(out_pickle)
    res.to_csv(out_dir / 'filtered_cohort.csv', index=False)

    print(res.describe())

    return res



def strother_cohort_stages_summary() -> pd.DataFrame:
    """
    Input: The merged complete dataset from reproduce_strother_tables.py

    Creates a summary table of how many patients were excluded at each stage of cohort selection.

    Output: 
    - Latex formatted table summary of how many patients were excluded at each stage
    """

    summary_data = []

    whole_cohort = load_r(Path('/home/lou/coding/bcf/breast-cancer-cpm-validation-nz/datasets/bcfnz/strother/merged_breast_tables.Rda'))

    summary_data.append({
        'stage': 'Whole cohort',
        'n_patients': len(whole_cohort)
    })

    no_dcis = load_r(Path('/home/lou/coding/bcf/breast-cancer-cpm-validation-nz/datasets/bcfnz/strother/merged_breast_tables_no_DCIS.Rda'))

    summary_data.append({
        'stage': 'No DCIS',
        'n_patients': len(no_dcis)
    })

    # gender female and 1st diagnosis
    exclusion_1 = load_r(Path('/home/lou/coding/bcf/breast-cancer-cpm-validation-nz/datasets/bcfnz/strother/exclusion_df_1.Rda'))

    summary_data.append({
        'stage': 'Female and 1st diagnosis',
        'n_patients': len(exclusion_1)
    })

    # neoadj therapy flagged as for metastatic disease
    exclusion_3_5 = load_r(Path('/home/lou/coding/bcf/breast-cancer-cpm-validation-nz/datasets/bcfnz/strother/exclusion_df_3_5.Rda'))

    summary_data.append({
        'stage': 'Neoadj therapy flagged as for metastatic disease',
        'n_patients': len(exclusion_3_5)
    })

    # any neoadj therapy
    exclusion_4_1 = load_r(Path('/home/lou/coding/bcf/breast-cancer-cpm-validation-nz/datasets/bcfnz/strother/exclusion_df_4_1.Rda'))

    summary_data.append({
        'stage': 'Any neoadj therapy',
        'n_patients': len(exclusion_4_1)
    })

    print(pd.DataFrame(summary_data).to_latex(index=False, caption="Summary of patient cohort selection stages", label="tab:cohort_selection_summary"))


    return pd.DataFrame(summary_data)


if __name__ == '__main__':
    cohort = filter_cohort()

    print(cohort.describe())

    #stages_summary = strother_cohort_stages_summary()
    
