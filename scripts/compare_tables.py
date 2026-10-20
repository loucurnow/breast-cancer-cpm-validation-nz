"""
Functions to compare the tables from Matt's R code and the Python transformations (lightweight row/column/value check).
"""
import pandas as pd

def align_dtypes(df1, df2):
    """Align data types of df2 to match df1 for comparison."""
    for col in df1.columns:
        if col in df2.columns:
            try:
                if col == "PatientNo":  # special case for PatientNo, convert to int if possible
                    df1[col] = pd.to_numeric(df1[col], errors='coerce').astype(int)
                    df2[col] = pd.to_numeric(df2[col], errors='coerce').astype(int)
                # if the column is float in at least one df, convert both to float
                elif pd.api.types.is_float_dtype(df1[col]) or pd.api.types.is_float_dtype(df2[col]):
                    df1[col] = pd.to_numeric(df1[col], errors='coerce')
                    df2[col] = pd.to_numeric(df2[col], errors='coerce')

                else: # otherwise, try to convert df2 to the same type as df1
                    df2[col] = df2[col].astype(df1[col].dtype)
            except Exception as e:
                print(f"Warning: Could not convert column {col} to {df1[col].dtype}: {e}")
    return df1, df2


def compare_tables(df1, df2, key, save_dir=None):
    """
    Compare two dataframes and print summary of differences.
    - Identify columns only in df1 vs df2
    - Identify rows with mismatched values in common columns - ignore if both null 
    - Print summary of differences
    - Optionally write out example mismatches to CSV
    """

    common_cols = list(set(df1.columns).intersection(set(df2.columns)))
    only_in_df1 = set(df1.columns) - set(df2.columns)
    only_in_df2 = set(df2.columns) - set(df1.columns)

    print(f"Columns only in df1: {only_in_df1}")
    print(f"Columns only in df2: {only_in_df2}")
    print(f"Common columns: {common_cols}")

    # set index to a common key if available for row-wise comparison
    if key and key in df1.columns and key in df2.columns:
        df1 = df1.set_index(key)
        df2 = df2.set_index(key)
        common_cols_no_key = [col for col in common_cols if col != key]
    else:
        common_cols_no_key = common_cols

    df1 = df1[common_cols_no_key].sort_index().reset_index().copy()
    df2 = df2[common_cols_no_key].sort_index().reset_index().copy()

    # get data types in df2 to conform to df1 for comparison
    df1, df2 = align_dtypes(df1, df2)

    # Merge df1 (39612) and df2 (39314) on PatientNo
    # 'indicator=True' adds a column called '_merge'
    df1 = df1.copy()
    df2 = df2.copy()
    merged = pd.merge(df1, df2, on=key, how='outer', indicator=True, suffixes=('_df1', '_df2'))
    merged = merged.copy()

    # Rows present ONLY in df1
    only_in_df1 = merged[merged['_merge'] == 'left_only'].copy()
    # Remove the _df2 columns and rename _df1 to original column names
    only_in_df1 = only_in_df1.drop(columns=[col for col in only_in_df1.columns if '_df2' in col])
    only_in_df1.columns = [col.replace('_df1', '') for col in only_in_df1.columns]

    # Rows present ONLY in df2
    only_in_df2 = merged[merged['_merge'] == 'right_only'].copy()
    # Clean up columns for df2 as well
    only_in_df2 = only_in_df2.drop(columns=[col for col in only_in_df2.columns if '_df1' in col])
    only_in_df2.columns = [col.replace('_df2', '') for col in only_in_df2.columns]

    # Save to CSV
    if save_dir:
        only_in_df1.to_csv(save_dir / 'only_in_df1.csv', index=False)
        only_in_df2.to_csv(save_dir / 'only_in_df2.csv', index=False)

    # Extract rows that exist in both
    common_patients = merged[merged['_merge'] == 'both']

    # Separate back into two frames, aligned by PatientNo
    # We must ensure they have the same columns in the same order
    cols = [col for col in df1.columns if col != key]  # Assuming both have the same column names
    common_df1 = common_patients[[key] + [f"{c}_df1" for c in cols]].copy()
    common_df2 = common_patients[[key] + [f"{c}_df2" for c in cols]].copy()

    # Fix column names to match for comparison
    common_df1.columns = [key] + cols
    common_df2.columns = [key] + cols

    # Set index to PatientNo so they are perfectly aligned for comparison
    common_df1 = common_df1.set_index(key).sort_index()
    common_df2 = common_df2.set_index(key).sort_index()

    # Now compare
    differences = common_df1.compare(common_df2)

    if differences.empty:
        print("No differences found in common rows.")
    else:
        print(f"Differences found in {len(differences)} rows of common patients.")
        print(f"Columns with differences: {differences.columns.get_level_values(0).unique().tolist()}")


    if save_dir:
        differences.to_csv(save_dir / 'differences.csv', index=True)

    differences = differences.reset_index()
    print(differences)

    return differences