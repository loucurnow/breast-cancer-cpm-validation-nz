"""
Basic summary functions for dataframes
"""

import pandas as pd


def duplicates_by_unique_id(df: pd.DataFrame, unique_id_cols: list=['unique_key']) -> pd.DataFrame:
    """
    Returns a dataframe of rows that have duplicate values in the specified unique_id_col.
    """
    duplicates = df[df.duplicated(subset=unique_id_cols, keep=False)]
    return duplicates.sort_values(by=unique_id_cols)


def aggregate_column_totals(df):
    """
    Summarise the number of rows in the dataframe, and the number of unique values in each column.
    Returns a dataframe with the summary.
    """
    df = df.copy()
    summary = pd.DataFrame({
        'column': df.columns,
        'n_unique': [df[col].nunique(dropna=True) for col in df.columns],
        'n_missing': [df[col].isna().sum() for col in df.columns],
        'n_rows': len(df)
    })

    