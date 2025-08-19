"""
        # her2       <- 1     # HER2+ = 1, HER2- = 0, missing = 9
        # ki67       <- 0     # KI67+ = 1, KI67- = 0, missing = 9

"""

import pandas as pd

def imputation_mice():
    # input : pandas df with mapping / recoding of variables done, but missing data not handled
    # output : pandas df with missing data handled via MICE (multiple imputation by chained equation)
    pass



def imputation_k_nearest_neighbour():
    """
    k = 10 default

    continuous/categorical variables: we used an euclidean/jaccard distance metric, look at k nearest neighbors of a datapoint.
            If at >= 3 not missing, impute using their mean/mode
            Otherwise, the overall mean/mode was used.

    Imputation involves only the original data available.
    In other words, we did not use imputed data to impute other features.

    The output variables should not require any imputation whatsoever.

    :return:
    """


