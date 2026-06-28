#!/usr/bin/env python3
"""Compare R and Python dataframes (lightweight row/column/value check).

Usage:
  python scripts/compare_dataframes.py --py datasets/bcfnz/pickle/processed/surgery_primary_full.pickle \
      --r datasets/bcfnz/strother/tidy_surgery_new_strother.Rda

Produces a brief summary and writes `compare_mismatches.csv` with example differing rows.
"""
from pathlib import Path
import argparse
import pandas as pd
import numpy as np
from scripts.align_dataframes import fix_excel_1900_leap_bug

def load_py(path: Path) -> pd.DataFrame:
    return pd.read_pickle(path)


def load_r(path: Path) -> pd.DataFrame:
    import pyreadr

    rr = pyreadr.read_r(str(path))
    _, df = next(iter(rr.items()))
    df = fix_excel_1900_leap_bug(df)
    return df


def compare(df_py: pd.DataFrame, df_r: pd.DataFrame, keys=("PatientNo", "WorkupNo", "tissue_dx_date")):
    # pick available keys
    avail_keys = [k for k in keys if k in df_py.columns and k in df_r.columns]
    if not avail_keys:
        # fallback to index-based comparison
        df_py = df_py.reset_index(drop=True)
        df_r = df_r.reset_index(drop=True)
        avail_keys = None

    if avail_keys:
        left = df_py.set_index(avail_keys)
        right = df_r.set_index(avail_keys)
        # align on common index (inner join)
        common_index = left.index.intersection(right.index)
        left = left.loc[common_index].sort_index()
        right = right.loc[common_index].sort_index()
    else:
        left = df_py.copy()
        right = df_r.copy()

    # align columns: consider only columns present in both for content comparison
    common_cols = [c for c in left.columns if c in right.columns]
    only_py = sorted([c for c in left.columns if c not in right.columns])
    only_r = sorted([c for c in right.columns if c not in left.columns])

    print(f"Comparing {len(left)} rows and {len(common_cols)} common columns..."
          f" (only in py: {len(only_py)}, only in R: {len(only_r)})")
    
    if only_py:
        print("Columns only in Python output:", only_py)
    if only_r:
        print("Columns only in R output:", only_r)

    summary = {
        "rows_compared": len(left),
        "common_columns": len(common_cols),
        "only_in_py": only_py,
        "only_in_r": only_r,
    }

    diffs = {}
    for c in common_cols:
        a = left[c]
        b = right[c]
        # coerce datetimes (use pandas helpers to support extension dtypes)
        if pd.api.types.is_datetime64_any_dtype(a) or pd.api.types.is_datetime64_any_dtype(b):
            a = pd.to_datetime(a, errors="coerce")
            b = pd.to_datetime(b, errors="coerce")
            neq = a.fillna(pd.NaT) != b.fillna(pd.NaT)
        elif pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            neq = ~(a.fillna(np.nan).astype(float).eq(b.fillna(np.nan).astype(float)))
        else:
            # compare as strings (strip/normalize)
            neq = a.fillna("").astype(str).str.strip() != b.fillna("").astype(str).str.strip()

        n_diff = int(neq.sum())
        if n_diff:
            diffs[c] = min(n_diff, 5)

    summary["diff_columns_count"] = len(diffs)
    summary["diff_columns_sample_counts"] = diffs

    # prepare example mismatches for export and include index/key values
    mismatch_rows = []
    for c in diffs:
        a = left[c]
        b = right[c]
        # compute inequality mask using same dtype-aware logic as above
        if pd.api.types.is_datetime64_any_dtype(a) or pd.api.types.is_datetime64_any_dtype(b):
            a2 = pd.to_datetime(a, errors="coerce")
            b2 = pd.to_datetime(b, errors="coerce")
            neq = a2.fillna(pd.NaT) != b2.fillna(pd.NaT)
        elif pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            neq = ~(a.fillna(np.nan).astype(float).eq(b.fillna(np.nan).astype(float)))
        else:
            neq = a.fillna("").astype(str).str.strip() != b.fillna("").astype(str).str.strip()

        mask = neq

        sel_left = left.loc[mask, c]
        sel_right = right.loc[mask, c]

        idx = sel_left.index
        # build a DataFrame of index/key values
        names = list(idx.names) if hasattr(idx, "names") else [idx.name]
        if len(names) > 1:
            col_names = [n if n else f"index_{i}" for i, n in enumerate(names)]
            idx_df = pd.DataFrame(list(idx), columns=col_names)
        else:
            name = names[0] or "index"
            idx_df = pd.DataFrame({name: list(idx)})

        ex_vals = pd.DataFrame({f"{c}_py": sel_left.astype(object).values, f"{c}_r": sel_right.astype(object).values})
        ex = pd.concat([idx_df.reset_index(drop=True), ex_vals.reset_index(drop=True)], axis=1)
        # keep at most 5 rows per column
        mismatch_rows.append(ex.head(5))

    if mismatch_rows:
        demo = pd.concat(mismatch_rows, axis=1)
    else:
        demo = pd.DataFrame()

    return summary, only_py, only_r, demo


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--py", required=True)
    p.add_argument("--r", required=True)
    args = p.parse_args()

    py_path = Path(args.py)
    r_path = Path(args.r)
    df_py = load_py(py_path)
    df_r = load_r(r_path)

    summary, only_py, only_r, demo = compare(df_py, df_r)

    print("Rows compared:", summary["rows_compared"])
    print("Columns in both:", summary["common_columns"])
    print("Columns only in python output:", only_py)
    print("Columns only in R output:", only_r)
    print("Differing columns (sample counts):", summary["diff_columns_sample_counts"])

    if not demo.empty:
        demo.to_csv('compare_mismatches.csv', index=False)
        print('Wrote sample mismatches to compare_mismatches.csv')


if __name__ == '__main__':
    main()
    #df = load_r(Path("/home/lou/coding/bcf/breast-cancer-cpm-validation-nz/datasets/bcfnz/strother/tidy_biological_markers.Rda"))
    #print(df[df['PatientNo'] == 12737.0].to_markdown())
