from pathlib import Path
import numpy as np
import pandas as pd
import tarfile
import urllib.request
import pyreadr
import matplotlib.pyplot as plt
from tabulate import tabulate

from derived_vars import tumour_size_group_path_stage_groupings


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
    return df


# example
def shuffle_and_split_data(data, test_ratio):
    shuffled_indices = np.random.permutation(len(data))
    test_set_size = int(len(data) * test_ratio)
    test_indices = shuffled_indices[:test_set_size]
    train_indices = shuffled_indices[test_set_size:]
    return data.iloc[train_indices], data.iloc[test_indices]


if __name__ == '__main__':
    data = load_gbcscs()
    print(tabulate(data, headers='keys', tablefmt='plain'))
