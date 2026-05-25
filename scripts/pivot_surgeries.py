#!/usr/bin/env python3
"""Read an Excel/CSV of surgeries, number surgeries per patient (workupno) by
surgery date and pivot Left/Right surgery type into columns L_1,R_1,L_2,R_2...

Usage:
  python scripts/pivot_surgeries.py --input path/to/file.csv --output out.csv
"""
from pathlib import Path
import argparse
import pandas as pd
import numpy as np
from typing import Optional, List


def find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    lowered = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lowered:
            return lowered[cand.lower()]
    return None


def read_input(path: Path, sheet_name: Optional[str] = None) -> pd.DataFrame:
    if path.suffix.lower() in (".xls", ".xlsx"):
        return pd.read_excel(path, sheet_name=sheet_name)
    else:
        return pd.read_csv(path)


def pivot_surgeries(
    df: pd.DataFrame,
    id_cols: Optional[list] = None,
    date_col: Optional[str] = None,
    left_col: Optional[str] = None,
    right_col: Optional[str] = None,
) -> pd.DataFrame:

    if not id_cols:
        raise ValueError("Could not find identifier columns; please pass --id-cols")
    if not date_col:
        raise ValueError("Could not find a surgery date column; please pass --date-col")
    if not left_col and not right_col:
        raise ValueError("Could not find left or right surgery type columns; please pass --left-col/--right-col")

    # normalise
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # split comma/semicolon-separated surgery-type strings into separate rows
    # so multiple procedures recorded in one cell become separate surgery records
    for col in (left_col, right_col):
        if col and col in df.columns:
            # Only split/explode when the column is an axillary-surgery field
            # (these sometimes come as comma/semicolon-separated lists).
            if 'axillary' not in col.lower():
                continue
            # ensure column is object-dtype so we can assign lists into it
            df[col] = df[col].where(df[col].notna(), None).astype(object)
            mask = df[col].notna()
            if mask.any():
                df.loc[mask, col] = df.loc[mask, col].astype(str).str.split(r"\s*[,;]\s*")
                df = df.explode(col)

    # sort and number surgeries per workupno
    df = df.sort_values(id_cols + [date_col])
    df["surg_n"] = df.groupby(id_cols).cumcount() + 1

    # pivot left and right separately
    parts = []
    max_n = int(df["surg_n"].max()) if not df["surg_n"].isna().all() else 0

    if left_col:
        left_pivot = df.pivot_table(index=id_cols, columns="surg_n", values=left_col, aggfunc="first")
        # rename columns to L_1, L_2...
        left_pivot.columns = [f"L_{int(c)}" for c in left_pivot.columns]
        parts.append(left_pivot)

    if right_col:
        right_pivot = df.pivot_table(index=id_cols, columns="surg_n", values=right_col, aggfunc="first")
        right_pivot.columns = [f"R_{int(c)}" for c in right_pivot.columns]
        parts.append(right_pivot)

    if not parts:
        raise RuntimeError("No pivot produced; check column names and input file")

    out = pd.concat(parts, axis=1)
    # also pivot surgery dates into L_surg_date_N / R_surg_date_N columns
    try:
        date_pivot = df.pivot_table(index=id_cols, columns="surg_n", values=date_col, aggfunc="first")
        # convert to date-only (no time)
        date_pivot = date_pivot.applymap(lambda x: pd.to_datetime(x, errors="coerce").date() if pd.notna(x) else x)
        for c in date_pivot.columns:
            n = int(c)
            lcol = f"L_surg_date_{n}"
            rcol = f"R_surg_date_{n}"
            out[lcol] = date_pivot[c]
            out[rcol] = date_pivot[c]
    except Exception:
        # non-fatal: if date pivoting fails, continue without date columns
        pass
    # ensure columns ordered as L_1,R_1,L_2,R_2...
    cols = []
    for i in range(1, max_n + 1):
        l = f"L_{i}"
        r = f"R_{i}"
        if l in out.columns:
            cols.append(l)
        if r in out.columns:
            cols.append(r)
    # add any remaining columns (defensive)
    for c in out.columns:
        if c not in cols:
            cols.append(c)
    out = out.reindex(columns=cols)
    out = out.reset_index()
    return out


def surg_first_last(df: pd.DataFrame, id_col: list = ["WorkupNo", "tissue_dx_date"], date_col: str = "DateOfSurgery") -> pd.DataFrame:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    surg_dates = df.groupby(id_col)[date_col].agg(first_surg_date="min", last_surg_date="max").reset_index()
    # convert to dates (no time) to keep output compact
    surg_dates["first_surg_date"] = pd.to_datetime(surg_dates["first_surg_date"], errors="coerce").dt.date
    surg_dates["last_surg_date"] = pd.to_datetime(surg_dates["last_surg_date"], errors="coerce").dt.date
    out = df.merge(surg_dates, on=id_col, how="left")
    return surg_dates


def prepare_surgery_data(
    df: pd.DataFrame,
    id_cols: Optional[list] = None,
    date_col: Optional[str] = None,
    left_col: Optional[str] = None,
    right_col: Optional[str] = None,
    expand_types: bool = False,
    drop_original: bool = False,
) -> pd.DataFrame:
    """Prepare surgery data for analysis.

    This wraps `pivot_surgeries` and optionally expands each surgery type into
    one-hot columns named like `L_1_<sanitized_type>` / `R_1_<sanitized_type>`.
    Returns the prepared DataFrame.
    """
    
    out = pivot_surgeries(df, id_cols=id_cols, date_col=date_col, left_col=left_col, right_col=right_col)

    if not expand_types:
        return out

    import re

    def sanitize(s: object) -> str:
        s = str(s)
        s = s.strip().lower()
        s = re.sub(r"[^0-9a-z]+", "_", s)
        s = re.sub(r"_+", "_", s)
        s = s.strip("_")

        if s == 'axillary_surgery_only':
            s = 'ax_only_surg'
        elif s == 'no_surgery':
            s = 'no_surg'      
        elif s == 'lumpectomy_excision_biopsy':
            s = 'lumpectomy_ex_biopsy'
        elif s == 'hookwire_localisation_excision':
            s = 'hookwire_local'
        elif s == 'prophylactic_mastectomy':
            s = 'ppx_mastectomy'
        elif s == 'wle_partial_mastectomy':
            s = 'wle_partial_matectomy'
        elif s == 'unknown':
            s = 'unknown_surg'
        elif s == 'no_breast_surgery':
            s = 'no_breast_surg'
        elif s == 'no_axillary_surgery_required':
            s = 'no_ax_surg'
        elif s == 'level_1_axillary_node_sample':
            s = 'L1_ax_ln_samp'
        elif s == 'level_1_axillary_node_clear':
            s = 'L1_ax_ln_clear'
        elif s == 'level_2_axillary_node_dissection':
            s = 'L2_ax_ln_dissect'
        elif s == 'level_3_axillary_node_clearance':
            s = 'L3_ax_ln_clear'
        elif s == 'declined':
            s = 'decline_surg'
        elif s == 'sentinel_node_biopsy':
            s = 'snb'
        elif s == 'sampling':
            s = 'L1_ax_ln_samp'
        elif s == 'mastectomy':
            s = 'mastectomy'
        elif s == 're_excision':
            s = 're_excision'
        else:
            s = None
        return s 

    id_cols = id_cols or find_column(df, ["workupno", "workup_no", "patientid", "patient_id", "id"])
    value_cols = [c for c in out.columns if c not in id_cols]
    melted = out.melt(id_vars=id_cols, value_vars=value_cols, var_name="surg_col", value_name="surg_type")
    melted = melted.dropna(subset=["surg_type"]) 

    # split comma/semicolon-separated lists (e.g. axillary surgery values) into separate rows
    if not melted.empty:
        melted["surg_type"] = melted["surg_type"].astype(str)

        # split on commas or semicolons, allowing surrounding whitespace
        melted["surg_type"] = melted["surg_type"].str.split(r"\s*[,;]\s*")
        melted = melted.explode("surg_type")
        # strip and drop empty pieces
        melted["surg_type"] = melted["surg_type"].str.strip()
        melted = melted.replace({"surg_type": {"": None}}).dropna(subset=["surg_type"]) 

    if melted.empty:
        if drop_original:
            return out.drop(columns=value_cols, errors="ignore")
        return out

    melted["type_sanit"] = melted["surg_type"].apply(sanitize)
    melted = melted.dropna(subset=["surg_type"]) 
    melted["newcol"] = melted["surg_col"].astype(str) + "_" + melted["type_sanit"]
    dummies = pd.get_dummies(melted["newcol"]) 
    for id_col in id_cols:
        dummies[id_col] = melted[id_col].values
    wide = dummies.groupby(id_cols).max().reset_index()
    out = out.merge(wide, on=id_cols, how="left")
    if drop_original:
        out = out.drop(columns=value_cols, errors="ignore")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", "-i", required=True, help="Input CSV or Excel file")
    p.add_argument("--output", "-o", required=True, help="Output CSV file")
    p.add_argument("--sheet", help="Excel sheet name (optional)")
    p.add_argument("--workup-col", help="Column name for workup/patient id")
    p.add_argument("--date-col", help="Column name for surgery date")
    p.add_argument("--left-col", help="Column name for left surgery type")
    p.add_argument("--right-col", help="Column name for right surgery type")
    p.add_argument("--expand-types", action="store_true", help="Also expand each surgery type into one-hot columns per L_/R_ number")
    p.add_argument("--drop-original", action="store_true", help="Drop the original L_*/R_* columns after expanding types")
    args = p.parse_args()

    path = Path(args.input)
    df = read_input(path, sheet_name=args.sheet)
    out = prepare_surgery_data(
        df,
        id_cols=args.workup_col,
        date_col=args.date_col,
        left_col=args.left_col,
        right_col=args.right_col,
        expand_types=args.expand_types,
        drop_original=args.drop_original,
    )
    out.to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
