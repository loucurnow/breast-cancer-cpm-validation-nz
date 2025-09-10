

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

