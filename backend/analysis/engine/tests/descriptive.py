# backend/analysis/engine/tests/descriptive.py
"""Descriptive statistics — all pre-built, deterministic functions."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error, interpret_effect_size


def _numeric_cols(df: pd.DataFrame, variables: list) -> list:
    return [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]


def _all_numeric(df: pd.DataFrame) -> list:
    return list(df.select_dtypes(include=[np.number]).columns)


def run_descriptive_stats(df, variables, brief, alpha=0.05):
    try:
        cols = _numeric_cols(df, variables) or _all_numeric(df)
        cat_cols = [c for c in (variables or df.columns) if c in df.columns and not pd.api.types.is_numeric_dtype(df[c])]
        per_col = {}
        for col in cols:
            s = df[col].dropna()
            if len(s) == 0:
                continue
            mode_res = stats.mode(s, keepdims=True)
            per_col[col] = {
                "n": int(s.count()), "missing": int(df[col].isna().sum()),
                "mean": round(float(s.mean()), 4), "median": round(float(s.median()), 4),
                "mode": round(float(mode_res.mode[0]), 4) if len(mode_res.mode) else None,
                "std": round(float(s.std()), 4), "variance": round(float(s.var()), 4),
                "min": round(float(s.min()), 4), "max": round(float(s.max()), 4),
                "range": round(float(s.max() - s.min()), 4),
                "se_mean": round(float(s.sem()), 4),
                "q1": round(float(s.quantile(0.25)), 4), "q3": round(float(s.quantile(0.75)), 4),
                "iqr": round(float(s.quantile(0.75) - s.quantile(0.25)), 4),
                "cv": round(float(s.std() / s.mean() * 100), 2) if s.mean() != 0 else None,
                "skewness": round(float(s.skew()), 4), "kurtosis": round(float(s.kurtosis()), 4),
            }
        for col in cat_cols:
            s = df[col].dropna()
            vc = s.value_counts()
            per_col[col] = {"n": int(s.count()), "missing": int(df[col].isna().sum()),
                            "value_counts": vc.to_dict(), "n_unique": int(s.nunique())}
        return build_result("Descriptive Statistics", "descriptive_stats", "N", len(df), n=len(df),
                            additional_stats={"columns": per_col})
    except Exception as e:
        return build_error("Descriptive Statistics", "descriptive_stats", str(e), "Check variable types.")


def run_frequency_analysis(df, variables, brief, alpha=0.05):
    import re as _re
    _UUID_SLUG = _re.compile(
        r'^[0-9a-f]{8}[-_][0-9a-f]{4}[-_][0-9a-f]{4}[-_][0-9a-f]{4}[-_][0-9a-f]{12}$',
        _re.IGNORECASE
    )

    try:
        n_rows = len(df)

        def _is_high_cardinality(col: str) -> bool:
            """Return True if column looks like an ID or free-text — not suitable for frequency table."""
            n_unique = df[col].nunique()
            return n_unique > min(50, n_rows * 0.5)

        def _is_phantom(col: str) -> bool:
            """Skip UUID-named columns and columns whose values are all empty."""
            if _UUID_SLUG.match(col):
                return True
            s = df[col].dropna().astype(str).str.strip()
            unique_vals = s.unique()
            # All values are empty string
            if len(unique_vals) == 0 or (len(unique_vals) == 1 and unique_vals[0] == ''):
                return True
            # Only 1 unique non-empty value — no distribution to show
            if len(unique_vals) == 1:
                return True
            return False

        # Use researcher-specified variables first; fall back to all non-numeric columns
        candidate_cols = [c for c in variables if c in df.columns] \
            or list(df.select_dtypes(exclude=[np.number]).columns)

        # Filter out high-cardinality and phantom columns
        cols = [c for c in candidate_cols if not _is_high_cardinality(c) and not _is_phantom(c)]

        if not cols:
            return build_error("Frequency Analysis", "frequency_analysis",
                               "No suitable categorical columns found (all columns have too many unique values).",
                               "Check that nominal/categorical variables are included.")

        freq = {}
        for col in cols:
            s = df[col].dropna()
            vc = s.value_counts()
            pct = (vc / len(s) * 100).round(2)
            cum_count = vc.cumsum()
            cum_pct = pct.cumsum().round(2)
            freq[col] = {
                "counts": vc.to_dict(), "percent": pct.to_dict(),
                "cumulative_count": cum_count.to_dict(), "cumulative_pct": cum_pct.to_dict(),
                "n_valid": int(s.count()), "n_missing": int(df[col].isna().sum()),
            }
        return build_result("Frequency Analysis", "frequency_analysis", "N", n_rows, n=n_rows,
                            additional_stats={"frequencies": freq})
    except Exception as e:
        return build_error("Frequency Analysis", "frequency_analysis", str(e), "Check column names.")




def run_mean_median_mode(df, variables, brief, alpha=0.05):
    try:
        cols = _numeric_cols(df, variables) or _all_numeric(df)
        summary = {}
        for col in cols:
            s = df[col].dropna()
            mode_r = stats.mode(s, keepdims=True)
            summary[col] = {
                "mean": round(float(s.mean()), 4), "median": round(float(s.median()), 4),
                "mode": round(float(mode_r.mode[0]), 4) if len(mode_r.mode) else None,
                "mode_count": int(mode_r.count[0]) if len(mode_r.count) else None,
                "n": int(s.count()),
            }
        return build_result("Mean, Median & Mode", "mean_median_mode", "N", len(df), n=len(df),
                            additional_stats={"columns": summary})
    except Exception as e:
        return build_error("Mean, Median & Mode", "mean_median_mode", str(e), "Ensure numeric columns exist.")


def run_dispersion_extended(df, variables, brief, alpha=0.05):
    try:
        cols = _numeric_cols(df, variables) or _all_numeric(df)
        summary = {}
        for col in cols:
            s = df[col].dropna()
            if len(s) < 2:
                continue
            mad = float(np.median(np.abs(s - np.median(s))))
            summary[col] = {
                "std": round(float(s.std()), 4), "variance": round(float(s.var()), 4),
                "range": round(float(s.max() - s.min()), 4),
                "iqr": round(float(s.quantile(0.75) - s.quantile(0.25)), 4),
                "mad": round(mad, 4),
                "cv": round(float(s.std() / s.mean() * 100), 2) if s.mean() != 0 else None,
                "se_mean": round(float(s.sem()), 4),
                "n": int(s.count()),
            }
        return build_result("Extended Dispersion", "dispersion_extended", "N", len(df), n=len(df),
                            additional_stats={"columns": summary})
    except Exception as e:
        return build_error("Extended Dispersion", "dispersion_extended", str(e), "Check numeric columns.")


def run_percentiles_extended(df, variables, brief, alpha=0.05):
    try:
        cols = _numeric_cols(df, variables) or _all_numeric(df)
        summary = {}
        pct_points = [5, 10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95]
        decile_points = [10, 20, 30, 40, 50, 60, 70, 80, 90]
        for col in cols:
            s = df[col].dropna()
            if len(s) < 5:
                continue
            summary[col] = {
                "percentiles": {str(p): round(float(s.quantile(p / 100)), 4) for p in pct_points},
                "deciles": {f"D{i}": round(float(s.quantile(i / 10)), 4) for i in range(1, 10)},
                "n": int(s.count()),
            }
        return build_result("Percentiles & Deciles", "percentiles_extended", "N", len(df), n=len(df),
                            additional_stats={"columns": summary})
    except Exception as e:
        return build_error("Percentiles & Deciles", "percentiles_extended", str(e), "Need >= 5 observations.")


def run_z_scores(df, variables, brief, alpha=0.05):
    try:
        cols = _numeric_cols(df, variables) or _all_numeric(df)
        summary = {}
        for col in cols:
            s = df[col].dropna()
            if len(s) < 3 or s.std() == 0:
                continue
            z = (s - s.mean()) / s.std()
            summary[col] = {
                "n_extreme": int((z.abs() > 3).sum()),
                "area_within_1sd": round(float((z.abs() <= 1).mean() * 100), 2),
                "area_within_2sd": round(float((z.abs() <= 2).mean() * 100), 2),
                "area_within_3sd": round(float((z.abs() <= 3).mean() * 100), 2),
                "max_z": round(float(z.max()), 4), "min_z": round(float(z.min()), 4),
                "n": int(s.count()),
            }
        return build_result("Z-Scores", "z_scores", "N", len(df), n=len(df),
                            additional_stats={"columns": summary})
    except Exception as e:
        return build_error("Z-Scores", "z_scores", str(e), "Ensure numeric columns with variation.")


def run_skewness_analysis(df, variables, brief, alpha=0.05):
    try:
        cols = _numeric_cols(df, variables) or _all_numeric(df)
        summary = {}
        for col in cols:
            s = df[col].dropna()
            n = len(s)
            if n < 3:
                continue
            skew = float(s.skew())
            se_skew = float(np.sqrt(6 * n * (n - 1) / ((n - 2) * (n + 1) * (n + 3))))
            z_skew = skew / se_skew if se_skew > 0 else 0
            if abs(skew) < 0.5: interp = "approximately symmetric"
            elif abs(skew) < 1.0: interp = "moderately skewed"
            else: interp = "highly skewed"
            summary[col] = {
                "skewness": round(skew, 4), "se_skewness": round(se_skew, 4),
                "z_skewness": round(z_skew, 4), "interpretation": interp, "n": n,
            }
        return build_result("Skewness Analysis", "skewness_analysis", "N", len(df), n=len(df),
                            additional_stats={"columns": summary})
    except Exception as e:
        return build_error("Skewness Analysis", "skewness_analysis", str(e), "Need >= 3 observations.")


def run_kurtosis_analysis(df, variables, brief, alpha=0.05):
    try:
        cols = _numeric_cols(df, variables) or _all_numeric(df)
        summary = {}
        for col in cols:
            s = df[col].dropna()
            n = len(s)
            if n < 4:
                continue
            kurt = float(s.kurtosis())  # excess kurtosis
            se_kurt = float(2 * np.sqrt(6 * n * (n - 1) / ((n - 2) * (n + 1) * (n + 3))) *
                            np.sqrt((n * n - 1) / ((n - 3) * (n + 5))))
            z_kurt = kurt / se_kurt if se_kurt > 0 else 0
            if abs(kurt) < 0.5: interp = "mesokurtic (normal)"
            elif kurt > 0: interp = "leptokurtic (heavy tails)"
            else: interp = "platykurtic (light tails)"
            summary[col] = {
                "kurtosis": round(kurt, 4), "se_kurtosis": round(se_kurt, 4),
                "z_kurtosis": round(z_kurt, 4), "interpretation": interp, "n": n,
            }
        return build_result("Kurtosis Analysis", "kurtosis_analysis", "N", len(df), n=len(df),
                            additional_stats={"columns": summary})
    except Exception as e:
        return build_error("Kurtosis Analysis", "kurtosis_analysis", str(e), "Need >= 4 observations.")


def run_variable_transformation(df, variables, brief, alpha=0.05):
    try:
        cols = _numeric_cols(df, variables) or _all_numeric(df)
        summary = {}
        for col in cols:
            s = df[col].dropna()
            if len(s) < 3:
                continue
            col_res = {"original_skewness": round(float(s.skew()), 4)}
            # Log transform (only if all positive)
            if (s > 0).all():
                log_s = np.log(s)
                w, p = stats.shapiro(log_s) if len(log_s) < 50 else stats.kstest((log_s - log_s.mean()) / log_s.std(), 'norm')
                col_res["log_transform"] = {"p": round(float(p), 4), "normalised": bool(p > alpha), "skewness": round(float(log_s.skew()), 4)}
            # Sqrt transform (only if all non-negative)
            if (s >= 0).all():
                sqrt_s = np.sqrt(s)
                w2, p2 = stats.shapiro(sqrt_s) if len(sqrt_s) < 50 else stats.kstest((sqrt_s - sqrt_s.mean()) / sqrt_s.std(), 'norm')
                col_res["sqrt_transform"] = {"p": round(float(p2), 4), "normalised": bool(p2 > alpha), "skewness": round(float(sqrt_s.skew()), 4)}
            # Box-Cox (only positive)
            if (s > 0).all():
                try:
                    bc_s, lam = stats.boxcox(s)
                    bc_series = pd.Series(bc_s)
                    w3, p3 = stats.shapiro(bc_series) if len(bc_series) < 50 else stats.kstest((bc_series - bc_series.mean()) / bc_series.std(), 'norm')
                    col_res["boxcox_transform"] = {"lambda": round(float(lam), 4), "p": round(float(p3), 4), "normalised": bool(p3 > alpha)}
                except Exception:
                    pass
            # Recommend
            best = "none"
            best_p = 0.0
            for t_name in ["log_transform", "sqrt_transform", "boxcox_transform"]:
                if t_name in col_res and col_res[t_name].get("p", 0) > best_p:
                    best_p = col_res[t_name]["p"]
                    best = t_name.replace("_transform", "")
            col_res["recommended"] = best
            summary[col] = col_res
        return build_result("Variable Transformation", "variable_transformation", "N", len(df), n=len(df),
                            additional_stats={"columns": summary})
    except Exception as e:
        return build_error("Variable Transformation", "variable_transformation", str(e), "Check for positive values.")
