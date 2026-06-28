import pandas as pd



def fix_excel_1900_leap_bug(df: pd.DataFrame) -> pd.DataFrame:
    """Scans a DataFrame for datetime columns and corrects the

    1900 leap year bug by shifting '1899-12-31' to '1900-01-01'.
    """
    # Create a copy so we don't accidentally modify the original data frame
    df_clean = df.copy()

    # change all cols containing 'date' in the name to datetime type (if not already)
    for col in df_clean.columns:
        if 'date' in col.lower():
            df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce')

    # Find all columns that are datetime types
    datetime_cols = df_clean.select_dtypes(
        include=["datetime64[ns]", "datetime"]
    ).columns

    for col in datetime_cols:
        # Check if the problematic date exists in this column to save processing time
        if (df_clean[col] == "1899-12-31").any():
            df_clean[col] = df_clean[col].mask(
                df_clean[col] == "1899-12-31", pd.Timestamp("1900-01-01")
            )

    return df_clean