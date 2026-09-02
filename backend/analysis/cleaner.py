# backend/analysis/cleaner.py
"""
Stage 1b: Comprehensive Data Cleaning & Inspection
Runs immediately after file ingestion, BEFORE decode.

12-Stage Pipeline:
  1.  Audit & initial profile
  2.  Strip junk (whitespace, null synonyms)
  3.  Fix data types (numeric strings, datetime strings, booleans, downcast)
  4.  Deduplicate (exact match)
  5.  Drop junk columns (>=95% missing)
  6.  Missing value analysis & strategy recommendations
  7.  Inconsistency detection (case variants, rare typo values)
  8.  Outlier detection (IQR + Z-score dual method)
  9.  Skewness & distribution profiling + full column profiles
  10. Class imbalance detection (for low-cardinality columns)
  11. Data quality score computation (0-100)
  12. Post-clean validation & audit trail

Returns: (df_clean, inspection_report, cleaning_summary)
"""
from __future__ import annotations

_NULL_SYNONYMS = {
    "nan", "none", "n/a", "na", "null", "nil", "-", "--", "---",
    "unknown", "not available", "missing", ".", " ", ""
}


def _to_null_synonyms(series, pd):
    lower = series.astype(str).str.strip().str.lower()
    mask = lower.isin(_NULL_SYNONYMS)
    series = series.copy()
    series[mask] = pd.NA
    return series


def _safe_skew(vals):
    try:
        from scipy.stats import skew
        return round(float(skew(vals)), 4)
    except Exception:
        try:
            return round(float(vals.skew()), 4)
        except Exception:
            return None


def _safe_kurt(vals):
    try:
        from scipy.stats import kurtosis
        return round(float(kurtosis(vals)), 4)
    except Exception:
        try:
            return round(float(vals.kurt()), 4)
        except Exception:
            return None


def _missing_description(pct, strategy):
    labels = {
        "none_needed":    "No missing values",
        "median_impute":  f"{pct}% missing — median imputation recommended",
        "mean_impute":    f"{pct}% missing — mean imputation recommended",
        "mode_impute":    f"{pct}% missing — mode imputation recommended (categorical)",
        "knn_impute":     f"{pct}% missing — KNN imputation recommended (uses similar rows)",
        "mice_impute":    f"{pct}% missing — MICE imputation recommended (model-based)",
        "indicator_flag": f"{pct}% missing — create missingness indicator before imputing",
        "drop_column":    f"{pct}% missing — column too sparse; consider dropping",
        "ffill":          f"{pct}% missing — forward-fill recommended (time-series)",
        "flag_only":      f"{pct}% missing — flagged for review",
    }
    return labels.get(strategy, f"{pct}% missing")


def _outlier_treatments(pct):
    opts = []
    if pct < 2:
        opts.append("Remove — small number, likely data entry errors")
    opts.append("Cap/Winsorize — clip to 1st/99th percentile boundary")
    opts.append("Log transform — compress range for right-skewed data")
    opts.append("Keep & note — outliers may be genuine signals (e.g. fraud, extremes)")
    return opts


def clean_and_inspect(df) -> tuple:
    """
    Run all 12 cleaning and inspection stages on the raw DataFrame.

    Returns:
        df_clean          — cleaned DataFrame
        inspection_report — dict describing what was found (comprehensive)
        cleaning_summary  — dict describing what was changed
    """
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        return df, {}, {}

    shape_before = {"rows": int(len(df)), "columns": int(len(df.columns))}
    actions_taken = []
    type_fixes_applied = []

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 2 — Strip whitespace + null synonyms from object columns
    # ══════════════════════════════════════════════════════════════════════════
    for col in df.select_dtypes(include="object").columns:
        try:
            df[col] = df[col].apply(lambda x: "; ".join(f"{k}: {v}" for k, v in x.items()) if isinstance(x, dict) else ("; ".join(str(v) for v in x) if isinstance(x, list) else x))
            df[col] = df[col].astype(str).str.strip()
            df[col] = _to_null_synonyms(df[col], pd)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 3 — Fix data types
    # ══════════════════════════════════════════════════════════════════════════
    BOOL_MAP = {
        "true": True, "false": False, "yes": True, "no": False,
        "1": True, "0": False, "y": True, "n": False,
    }
    for col in list(df.columns):
        s = df[col]
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
            continue
        non_null = s.dropna()
        if len(non_null) == 0:
            continue
        lower_vals = set(non_null.astype(str).str.lower().unique())
        # 3a. Boolean detection
        if lower_vals <= set(BOOL_MAP.keys()):
            try:
                df[col] = s.astype(str).str.lower().map(lambda x: BOOL_MAP.get(x, pd.NA))
                type_fixes_applied.append({
                    "column": col, "from": "object", "to": "boolean",
                    "reason": "Only true/false/yes/no values"
                })
                continue
            except Exception:
                pass
        # 3b. Numeric strings
        num_attempt = pd.to_numeric(non_null.astype(str).str.replace(",", ""), errors="coerce")
        if num_attempt.notna().mean() >= 0.80:
            try:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
                type_fixes_applied.append({
                    "column": col, "from": "object", "to": "numeric",
                    "reason": ">=80% values parseable as numbers"
                })
                continue
            except Exception:
                pass
        # 3c. Datetime strings
        if non_null.astype(str).str.match(r"^\d{1,4}[-/\.]\d{1,2}[-/\.]").mean() >= 0.60:
            try:
                dt_attempt = pd.to_datetime(non_null.astype(str), errors="coerce", infer_datetime_format=True)
                if dt_attempt.notna().mean() >= 0.60:
                    df[col] = pd.to_datetime(df[col].astype(str), errors="coerce", infer_datetime_format=True)
                    type_fixes_applied.append({
                        "column": col, "from": "object", "to": "datetime",
                        "reason": ">=60% values match date patterns"
                    })
                    continue
            except Exception:
                pass

    if type_fixes_applied:
        actions_taken.append({
            "action": "data_types_fixed", "count": len(type_fixes_applied),
            "description": f"Fixed data types on {len(type_fixes_applied)} column(s)",
            "details": type_fixes_applied
        })

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 4 — Exact duplicate removal
    # ══════════════════════════════════════════════════════════════════════════
    n_duplicates = int(df.duplicated().sum())
    if n_duplicates > 0:
        df = df.drop_duplicates().reset_index(drop=True)
        actions_taken.append({
            "action": "duplicates_removed", "count": n_duplicates,
            "description": f"Removed {n_duplicates} exact duplicate row(s)"
        })

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 5 — Drop columns >=95% missing
    # ══════════════════════════════════════════════════════════════════════════
    dropped_cols = []
    if len(df) > 0:
        pct_miss_cols = df.isnull().mean()
        cols_to_drop = pct_miss_cols[pct_miss_cols >= 0.95].index.tolist()
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            dropped_cols = cols_to_drop
            actions_taken.append({
                "action": "empty_columns_dropped", "count": len(cols_to_drop),
                "columns": cols_to_drop,
                "description": f"Dropped {len(cols_to_drop)} column(s) with >=95% missing"
            })

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 6 — Missing value analysis + strategy recommendations
    # ══════════════════════════════════════════════════════════════════════════
    missing_per_col = {}
    for col in df.columns:
        n_miss = int(df[col].isna().sum())
        pct = round(n_miss / len(df) * 100, 1) if len(df) > 0 else 0.0
        is_num = pd.api.types.is_numeric_dtype(df[col])
        n_uniq = df[col].nunique()
        if pct == 0:
            strategy = "none_needed"
        elif pct < 5:
            strategy = "median_impute" if is_num else "mode_impute"
        elif pct < 15:
            strategy = "knn_impute" if is_num else "mode_impute"
        elif pct < 40:
            strategy = "mice_impute" if is_num else "indicator_flag"
        elif pct < 60:
            strategy = "indicator_flag"
        else:
            strategy = "drop_column"
        mnar_risk = pct > 20 and n_uniq <= 5 and is_num
        missing_per_col[col] = {
            "n_missing": n_miss, "pct_missing": pct,
            "recommended_strategy": strategy,
            "mnar_risk": mnar_risk,
            "description": _missing_description(pct, strategy),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 7 — Inconsistency detection
    # ══════════════════════════════════════════════════════════════════════════
    inconsistencies = {}
    for col in df.select_dtypes(include="object").columns:
        try:
            non_null_vals = df[col].dropna().astype(str)
            if non_null_vals.empty:
                continue
            lower_groups: dict = {}
            for val in non_null_vals.unique():
                key = val.strip().lower()
                lower_groups.setdefault(key, []).append(val)
            case_variants = {k: v for k, v in lower_groups.items() if len(v) > 1}
            val_counts = non_null_vals.value_counts(normalize=True)
            rare_vals = val_counts[val_counts < 0.01].index.tolist()[:5]
            if case_variants or rare_vals:
                inconsistencies[col] = {}
                if case_variants:
                    inconsistencies[col]["case_variants"] = case_variants
                if rare_vals:
                    inconsistencies[col]["rare_values"] = rare_vals
                    inconsistencies[col]["rare_note"] = "Values appearing <1% — may be typos or encoding errors"
        except Exception:
            pass

    if inconsistencies:
        actions_taken.append({
            "action": "inconsistencies_detected", "count": len(inconsistencies),
            "description": f"Inconsistencies found in {len(inconsistencies)} column(s) — review recommended"
        })

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 8 — Outlier detection (IQR + Z-score dual method)
    # ══════════════════════════════════════════════════════════════════════════
    outlier_report = {}
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    for col in num_cols[:30]:
        try:
            series = df[col].dropna()
            if len(series) < 4:
                continue
            Q1, Q3 = float(series.quantile(0.25)), float(series.quantile(0.75))
            IQR = Q3 - Q1
            iqr_outliers = 0
            iqr_lower = iqr_upper = None
            if IQR > 0:
                iqr_lower, iqr_upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
                iqr_outliers = int(((series < iqr_lower) | (series > iqr_upper)).sum())
            z_outliers = 0
            if len(series) >= 10:
                std = series.std()
                if std > 0:
                    z_scores = (series - series.mean()) / std
                    z_outliers = int((z_scores.abs() > 3).sum())
            total = max(iqr_outliers, z_outliers)
            if total > 0:
                pct_out = round(total / len(series) * 100, 1)
                outlier_report[col] = {
                    "n_outliers_iqr": iqr_outliers, "n_outliers_zscore": z_outliers,
                    "pct_outliers": pct_out,
                    "lower_fence": round(iqr_lower, 4) if iqr_lower is not None else None,
                    "upper_fence": round(iqr_upper, 4) if iqr_upper is not None else None,
                    "min": round(float(series.min()), 4), "max": round(float(series.max()), 4),
                    "mean": round(float(series.mean()), 4),
                    "treatment_options": _outlier_treatments(pct_out),
                }
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 9 — Column profiles + skewness & distribution
    # ══════════════════════════════════════════════════════════════════════════
    skewed_columns = []
    column_profiles = {}
    for col in df.columns:
        try:
            s = df[col]
            n_miss = int(s.isna().sum())
            pct_miss = round(n_miss / len(df) * 100, 1) if len(df) > 0 else 0.0
            n_uniq = int(s.nunique())
            is_num = pd.api.types.is_numeric_dtype(s)
            is_dt = pd.api.types.is_datetime64_any_dtype(s)
            if is_dt:
                inferred = "datetime"
            elif is_num:
                inferred = "binary" if n_uniq <= 2 else ("ordinal" if n_uniq <= 7 else "continuous")
            else:
                inferred = "categorical" if n_uniq <= 10 else "text/high-cardinality"
            cardinality = (
                "binary" if n_uniq <= 2 else
                "low" if n_uniq <= 10 else
                "medium" if n_uniq <= 50 else "high"
            )
            profile: dict = {
                "dtype": str(s.dtype), "inferred_type": inferred,
                "n_missing": n_miss, "pct_missing": pct_miss,
                "n_unique": n_uniq, "cardinality": cardinality, "issues": []
            }
            if is_num:
                vals = s.dropna()
                if len(vals) > 0:
                    profile.update({
                        "mean": round(float(vals.mean()), 4), "std": round(float(vals.std()), 4),
                        "min": round(float(vals.min()), 4), "max": round(float(vals.max()), 4),
                        "median": round(float(vals.median()), 4),
                        "q1": round(float(vals.quantile(0.25)), 4),
                        "q3": round(float(vals.quantile(0.75)), 4),
                    })
                    skew = _safe_skew(vals)
                    kurt = _safe_kurt(vals)
                    if skew is not None:
                        profile["skewness"] = skew
                        if abs(skew) > 2:
                            profile["skew_severity"] = "high"
                            profile["issues"].append(f"Highly skewed (skew={skew}) — consider log/sqrt transform")
                            skewed_columns.append(col)
                        elif abs(skew) > 1:
                            profile["skew_severity"] = "moderate"
                            profile["issues"].append(f"Moderately skewed (skew={skew})")
                        else:
                            profile["skew_severity"] = "low"
                    if kurt is not None:
                        profile["kurtosis"] = kurt
                    profile["recommended_scaling"] = (
                        "log_transform" if abs(skew or 0) > 1 else
                        "z_score" if n_uniq > 10 else "min_max"
                    )
                if col in outlier_report:
                    profile["n_outliers_iqr"] = outlier_report[col]["n_outliers_iqr"]
                    profile["n_outliers_zscore"] = outlier_report[col]["n_outliers_zscore"]
                    profile["issues"].append(f"{outlier_report[col]['n_outliers_iqr']} outlier(s) detected (IQR)")
            if pct_miss > 0:
                ms = missing_per_col.get(col, {})
                profile["recommended_missing_strategy"] = ms.get("recommended_strategy", "flag_only")
                if pct_miss > 20:
                    profile["issues"].append(f"{pct_miss}% missing — {ms.get('recommended_strategy', 'review')}")
                elif pct_miss > 5:
                    profile["issues"].append(f"{pct_miss}% missing values")
            column_profiles[col] = profile
        except Exception:
            column_profiles[col] = {"dtype": str(df[col].dtype), "issues": []}

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 10 — Class imbalance detection
    # ══════════════════════════════════════════════════════════════════════════
    class_imbalance = {}
    for col in df.columns:
        try:
            s = df[col].dropna()
            n_uniq = s.nunique()
            if 2 <= n_uniq <= 10 and len(s) >= 20:
                vc = s.value_counts(normalize=True)
                minority_pct = round(float(vc.min()) * 100, 1)
                imbalanced = minority_pct < 20 and n_uniq <= 5
                class_imbalance[col] = {
                    "class_ratios": {str(k): round(float(v), 4) for k, v in vc.items()},
                    "minority_pct": minority_pct, "imbalanced": imbalanced,
                    "suggestion": (
                        "Consider SMOTE or class_weight='balanced' if this is a target variable"
                        if imbalanced else "Class distribution acceptable"
                    ),
                }
                if imbalanced and col in column_profiles:
                    column_profiles[col]["issues"].append(f"Class imbalance — minority class is {minority_pct}%")
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 11 — Data quality score (0-100)
    # ══════════════════════════════════════════════════════════════════════════
    n_rows_now = len(df)
    n_cols_now = len(df.columns)
    total_cells = n_rows_now * n_cols_now
    missing_cells = int(df.isnull().sum().sum())
    completeness = (1 - missing_cells / total_cells) if total_cells > 0 else 1.0
    completeness_score = completeness * 40
    dup_score = max(0.0, 1.0 - (n_duplicates / max(shape_before["rows"], 1)) * 5) * 20
    n_obj = len(df.select_dtypes(include="object").columns)
    type_score = max(0.0, 1.0 - (n_obj / max(n_cols_now, 1)) * 0.5) * 20
    total_out = sum(v.get("n_outliers_iqr", 0) for v in outlier_report.values())
    outlier_score = max(0.0, 1.0 - (total_out / max(total_cells, 1)) * 50) * 20
    data_quality_score = round(completeness_score + dup_score + type_score + outlier_score, 1)
    quality_label = (
        "Excellent" if data_quality_score >= 90 else
        "Good" if data_quality_score >= 75 else
        "Fair" if data_quality_score >= 55 else "Poor"
    )

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 12 — Final assembly
    # ══════════════════════════════════════════════════════════════════════════
    shape_after = {"rows": int(len(df)), "columns": int(len(df.columns))}
    pct_complete_rows = round(df.dropna().shape[0] / len(df) * 100, 1) if len(df) > 0 else 0.0

    inspection_report = {
        "shape_before": shape_before, "shape_after": shape_after,
        "data_quality_score": data_quality_score, "quality_label": quality_label,
        "completeness_pct": round(completeness * 100, 1), "pct_complete_rows": pct_complete_rows,
        "total_missing_cells": missing_cells,
        "n_duplicates_found": n_duplicates, "n_empty_columns_dropped": len(dropped_cols),
        "dropped_columns": dropped_cols, "type_fixes_applied": type_fixes_applied,
        "column_profiles": column_profiles, "missing_per_column": missing_per_col,
        "outliers": outlier_report, "inconsistencies": inconsistencies,
        "class_imbalance": class_imbalance, "skewed_columns": skewed_columns,
        "actions_taken": actions_taken,
    }
    cleaning_summary = {
        "actions_taken": actions_taken,
        "rows_before": shape_before["rows"], "rows_after": shape_after["rows"],
        "columns_before": shape_before["columns"], "columns_after": shape_after["columns"],
        "cleaned": len(actions_taken) > 0,
        "data_quality_score": data_quality_score, "quality_label": quality_label,
    }
    return df, inspection_report, cleaning_summary


# ══════════════════════════════════════════════════════════════════════════════
# NEW STAGE 1 PIPELINE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def profile_only(df) -> dict:
    """
    READ-ONLY profile of a DataFrame — detects issues without modifying data.
    Used as Stage 1a of the new preprocessing pipeline gate.
    Returns the full inspection_report dict but does NOT change the DataFrame.
    """
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        return {}

    # We call clean_and_inspect on a copy so the original is untouched
    df_copy = df.copy()
    _, inspection_report, _ = clean_and_inspect(df_copy)
    return inspection_report


def auto_clean(df, inspection_report: dict) -> tuple:
    """
    Applies AI-chosen best cleaning strategy per column based on the inspection_report.
    Returns (df_clean, cleaning_summary).

    Strategy rules (matching the recommendations already in the inspection_report):
    - missing values   → apply recommended_strategy per column
    - outliers (<2%)   → remove rows; (≥2%) → Winsorize to 1st/99th percentile
    - skewed columns   → log1p transform (if all values ≥ 0)
    - inconsistencies  → standardise case (title-case) for object columns
    - duplicates       → already handled by profile_only (via clean_and_inspect copy)
      but we re-apply on original df
    """
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        return df, {"cleaned": False, "actions_taken": [], "mode": "auto"}

    df = df.copy()
    actions_taken = []
    shape_before = {"rows": int(len(df)), "columns": int(len(df.columns))}

    # ── Always: strip whitespace + null synonyms ─────────────────────────────
    for col in df.select_dtypes(include="object").columns:
        try:
            df[col] = df[col].astype(str).str.strip()
            df[col] = _to_null_synonyms(df[col], pd)
        except Exception:
            pass

    # ── Always: type fixes ────────────────────────────────────────────────────
    BOOL_MAP = {"true": True, "false": False, "yes": True, "no": False, "1": True, "0": False, "y": True, "n": False}
    type_fixes = []
    for col in list(df.columns):
        s = df[col]
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
            continue
        non_null = s.dropna()
        if len(non_null) == 0:
            continue
        lower_vals = set(non_null.astype(str).str.lower().unique())
        if lower_vals <= set(BOOL_MAP.keys()):
            try:
                df[col] = s.astype(str).str.lower().map(lambda x: BOOL_MAP.get(x, pd.NA))
                type_fixes.append(col)
                continue
            except Exception:
                pass
        num_attempt = pd.to_numeric(non_null.astype(str).str.replace(",", ""), errors="coerce")
        if num_attempt.notna().mean() >= 0.80:
            try:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
                type_fixes.append(col)
                continue
            except Exception:
                pass
    if type_fixes:
        actions_taken.append({"action": "data_types_fixed", "count": len(type_fixes),
                               "description": f"Auto-fixed data types on {len(type_fixes)} column(s)", "columns": type_fixes})

    # ── Always: drop exact duplicates ────────────────────────────────────────
    n_dup = int(df.duplicated().sum())
    if n_dup > 0:
        df = df.drop_duplicates().reset_index(drop=True)
        actions_taken.append({"action": "duplicates_removed", "count": n_dup,
                               "description": f"Removed {n_dup} exact duplicate row(s)"})

    # ── Always: drop >=95% missing columns ───────────────────────────────────
    if len(df) > 0:
        pct_miss_cols = df.isnull().mean()
        cols_to_drop = pct_miss_cols[pct_miss_cols >= 0.95].index.tolist()
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            actions_taken.append({"action": "empty_columns_dropped", "count": len(cols_to_drop),
                                   "columns": cols_to_drop,
                                   "description": f"Auto-dropped {len(cols_to_drop)} near-empty column(s)"})

    # ── Missing value imputation ─────────────────────────────────────────────
    missing_info = inspection_report.get("missing_per_column", {})
    imputed_cols = []
    for col in df.columns:
        if col not in missing_info:
            continue
        info = missing_info[col]
        strategy = info.get("recommended_strategy", "none_needed")
        if strategy == "none_needed":
            continue
        try:
            if strategy == "drop_column":
                df = df.drop(columns=[col])
                actions_taken.append({"action": "column_dropped", "column": col,
                                       "description": f"Auto-dropped '{col}' (>50% missing)"})
                continue
            s = df[col]
            is_num = pd.api.types.is_numeric_dtype(s)
            if strategy in ("median_impute",) and is_num:
                df[col] = s.fillna(s.median())
            elif strategy in ("mean_impute",) and is_num:
                df[col] = s.fillna(s.mean())
            elif strategy in ("knn_impute",) and is_num:
                # Fallback to median if sklearn not available
                try:
                    from sklearn.impute import KNNImputer
                    imp = KNNImputer(n_neighbors=5)
                    df[[col]] = imp.fit_transform(df[[col]])
                except ImportError:
                    df[col] = s.fillna(s.median())
            elif strategy in ("mice_impute",) and is_num:
                try:
                    from sklearn.experimental import enable_iterative_imputer  # noqa
                    from sklearn.impute import IterativeImputer
                    imp = IterativeImputer(max_iter=10, random_state=42)
                    df[[col]] = imp.fit_transform(df[[col]])
                except ImportError:
                    df[col] = s.fillna(s.median())
            elif strategy in ("mode_impute", "indicator_flag") or not is_num:
                mode_val = s.mode(dropna=True)
                if len(mode_val) > 0:
                    df[col] = s.fillna(mode_val.iloc[0])
            imputed_cols.append({"col": col, "strategy": strategy})
        except Exception:
            pass
    if imputed_cols:
        actions_taken.append({"action": "missing_imputed", "count": len(imputed_cols),
                               "description": f"Auto-imputed missing values in {len(imputed_cols)} column(s)",
                               "details": imputed_cols})

    # ── Outlier treatment ─────────────────────────────────────────────────────
    outlier_info = inspection_report.get("outliers", {})
    winsorized = []
    removed_outlier_mask = pd.Series([True] * len(df), index=df.index)
    for col, info in outlier_info.items():
        if col not in df.columns:
            continue
        pct = info.get("pct_outliers", 0)
        try:
            lower = df[col].quantile(0.01)
            upper = df[col].quantile(0.99)
            if pct < 2.0:
                # Remove rows with extreme outliers (small count, likely errors)
                mask = (df[col] >= lower) & (df[col] <= upper)
                removed_outlier_mask = removed_outlier_mask & mask
            else:
                # Winsorize — clip to 1st/99th percentile
                df[col] = df[col].clip(lower=lower, upper=upper)
                winsorized.append(col)
        except Exception:
            pass
    # Apply row removals for <2% outlier columns
    rows_before_outlier = len(df)
    df = df[removed_outlier_mask].reset_index(drop=True)
    rows_removed = rows_before_outlier - len(df)
    if rows_removed > 0:
        actions_taken.append({"action": "outlier_rows_removed", "count": rows_removed,
                               "description": f"Removed {rows_removed} row(s) with extreme outliers (<2%)"})
    if winsorized:
        actions_taken.append({"action": "outliers_winsorized", "count": len(winsorized),
                               "description": f"Winsorized outliers in {len(winsorized)} column(s) to 1st/99th percentile",
                               "columns": winsorized})

    # ── Skewness: log1p transform for highly skewed positive numeric columns ──
    skewed = inspection_report.get("skewed_columns", [])
    transformed = []
    for col in skewed:
        if col not in df.columns:
            continue
        try:
            s = df[col].dropna()
            if pd.api.types.is_numeric_dtype(df[col]) and (s >= 0).all():
                df[col] = np.log1p(df[col])
                transformed.append(col)
        except Exception:
            pass
    if transformed:
        actions_taken.append({"action": "log_transformed", "count": len(transformed),
                               "description": f"Log1p-transformed {len(transformed)} skewed column(s)",
                               "columns": transformed})

    # ── Inconsistencies: standardise case for object columns ──────────────────
    inconsistencies = inspection_report.get("inconsistencies", {})
    standardised = []
    for col in inconsistencies:
        if col not in df.columns:
            continue
        try:
            if df[col].dtype == object:
                df[col] = df[col].str.strip().str.title()
                standardised.append(col)
        except Exception:
            pass
    if standardised:
        actions_taken.append({"action": "case_standardised", "count": len(standardised),
                               "description": f"Standardised text case in {len(standardised)} column(s)",
                               "columns": standardised})

    shape_after = {"rows": int(len(df)), "columns": int(len(df.columns))}
    cleaning_summary = {
        "mode": "auto",
        "actions_taken": actions_taken,
        "rows_before": shape_before["rows"], "rows_after": shape_after["rows"],
        "columns_before": shape_before["columns"], "columns_after": shape_after["columns"],
        "cleaned": len(actions_taken) > 0,
    }
    return df, cleaning_summary


def manual_clean(df, manual_choices: dict) -> tuple:
    """
    Applies user-selected preprocessing choices per column.
    manual_choices: { "column_name": "strategy_id", ... }

    Supported strategies:
        median_impute, mean_impute, mode_impute, knn_impute, mice_impute,
        drop_column, remove_outliers, winsorize, log_transform,
        standardise_case, keep
    """
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        return df, {"cleaned": False, "actions_taken": [], "mode": "manual"}

    df = df.copy()
    actions_taken = []
    shape_before = {"rows": int(len(df)), "columns": int(len(df.columns))}

    # ── Always: strip whitespace + null synonyms ─────────────────────────────
    for col in df.select_dtypes(include="object").columns:
        try:
            df[col] = df[col].astype(str).str.strip()
            df[col] = _to_null_synonyms(df[col], pd)
        except Exception:
            pass

    # ── Always: drop exact duplicates ────────────────────────────────────────
    n_dup = int(df.duplicated().sum())
    if n_dup > 0:
        df = df.drop_duplicates().reset_index(drop=True)
        actions_taken.append({"action": "duplicates_removed", "count": n_dup,
                               "description": f"Removed {n_dup} duplicate row(s)"})

    # ── Apply user choices per column ─────────────────────────────────────────
    for col, strategy in manual_choices.items():
        if col not in df.columns or strategy == "keep":
            continue
        try:
            s = df[col]
            is_num = pd.api.types.is_numeric_dtype(s)

            if strategy == "drop_column":
                df = df.drop(columns=[col])
                actions_taken.append({"action": "column_dropped", "column": col,
                                       "description": f"Dropped column '{col}' (user choice)"})
                continue

            elif strategy == "median_impute" and is_num:
                df[col] = s.fillna(s.median())
                actions_taken.append({"action": "imputed", "column": col, "strategy": "median"})

            elif strategy == "mean_impute" and is_num:
                df[col] = s.fillna(s.mean())
                actions_taken.append({"action": "imputed", "column": col, "strategy": "mean"})

            elif strategy == "mode_impute":
                mode_val = s.mode(dropna=True)
                if len(mode_val) > 0:
                    df[col] = s.fillna(mode_val.iloc[0])
                actions_taken.append({"action": "imputed", "column": col, "strategy": "mode"})

            elif strategy == "knn_impute" and is_num:
                try:
                    from sklearn.impute import KNNImputer
                    df[[col]] = KNNImputer(n_neighbors=5).fit_transform(df[[col]])
                except ImportError:
                    df[col] = s.fillna(s.median())
                actions_taken.append({"action": "imputed", "column": col, "strategy": "knn"})

            elif strategy == "mice_impute" and is_num:
                try:
                    from sklearn.experimental import enable_iterative_imputer  # noqa
                    from sklearn.impute import IterativeImputer
                    df[[col]] = IterativeImputer(max_iter=10, random_state=42).fit_transform(df[[col]])
                except ImportError:
                    df[col] = s.fillna(s.median())
                actions_taken.append({"action": "imputed", "column": col, "strategy": "mice"})

            elif strategy == "remove_outliers" and is_num:
                lower, upper = df[col].quantile(0.01), df[col].quantile(0.99)
                before = len(df)
                df = df[(df[col] >= lower) & (df[col] <= upper)].reset_index(drop=True)
                removed = before - len(df)
                actions_taken.append({"action": "outliers_removed", "column": col,
                                       "count": removed, "description": f"Removed {removed} outlier rows from '{col}'"})

            elif strategy == "winsorize" and is_num:
                lower, upper = df[col].quantile(0.01), df[col].quantile(0.99)
                df[col] = df[col].clip(lower=lower, upper=upper)
                actions_taken.append({"action": "winsorized", "column": col,
                                       "description": f"Winsorized '{col}' to 1st/99th percentile"})

            elif strategy == "log_transform" and is_num:
                if (df[col].dropna() >= 0).all():
                    df[col] = np.log1p(df[col])
                    actions_taken.append({"action": "log_transformed", "column": col,
                                           "description": f"Log1p-transformed '{col}'"})

            elif strategy == "standardise_case":
                if df[col].dtype == object:
                    df[col] = df[col].str.strip().str.title()
                    actions_taken.append({"action": "case_standardised", "column": col,
                                           "description": f"Standardised case in '{col}'"})

        except Exception as e:
            actions_taken.append({"action": "error", "column": col, "error": str(e)})

    shape_after = {"rows": int(len(df)), "columns": int(len(df.columns))}
    cleaning_summary = {
        "mode": "manual",
        "actions_taken": actions_taken,
        "rows_before": shape_before["rows"], "rows_after": shape_after["rows"],
        "columns_before": shape_before["columns"], "columns_after": shape_after["columns"],
        "cleaned": len(actions_taken) > 0,
    }
    return df, cleaning_summary

    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        return df, {}, {}

    shape_before = {"rows": int(len(df)), "columns": int(len(df.columns))}
    actions_taken = []
    type_fixes_applied = []

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 2 — Strip whitespace + null synonyms from object columns
    # ══════════════════════════════════════════════════════════════════════════
    for col in df.select_dtypes(include="object").columns:
        try:
            df[col] = df[col].astype(str).str.strip()
            df[col] = _to_null_synonyms(df[col], pd)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 3 — Fix data types
    # ══════════════════════════════════════════════════════════════════════════
    BOOL_MAP = {
        "true": True, "false": False, "yes": True, "no": False,
        "1": True, "0": False, "y": True, "n": False,
    }
    for col in list(df.columns):
        s = df[col]
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
            continue
        non_null = s.dropna()
        if len(non_null) == 0:
            continue
        lower_vals = set(non_null.astype(str).str.lower().unique())
        # 3a. Boolean detection
        if lower_vals <= set(BOOL_MAP.keys()):
            try:
                df[col] = s.astype(str).str.lower().map(lambda x: BOOL_MAP.get(x, pd.NA))
                type_fixes_applied.append({
                    "column": col, "from": "object", "to": "boolean",
                    "reason": "Only true/false/yes/no values"
                })
                continue
            except Exception:
                pass
        # 3b. Numeric strings
        num_attempt = pd.to_numeric(non_null.astype(str).str.replace(",", ""), errors="coerce")
        if num_attempt.notna().mean() >= 0.80:
            try:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
                type_fixes_applied.append({
                    "column": col, "from": "object", "to": "numeric",
                    "reason": ">=80% values parseable as numbers"
                })
                continue
            except Exception:
                pass
        # 3c. Datetime strings
        if non_null.astype(str).str.match(r"^\d{1,4}[-/\.]\d{1,2}[-/\.]").mean() >= 0.60:
            try:
                dt_attempt = pd.to_datetime(non_null.astype(str), errors="coerce", infer_datetime_format=True)
                if dt_attempt.notna().mean() >= 0.60:
                    df[col] = pd.to_datetime(df[col].astype(str), errors="coerce", infer_datetime_format=True)
                    type_fixes_applied.append({
                        "column": col, "from": "object", "to": "datetime",
                        "reason": ">=60% values match date patterns"
                    })
                    continue
            except Exception:
                pass

    if type_fixes_applied:
        actions_taken.append({
            "action": "data_types_fixed", "count": len(type_fixes_applied),
            "description": f"Fixed data types on {len(type_fixes_applied)} column(s)",
            "details": type_fixes_applied
        })

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 4 — Exact duplicate removal
    # ══════════════════════════════════════════════════════════════════════════
    n_duplicates = int(df.duplicated().sum())
    if n_duplicates > 0:
        df = df.drop_duplicates().reset_index(drop=True)
        actions_taken.append({
            "action": "duplicates_removed", "count": n_duplicates,
            "description": f"Removed {n_duplicates} exact duplicate row(s)"
        })

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 5 — Drop columns >=95% missing
    # ══════════════════════════════════════════════════════════════════════════
    dropped_cols = []
    if len(df) > 0:
        pct_miss_cols = df.isnull().mean()
        cols_to_drop = pct_miss_cols[pct_miss_cols >= 0.95].index.tolist()
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            dropped_cols = cols_to_drop
            actions_taken.append({
                "action": "empty_columns_dropped", "count": len(cols_to_drop),
                "columns": cols_to_drop,
                "description": f"Dropped {len(cols_to_drop)} column(s) with >=95% missing"
            })

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 6 — Missing value analysis + strategy recommendations
    # ══════════════════════════════════════════════════════════════════════════
    missing_per_col = {}
    for col in df.columns:
        n_miss = int(df[col].isna().sum())
        pct = round(n_miss / len(df) * 100, 1) if len(df) > 0 else 0.0
        is_num = pd.api.types.is_numeric_dtype(df[col])
        n_uniq = df[col].nunique()
        if pct == 0:
            strategy = "none_needed"
        elif pct < 5:
            strategy = "median_impute" if is_num else "mode_impute"
        elif pct < 15:
            strategy = "knn_impute" if is_num else "mode_impute"
        elif pct < 40:
            strategy = "mice_impute" if is_num else "indicator_flag"
        elif pct < 60:
            strategy = "indicator_flag"
        else:
            strategy = "drop_column"
        mnar_risk = pct > 20 and n_uniq <= 5 and is_num
        missing_per_col[col] = {
            "n_missing": n_miss, "pct_missing": pct,
            "recommended_strategy": strategy,
            "mnar_risk": mnar_risk,
            "description": _missing_description(pct, strategy),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 7 — Inconsistency detection
    # ══════════════════════════════════════════════════════════════════════════
    inconsistencies = {}
    for col in df.select_dtypes(include="object").columns:
        try:
            non_null_vals = df[col].dropna().astype(str)
            if non_null_vals.empty:
                continue
            lower_groups: dict = {}
            for val in non_null_vals.unique():
                key = val.strip().lower()
                lower_groups.setdefault(key, []).append(val)
            case_variants = {k: v for k, v in lower_groups.items() if len(v) > 1}
            val_counts = non_null_vals.value_counts(normalize=True)
            rare_vals = val_counts[val_counts < 0.01].index.tolist()[:5]
            if case_variants or rare_vals:
                inconsistencies[col] = {}
                if case_variants:
                    inconsistencies[col]["case_variants"] = case_variants
                if rare_vals:
                    inconsistencies[col]["rare_values"] = rare_vals
                    inconsistencies[col]["rare_note"] = "Values appearing <1% — may be typos or encoding errors"
        except Exception:
            pass

    if inconsistencies:
        actions_taken.append({
            "action": "inconsistencies_detected", "count": len(inconsistencies),
            "description": f"Inconsistencies found in {len(inconsistencies)} column(s) — review recommended"
        })

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 8 — Outlier detection (IQR + Z-score dual method)
    # ══════════════════════════════════════════════════════════════════════════
    outlier_report = {}
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    for col in num_cols[:30]:
        try:
            series = df[col].dropna()
            if len(series) < 4:
                continue
            Q1, Q3 = float(series.quantile(0.25)), float(series.quantile(0.75))
            IQR = Q3 - Q1
            iqr_outliers = 0
            iqr_lower = iqr_upper = None
            if IQR > 0:
                iqr_lower, iqr_upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
                iqr_outliers = int(((series < iqr_lower) | (series > iqr_upper)).sum())
            z_outliers = 0
            if len(series) >= 10:
                std = series.std()
                if std > 0:
                    z_scores = (series - series.mean()) / std
                    z_outliers = int((z_scores.abs() > 3).sum())
            total = max(iqr_outliers, z_outliers)
            if total > 0:
                pct_out = round(total / len(series) * 100, 1)
                outlier_report[col] = {
                    "n_outliers_iqr": iqr_outliers, "n_outliers_zscore": z_outliers,
                    "pct_outliers": pct_out,
                    "lower_fence": round(iqr_lower, 4) if iqr_lower is not None else None,
                    "upper_fence": round(iqr_upper, 4) if iqr_upper is not None else None,
                    "min": round(float(series.min()), 4), "max": round(float(series.max()), 4),
                    "mean": round(float(series.mean()), 4),
                    "treatment_options": _outlier_treatments(pct_out),
                }
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 9 — Column profiles + skewness & distribution
    # ══════════════════════════════════════════════════════════════════════════
    skewed_columns = []
    column_profiles = {}
    for col in df.columns:
        try:
            s = df[col]
            n_miss = int(s.isna().sum())
            pct_miss = round(n_miss / len(df) * 100, 1) if len(df) > 0 else 0.0
            n_uniq = int(s.nunique())
            is_num = pd.api.types.is_numeric_dtype(s)
            is_dt = pd.api.types.is_datetime64_any_dtype(s)
            if is_dt:
                inferred = "datetime"
            elif is_num:
                inferred = "binary" if n_uniq <= 2 else ("ordinal" if n_uniq <= 7 else "continuous")
            else:
                inferred = "categorical" if n_uniq <= 10 else "text/high-cardinality"
            cardinality = (
                "binary" if n_uniq <= 2 else
                "low" if n_uniq <= 10 else
                "medium" if n_uniq <= 50 else "high"
            )
            profile: dict = {
                "dtype": str(s.dtype), "inferred_type": inferred,
                "n_missing": n_miss, "pct_missing": pct_miss,
                "n_unique": n_uniq, "cardinality": cardinality, "issues": []
            }
            if is_num:
                vals = s.dropna()
                if len(vals) > 0:
                    profile.update({
                        "mean": round(float(vals.mean()), 4), "std": round(float(vals.std()), 4),
                        "min": round(float(vals.min()), 4), "max": round(float(vals.max()), 4),
                        "median": round(float(vals.median()), 4),
                        "q1": round(float(vals.quantile(0.25)), 4),
                        "q3": round(float(vals.quantile(0.75)), 4),
                    })
                    skew = _safe_skew(vals)
                    kurt = _safe_kurt(vals)
                    if skew is not None:
                        profile["skewness"] = skew
                        if abs(skew) > 2:
                            profile["skew_severity"] = "high"
                            profile["issues"].append(f"Highly skewed (skew={skew}) — consider log/sqrt transform")
                            skewed_columns.append(col)
                        elif abs(skew) > 1:
                            profile["skew_severity"] = "moderate"
                            profile["issues"].append(f"Moderately skewed (skew={skew})")
                        else:
                            profile["skew_severity"] = "low"
                    if kurt is not None:
                        profile["kurtosis"] = kurt
                    profile["recommended_scaling"] = (
                        "log_transform" if abs(skew or 0) > 1 else
                        "z_score" if n_uniq > 10 else "min_max"
                    )
                if col in outlier_report:
                    profile["n_outliers_iqr"] = outlier_report[col]["n_outliers_iqr"]
                    profile["n_outliers_zscore"] = outlier_report[col]["n_outliers_zscore"]
                    profile["issues"].append(f"{outlier_report[col]['n_outliers_iqr']} outlier(s) detected (IQR)")
            if pct_miss > 0:
                ms = missing_per_col.get(col, {})
                profile["recommended_missing_strategy"] = ms.get("recommended_strategy", "flag_only")
                if pct_miss > 20:
                    profile["issues"].append(f"{pct_miss}% missing — {ms.get('recommended_strategy', 'review')}")
                elif pct_miss > 5:
                    profile["issues"].append(f"{pct_miss}% missing values")
            column_profiles[col] = profile
        except Exception:
            column_profiles[col] = {"dtype": str(df[col].dtype), "issues": []}

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 10 — Class imbalance detection
    # ══════════════════════════════════════════════════════════════════════════
    class_imbalance = {}
    for col in df.columns:
        try:
            s = df[col].dropna()
            n_uniq = s.nunique()
            if 2 <= n_uniq <= 10 and len(s) >= 20:
                vc = s.value_counts(normalize=True)
                minority_pct = round(float(vc.min()) * 100, 1)
                imbalanced = minority_pct < 20 and n_uniq <= 5
                class_imbalance[col] = {
                    "class_ratios": {str(k): round(float(v), 4) for k, v in vc.items()},
                    "minority_pct": minority_pct, "imbalanced": imbalanced,
                    "suggestion": (
                        "Consider SMOTE or class_weight='balanced' if this is a target variable"
                        if imbalanced else "Class distribution acceptable"
                    ),
                }
                if imbalanced and col in column_profiles:
                    column_profiles[col]["issues"].append(f"Class imbalance — minority class is {minority_pct}%")
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 11 — Data quality score (0-100)
    # ══════════════════════════════════════════════════════════════════════════
    n_rows_now = len(df)
    n_cols_now = len(df.columns)
    total_cells = n_rows_now * n_cols_now
    missing_cells = int(df.isnull().sum().sum())
    completeness = (1 - missing_cells / total_cells) if total_cells > 0 else 1.0
    completeness_score = completeness * 40
    dup_score = max(0.0, 1.0 - (n_duplicates / max(shape_before["rows"], 1)) * 5) * 20
    n_obj = len(df.select_dtypes(include="object").columns)
    type_score = max(0.0, 1.0 - (n_obj / max(n_cols_now, 1)) * 0.5) * 20
    total_out = sum(v.get("n_outliers_iqr", 0) for v in outlier_report.values())
    outlier_score = max(0.0, 1.0 - (total_out / max(total_cells, 1)) * 50) * 20
    data_quality_score = round(completeness_score + dup_score + type_score + outlier_score, 1)
    quality_label = (
        "Excellent" if data_quality_score >= 90 else
        "Good" if data_quality_score >= 75 else
        "Fair" if data_quality_score >= 55 else "Poor"
    )

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 12 — Final assembly
    # ══════════════════════════════════════════════════════════════════════════
    shape_after = {"rows": int(len(df)), "columns": int(len(df.columns))}
    pct_complete_rows = round(df.dropna().shape[0] / len(df) * 100, 1) if len(df) > 0 else 0.0

    inspection_report = {
        "shape_before": shape_before, "shape_after": shape_after,
        "data_quality_score": data_quality_score, "quality_label": quality_label,
        "completeness_pct": round(completeness * 100, 1), "pct_complete_rows": pct_complete_rows,
        "total_missing_cells": missing_cells,
        "n_duplicates_found": n_duplicates, "n_empty_columns_dropped": len(dropped_cols),
        "dropped_columns": dropped_cols, "type_fixes_applied": type_fixes_applied,
        "column_profiles": column_profiles, "missing_per_column": missing_per_col,
        "outliers": outlier_report, "inconsistencies": inconsistencies,
        "class_imbalance": class_imbalance, "skewed_columns": skewed_columns,
        "actions_taken": actions_taken,
    }
    cleaning_summary = {
        "actions_taken": actions_taken,
        "rows_before": shape_before["rows"], "rows_after": shape_after["rows"],
        "columns_before": shape_before["columns"], "columns_after": shape_after["columns"],
        "cleaned": len(actions_taken) > 0,
        "data_quality_score": data_quality_score, "quality_label": quality_label,
    }
    return df, inspection_report, cleaning_summary

# ══════════════════════════════════════════════════════════════════════════════
# AI-POWERED UNIVERSAL STANDARDISATION
# ══════════════════════════════════════════════════════════════════════════════

def ai_standardise_inconsistencies(df, llm_client=None) -> dict:
    """
    Scan ALL text (object) columns in the DataFrame.
    For each low-cardinality column, detect inconsistencies in ANY type of data:

    Examples of what it catches:
      Gender:     "male", "Male", "MALE", "M", "m" → "Male"
      Education:  "BSc", "B.Sc", "bachelor", "Bachelor's" → "Bachelor's Degree"
      Country:    "NG", "NGA", "Nigeria", "nigeria" → "Nigeria"
      Yes/No:     "Yes", "YES", "yes", "Y", "y", "1" → "Yes"
      Employment: "Employed", "employed", "EMPLOYED", "full-time" → "Employed"
      Age group:  "18-24", "18 - 24", "18to24" → "18-24"
      Ethnicity:  any variants → canonical form

    Strategy:
      1. Case-variant clustering (heuristic — always runs, no AI needed)
         Groups values that are identical when lowercased/stripped.
         Picks the most-frequent form as canonical.

      2. Abbreviation/synonym detection (heuristic — always runs)
         Known short-form patterns: single letters, 2-3 letter codes,
         common abbreviations (Y/N, M/F, BSc/Bsc/B.Sc, etc.)

      3. AI semantic clustering (optional — uses Claude if llm_client provided)
         Sends unique values to Claude: "These are unique values from column X.
         Map any non-canonical or inconsistent entries to their canonical form."
         Claude understands context: knows "M" means "Male" in a Gender column,
         "PhD" and "Ph.D" are the same, "YES" and "Yes" are the same, etc.
         This handles cases the heuristics cannot catch.

    Returns:
        {
          "Gender": {
            "mapping": {"M": "Male", "male": "Male", "MALE": "Male"},
            "n_standardised": 35,
            "sample_before": ["M", "male", "MALE"],
            "canonical_values": ["Male", "Female"],
            "method": "heuristic+ai"
          }, ...
        }
    """
    result = {}
    obj_cols = df.select_dtypes(include="object").columns.tolist()

    # ── Known short-form patterns (universal, not just country) ───────────
    # These are common abbreviations across research data
    _COMMON_ABBREVS = {
        # Gender
        "m": "Male", "male": "Male",
        "f": "Female", "female": "Female",
        "fem": "Female",
        # Yes / No
        "y": "Yes", "yes": "Yes", "1": "Yes",
        "n": "No",  "no":  "No",  "0": "No",
        # Agree / Disagree (for non-Likert text versions)
        "agree": "Agree", "strongly agree": "Strongly Agree",
        "disagree": "Disagree", "strongly disagree": "Strongly Disagree",
        "neutral": "Neutral", "undecided": "Neutral",
        # Education levels
        "bsc": "Bachelor's Degree", "b.sc": "Bachelor's Degree",
        "b.sc.": "Bachelor's Degree", "bachelor": "Bachelor's Degree",
        "bachelor's": "Bachelor's Degree", "undergraduate": "Bachelor's Degree",
        "msc": "Master's Degree", "m.sc": "Master's Degree",
        "m.sc.": "Master's Degree", "masters": "Master's Degree",
        "master's": "Master's Degree", "postgraduate": "Master's Degree",
        "phd": "PhD", "ph.d": "PhD", "ph.d.": "PhD", "doctorate": "PhD",
        "hnd": "HND", "ond": "OND", "nce": "NCE",
        # Employment
        "employed": "Employed", "full-time": "Employed",
        "unemployed": "Unemployed", "not employed": "Unemployed",
        "self-employed": "Self-Employed", "self employed": "Self-Employed",
        "retired": "Retired",
        # Marital status
        "single": "Single", "unmarried": "Single",
        "married": "Married",
        "divorced": "Divorced", "separated": "Separated",
        "widowed": "Widowed", "widow": "Widowed",
        # Country codes (ISO 2 and 3 letter — commonly confused)
        "ng": "Nigeria", "nga": "Nigeria",
        "gh": "Ghana", "gha": "Ghana",
        "za": "South Africa", "zaf": "South Africa",
        "ke": "Kenya", "ken": "Kenya",
        "ug": "Uganda", "uga": "Uganda",
        "tz": "Tanzania", "tza": "Tanzania",
        "et": "Ethiopia", "eth": "Ethiopia",
        "cm": "Cameroon", "cmr": "Cameroon",
        "gb": "United Kingdom", "gbr": "United Kingdom", "uk": "United Kingdom",
        "us": "United States", "usa": "United States",
        "ca": "Canada", "can": "Canada",
        "au": "Australia", "aus": "Australia",
        "in": "India", "ind": "India",
        "cn": "China", "chn": "China",
        "de": "Germany", "deu": "Germany",
        "fr": "France", "fra": "France",
    }

    for col in obj_cols:
        series = df[col].dropna().astype(str).str.strip()
        unique_vals = series.unique().tolist()
        n_unique = len(unique_vals)

        # Only process low-cardinality categorical columns
        if n_unique < 2 or n_unique > 60:
            continue

        mapping = {}
        method = "heuristic"

        # ── HEURISTIC 1: Case-variant clustering ──────────────────────────
        # e.g. "male", "Male", "MALE" → pick most-frequent as canonical
        case_groups = {}
        for val in unique_vals:
            case_groups.setdefault(val.strip().lower(), []).append(val)

        freq = series.value_counts()
        for grp_key, variants in case_groups.items():
            if len(variants) > 1:
                canonical = max(variants, key=lambda v: freq.get(v, 0))
                for v in variants:
                    if v != canonical:
                        mapping[v] = canonical

        # ── HEURISTIC 2: Known abbreviation/synonym lookup ────────────────
        # After case-grouping, check if the lowercased form maps to a known canonical
        for val in unique_vals:
            # Skip if already mapped by case-clustering
            if val in mapping:
                continue
            key = val.strip().lower().rstrip(".")
            if key in _COMMON_ABBREVS:
                canonical = _COMMON_ABBREVS[key]
                # Only map if canonical is different and canonical is NOT already in unique_vals
                # (i.e. the abbreviated form is the only way this value appears)
                if val != canonical:
                    # Check if canonical already exists in the column
                    existing_canonical = [v for v in unique_vals if v.strip().lower() == canonical.lower()]
                    target = existing_canonical[0] if existing_canonical else canonical
                    if val != target:
                        mapping[val] = target

        # ── AI SEMANTIC CLUSTERING ────────────────────────────────────────
        # Claude reads ALL unique values with column name context and returns
        # a mapping of non-canonical → canonical for any inconsistencies it finds.
        # This catches: "Ph.D" vs "PhD", "self employed" vs "Self-Employed",
        # "18 - 24" vs "18-24", custom abbreviations, typos, etc.
        if llm_client is not None and n_unique <= 40:
            try:
                sample_str = "\n".join(f'  - "{v}"' for v in unique_vals[:40])
                prompt = (
                    f"I have a survey dataset column named \"{col}\".\n"
                    f"Here are all {n_unique} unique values in this column:\n{sample_str}\n\n"
                    "Your task: identify any values that represent the same concept but are written inconsistently "
                    "(different cases, abbreviations, spelling variants, symbols, codes, synonyms, or typos).\n\n"
                    "Return a JSON object mapping each non-canonical value to its canonical form.\n"
                    "Rules:\n"
                    "- Pick the most complete/formal/common form as canonical\n"
                    "- Include ALL variants that need standardising\n"
                    "- Do NOT include values that are already correct\n"
                    "- Do NOT invent new values — only use values that appear in the list above as canonical targets\n"
                    "  (unless a clearly more standard form exists, like \"Male\" for \"M\")\n"
                    "- If no standardisation is needed, return {}\n\n"
                    "Example output: {\"male\": \"Male\", \"MALE\": \"Male\", \"M\": \"Male\", "
                    "\"Ph.D\": \"PhD\", \"bachelor\": \"Bachelor's Degree\"}"
                )
                ai_resp = llm_client(prompt)
                import json as _json
                # Handle both string response and dict response
                if isinstance(ai_resp, str):
                    # Extract JSON from response (may have surrounding text)
                    import re
                    json_match = re.search(r'\{[^{}]*\}', ai_resp, re.DOTALL)
                    if json_match:
                        ai_mapping = _json.loads(json_match.group())
                    else:
                        ai_mapping = {}
                elif isinstance(ai_resp, dict):
                    ai_mapping = ai_resp
                else:
                    ai_mapping = {}

                if isinstance(ai_mapping, dict):
                    # Merge — AI mapping takes precedence (it has column context)
                    for k, v in ai_mapping.items():
                        if k in unique_vals and k != v:
                            mapping[k] = v
                    if ai_mapping:
                        method = "heuristic+ai"

            except Exception:
                pass  # AI unavailable — heuristic mapping is sufficient

        if mapping:
            n_standardised = int(series.isin(mapping.keys()).sum())
            result[col] = {
                "mapping": mapping,
                "n_standardised": n_standardised,
                "sample_before": list(mapping.keys())[:10],
                "canonical_values": sorted(set(mapping.values()))[:10],
                "method": method,
            }

    return result


def apply_ai_standardisations(df, standardisations: dict):
    """
    Apply the mapping from ai_standardise_inconsistencies() to the DataFrame.
    Returns (modified_df, list_of_action_strings_for_cleaning_summary).
    """
    actions = []
    df = df.copy()
    for col, info in standardisations.items():
        mapping = info.get("mapping", {})
        if mapping and col in df.columns:
            df[col] = df[col].replace(mapping)
            canonical_preview = ", ".join(sorted(set(mapping.values()))[:3])
            actions.append(
                f"AI standardised '{col}': {info['n_standardised']} value(s) "
                f"mapped to canonical forms [{canonical_preview}] "
                f"(method: {info.get('method', 'heuristic')})"
            )
    return df, actions


# ══════════════════════════════════════════════════════════════════════════════
# SUSPICIOUS DATA FLAGGING AGENT
# Detects data quality issues typical in survey research.
# ══════════════════════════════════════════════════════════════════════════════

def flag_suspicious_entries(df, likert_cols=None, likert_max: int = 5) -> dict:
    """
    Detect suspicious survey response patterns in the DataFrame:

    1. Straight-liners  — respondents who gave the SAME answer to all Likert items.
       These responses are likely not genuine (e.g. always clicking 3).

    2. All-extreme      — respondents who selected ALL 1s or ALL max values.
       May indicate disengagement or response bias.

    3. Exact duplicates — identical rows (possible multiple submissions).

    4. Impossible values — values outside plausible bounds for known variable types
       (e.g. Age = 243, GPA = 7.5, Likert value = 9 on a 5-point scale).

    Args:
        df:          Cleaned DataFrame.
        likert_cols: List of Likert column names. If None, auto-detected.
        likert_max:  Maximum valid Likert value (default 5).

    Returns:
        {
          "straight_liners":   {"row_indices": [...], "count": N},
          "all_extreme":       {"row_indices": [...], "count": N},
          "duplicate_rows":    {"row_indices": [...], "count": N},
          "impossible_values": [{"column":..., "row_index":..., "value":..., "reason":...}],
          "total_flagged_rows": N,
          "flagged_row_indices": [...],
          "summary": "12 suspicious rows detected ..."
        }
    """
    result = {
        "straight_liners": {"row_indices": [], "count": 0},
        "all_extreme":     {"row_indices": [], "count": 0},
        "duplicate_rows":  {"row_indices": [], "count": 0},
        "impossible_values": [],
        "total_flagged_rows": 0,
        "flagged_row_indices": [],
        "summary": "",
    }
    flagged_set = set()

    # ── Auto-detect Likert columns ─────────────────────────────────────────
    if likert_cols is None:
        num_cols = df.select_dtypes(include="number").columns.tolist()
        likert_cols = [
            c for c in num_cols
            if 3 <= int(df[c].nunique(dropna=True)) <= 7
            and float(df[c].min(skipna=True)) >= 1
            and float(df[c].max(skipna=True)) <= 10
        ]

    if likert_cols:
        likert_df = df[likert_cols].dropna(how="all")
        row_min = likert_df.min(axis=1)
        row_max = likert_df.max(axis=1)

        # Straight-liners: same value across ALL Likert items in a row
        straight_mask = (row_min == row_max) & likert_df.notna().all(axis=1)
        straight_idxs = likert_df.index[straight_mask].tolist()
        result["straight_liners"] = {"row_indices": straight_idxs, "count": len(straight_idxs)}
        flagged_set.update(straight_idxs)

        # All-extreme: all responses are minimum (1) or maximum
        all_min_mask = (row_max == 1) & likert_df.notna().all(axis=1)
        all_max_mask = (row_min == likert_max) & likert_df.notna().all(axis=1)
        extreme_idxs = likert_df.index[all_min_mask | all_max_mask].tolist()
        result["all_extreme"] = {"row_indices": extreme_idxs, "count": len(extreme_idxs)}
        flagged_set.update(extreme_idxs)

    # ── Exact duplicate rows ───────────────────────────────────────────────
    dup_mask = df.duplicated(keep="first")
    dup_idxs = df.index[dup_mask].tolist()
    result["duplicate_rows"] = {"row_indices": dup_idxs, "count": len(dup_idxs)}
    flagged_set.update(dup_idxs)

    # ── Impossible numeric values ──────────────────────────────────────────
    impossible = []
    _BOUNDS = {
        "age":    (0,   120),
        "year":   (1900, 2100),
        "salary": (0, 10_000_000),
        "income": (0, 10_000_000),
        "score":  (0, 100),
        "grade":  (0, 100),
        "gpa":    (0,   5),
        "cgpa":   (0,   5),
        "weight": (1,   500),
        "height": (50,  300),
    }
    for col in df.select_dtypes(include="number").columns.tolist():
        col_lower = col.strip().lower()
        for key, (lo, hi) in _BOUNDS.items():
            if key in col_lower:
                bad_mask = (df[col] < lo) | (df[col] > hi)
                for idx in df.index[bad_mask & df[col].notna()].tolist():
                    impossible.append({
                        "column": col, "row_index": int(idx),
                        "value": float(df.at[idx, col]),
                        "reason": f"Value {df.at[idx, col]:.4g} is outside the plausible range [{lo}, {hi}] for '{col}'"
                    })
                    flagged_set.add(idx)
                break

        # Likert scale max violation
        if col in (likert_cols or []):
            for idx in df.index[(df[col] > likert_max) & df[col].notna()].tolist():
                impossible.append({
                    "column": col, "row_index": int(idx),
                    "value": float(df.at[idx, col]),
                    "reason": f"Likert response {df.at[idx, col]:.4g} exceeds the declared maximum of {likert_max}"
                })
                flagged_set.add(idx)

    result["impossible_values"] = impossible
    result["total_flagged_rows"] = len(flagged_set)
    result["flagged_row_indices"] = sorted(flagged_set)
    result["summary"] = (
        f"{len(flagged_set)} suspicious row(s) detected: "
        f"{result['straight_liners']['count']} straight-liner(s), "
        f"{result['all_extreme']['count']} all-extreme responder(s), "
        f"{result['duplicate_rows']['count']} exact duplicate(s), "
        f"{len(impossible)} impossible value(s)."
        + (f" First flagged rows: {sorted(flagged_set)[:5]}" if flagged_set else "")
    )
    return result
