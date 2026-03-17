import pandas as pd


def tumour_size_group_path_stage_groupings(size):
    if size <= 20:
        return 1  # corresponds to pT1
    elif size <= 50:
        return 2  # corresponds to pT2
    else:
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

    brca_1 = brca_map.get(row['Genetic test result (BRCA1)'])
    brca_2 = brca_map.get(row['Genetic test result (BRCA2)'])

    if brca_1 == 1 or brca_2 == 1:
        result = 1
    elif brca_1 == 0 and brca_2 == 0:
        result = 0
    else:
        result = 9

    return result


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
            or (pd.isna(ihc) and fish == 'FISH HER2 Amplified (positive)'):
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
            or (pd.isna(ihc) and fish == 'FISH HER2 No Amplification (negative)'):
        return 0

    if pd.isna(fish):  # when fish her2 result is not known
        if ihc == 'IHC HER2 0':
            return 0
        if ihc == 'IHC HER2 1+' or ihc == 'IHC HER2 2+':
            return 9

    else:
        print(fish, ihc)
        return 99



