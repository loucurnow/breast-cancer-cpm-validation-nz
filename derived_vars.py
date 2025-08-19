

def tumour_size_group_path_stage_groupings(size):
    if size <= 20:
        return 1  # corresponds to pT1
    elif size <= 50:
        return 2  # corresponds to pT2
    else:
        return 3  # corresponds to pT3