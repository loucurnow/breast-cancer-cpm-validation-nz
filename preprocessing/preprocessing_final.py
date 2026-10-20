import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from preprocessing.cohort_selection import filter_cohort
from preprocessing.reproduce_strother_tables import generate_strother_files
from preprocessing.derived_vars import nhs_predict_model_vars
import pandas as pd


def trim_excess_cols(df, out_dir=Path('datasets/bcfnz/pickle/processed/')):
    """
    Removes all oclumns from the dataset which are not either directly required for the PREDICT model,
    or useful for demographic analysis / subgroup validation testing of the model's performance
    """

    model_cols = ['age.start.in', 'screen.in', 'size.in', 'grade.in', 'nodes.in', 'er.in', 'her2.in', 
                  'ki67.in', 'pr.in', 'generation.in', 'horm.in', 'traz.in', 'bis.in',
                  'radio.in', 'heart.gy.in', 'smoker.in']
    
    dem_cols = ['unique_key', 'diag.year', 'ethnic', 'menopause', 'Region', 'lesion_count', 
                'dod', 'cod', 'cod_verified', 
                'ICDCodeOfTheCauseOfDeath', 'final_survival_sweep', 'days_to_mets']

    col_selection = model_cols + dem_cols + ['surv.time.actual', 'days.to.censor', 'days.to.death', 'surv.actual', 'treatments.given']

    df_input_for_model = df[col_selection]

    out_pickle = out_dir / 'model_input.pickle'
    df_input_for_model.to_pickle(out_pickle)
    df_input_for_model.to_csv(out_dir / 'model_input.csv', index=False)

    return df_input_for_model





if __name__ == '__main__':
    #
    out_dir = Path('datasets/bcfnz/pickle/processed/')
    unfiltered_save_path = Path('./datasets/bcfnz/pickle/processed/unfiltered_with_nhs_vars.pickle')

    regenerate = True

    if regenerate:
        #generate_strother_files() # uncomment this line to regenerate the strother tables from the original data. This is not necessary if you have already generated them once.

        df = pd.read_pickle(Path('./datasets/bcfnz/pickle/processed/strother/merged_breast_tables.pickle'))

        df = nhs_predict_model_vars(df)
        df.to_pickle(unfiltered_save_path)
    
        final_cohort = filter_cohort(unfiltered_data=unfiltered_save_path, out_dir=out_dir, plot=True)

    df = pd.read_pickle(Path('./datasets/bcfnz/pickle/processed/filtered_cohort.pickle'))

    df_input_for_model = trim_excess_cols(df, out_dir)

    print(df.shape)

    print(df_input_for_model['smoker.in'].describe())

    print(df_input_for_model['smoker.in'].value_counts())

    #stages_summary = strother_cohort_stages_summary()