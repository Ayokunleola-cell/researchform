"""
analysis/engine/tests/missing_data.py

Missing Data Analysis & MICE Imputation.
- Diagnoses missingness patterns (MCAR/MAR/MNAR)
- Little's MCAR test
- Multiple Imputation by Chained Equations (MICE) via sklearn IterativeImputer
- Returns structured report + imputed DataFrame
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats as _stats
from analysis.engine.schema import build_result, build_error


def _pct(n, total):
    return round(n / total * 100, 2) if total else 0.0


# ─── Missing Pattern Analysis ─────────────────────────────────────────────────

def run_missing_analysis(df, variables=None, brief=None, alpha=0.05, **kw):
    """
    Analyse missingness in the DataFrame.
    Returns per-column counts, overall pattern, and Little's MCAR test.
    """
    try:
        cols = [c for c in (variables or df.columns) if c in df.columns]
        data = df[cols]
        n, p = len(data), len(cols)

        # Per-column missingness
        col_stats = {}
        any_missing = False
        for col in cols:
            miss = int(data[col].isna().sum())
            if miss > 0:
                any_missing = True
            col_stats[col] = {
                "missing_n": miss,
                "missing_pct": _pct(miss, n),
                "complete_n": n - miss,
                "complete_pct": _pct(n - miss, n),
            }

        # Overall stats
        total_cells   = n * p
        total_missing = int(data.isna().sum().sum())
        overall_pct   = _pct(total_missing, total_cells)

        # Severity classification
        if overall_pct == 0:
            severity = "none"
            recommendation = "No missing data detected. Proceed with analysis."
        elif overall_pct < 5:
            severity = "low"
            recommendation = "< 5% missing. Listwise deletion is acceptable. MICE optional."
        elif overall_pct < 15:
            severity = "moderate"
            recommendation = "5-15% missing. MICE imputation recommended for unbiased estimates."
        else:
            severity = "high"
            recommendation = "> 15% missing. MICE strongly recommended. Consider data quality review."

        # Little's MCAR test (approximate via chi-square on mean shifts)
        mcar_result = _little_mcar_test(data, cols)

        # Missing pattern matrix (binary heatmap data for frontend)
        pattern_matrix = data.isna().astype(int).values.tolist()
        pattern_cols   = cols

        mcar_p = mcar_result.get("p_value")
        return build_result(
            test_name="Missing Data Analysis",
            test_function="missing_analysis",
            statistic_label="Missing %",
            statistic_value=round(overall_pct, 4),
            p_value=mcar_p if mcar_p is not None else None,
            n=int(total_cells),
            conclusion=(
                f"{total_missing} missing values detected across {p} variables "
                f"({overall_pct:.1f}% of all cells). Severity: {severity.upper()}. "
                f"{recommendation}"
            ),
            additional_stats={
                "n": n,
                "p_variables": p,
                "total_missing_cells": total_missing,
                "overall_missing_pct": overall_pct,
                "severity": severity,
                "recommendation": recommendation,
                "has_missing": any_missing,
                "column_stats": col_stats,
                "mcar_test": mcar_result,
                "pattern_matrix": pattern_matrix,
                "pattern_columns": pattern_cols,
                "significant": any_missing,
            }
        )
    except Exception as e:
        return {"error": str(e), "test_name": "Missing Data Analysis",
                "test_function": "missing_analysis"}


def _little_mcar_test(data: pd.DataFrame, cols: list) -> dict:
    """
    Approximate Little's MCAR test.
    Tests whether the pattern of missingness is completely random (MCAR).
    Uses chi-square test on missing pattern vs observed means.
    """
    try:
        # Create missing indicator matrix
        miss_indicator = data[cols].isna().astype(int)
        n = len(data)

        # For each unique missing pattern, compare means of observed vars
        patterns = miss_indicator.apply(lambda r: tuple(r), axis=1)
        unique_patterns = patterns.unique()

        if len(unique_patterns) <= 1:
            return {
                "test": "Little's MCAR",
                "chi2": 0.0, "df": 0, "p_value": 1.0,
                "result": "MCAR (no missing pattern variation)",
                "interpretation": "Data appears to be Missing Completely at Random (MCAR)."
            }

        # Compute grand means for complete cases
        complete = data[cols].dropna()
        if len(complete) < 2:
            return {"test": "Little's MCAR", "error": "Insufficient complete cases for MCAR test."}

        grand_means = complete.mean()
        col_vars = {c: max(float(np.var(data[c].dropna(), ddof=1)), 1e-8) for c in cols}

        chi2_total = 0.0
        df_total = 0
        for pat in unique_patterns:
            mask = patterns == pat
            group = data.loc[mask, cols]
            observed_cols = [c for c, m in zip(cols, pat) if m == 0]
            if not observed_cols or len(group) < 2:
                continue
            g_means = group[observed_cols].mean()
            g_n = len(group)
            for c in observed_cols:
                if grand_means[c] != 0:
                    diff = g_means[c] - grand_means[c]
                    var = col_vars[c]
                    if var <= 0 or np.isnan(var):
                        continue
                    chi2_total += g_n * (diff ** 2) / abs(var)
                    df_total += 1

        df_total = max(df_total - len(cols), 1)
        p_value  = float(_stats.chi2.sf(chi2_total, df_total))
        mcar     = p_value >= 0.05

        return {
            "test": "Little's MCAR (approximate)",
            "chi2": round(chi2_total, 4),
            "df": df_total,
            "p_value": round(p_value, 4),
            "result": "MCAR" if mcar else "MAR or MNAR",
            "interpretation": (
                "Data appears to be Missing Completely at Random (MCAR) — "
                "listwise deletion is valid." if mcar else
                "Data is NOT MCAR (p < .05) — missing values are related to observed data. "
                "MICE imputation is strongly recommended."
            ),
        }
    except Exception as e:
        return {"test": "Little's MCAR", "error": str(e)}


# ─── MICE Imputation ──────────────────────────────────────────────────────────

def run_mice_imputation(df, variables=None, brief=None,
                         n_imputations: int = 5, max_iter: int = 10, **kw):
    """
    Multiple Imputation by Chained Equations (MICE).
    Uses sklearn IterativeImputer. Returns pooled DataFrame + report.
    """
    try:
        from sklearn.experimental import enable_iterative_imputer  # noqa
        from sklearn.impute import IterativeImputer
        from sklearn.preprocessing import LabelEncoder

        cols = [c for c in (variables or df.columns) if c in df.columns]
        data = df[cols].copy()
        n    = len(data)

        # Separate numeric and categorical
        numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(data[c])]
        cat_cols     = [c for c in cols if not pd.api.types.is_numeric_dtype(data[c])]

        # Encode categoricals temporarily
        encoders = {}
        for c in cat_cols:
            le = LabelEncoder()
            non_null = data[c].dropna()
            le.fit(non_null.astype(str))
            data[c] = data[c].apply(
                lambda x: le.transform([str(x)])[0] if pd.notna(x) else np.nan
            )
            encoders[c] = le

        if not numeric_cols and not cat_cols:
            return {"error": "No suitable columns for imputation.", "test_function": "mice"}

        work_cols = numeric_cols + cat_cols
        X = data[work_cols].values.astype(float)

        # Count missingness before
        miss_before = {c: int(data[c].isna().sum()) for c in work_cols}

        # Run MICE n_imputations times and average
        imputed_arrays = []
        for seed in range(n_imputations):
            imp = IterativeImputer(
                max_iter=max_iter,
                random_state=seed,
                initial_strategy="mean",
                imputation_order="ascending"
            )
            imputed_arrays.append(imp.fit_transform(X))

        # Pool: average across imputations (Rubin's rules simplified)
        pooled = np.mean(imputed_arrays, axis=0)

        # Round categorical columns back to integer
        cat_indices = [work_cols.index(c) for c in cat_cols if c in work_cols]
        for idx in cat_indices:
            pooled[:, idx] = np.round(pooled[:, idx]).astype(int)

        # Build result DataFrame
        result_df = df.copy()
        for i, c in enumerate(work_cols):
            result_df[c] = pooled[:, i]
            # Decode categoricals
            if c in encoders:
                le = encoders[c]
                vals = np.clip(pooled[:, i].round().astype(int), 0, len(le.classes_) - 1)
                result_df[c] = le.inverse_transform(vals)

        # Report
        imputed_report = []
        for c in work_cols:
            before = miss_before.get(c, 0)
            if before > 0:
                imputed_report.append({
                    "column": c,
                    "imputed_n": before,
                    "imputed_pct": _pct(before, n),
                    "method": "MICE (chained equations)",
                    "n_imputations": n_imputations,
                })

        n_imputed = sum(r["imputed_n"] for r in imputed_report)
        return build_result(
            test_name="MICE Imputation",
            test_function="mice_imputation",
            statistic_label="Imputed Cells",
            statistic_value=int(n_imputed) if 'n_imputed' in locals() else 0,
            p_value=None,
            n=int(len(df)),
            conclusion="MICE imputation completed.",
            additional_stats={
                "n_imputations": n_imputations,
                "max_iter": max_iter,
                "n_rows": n,
                "columns_imputed": imputed_report,
                "total_imputed": n_imputed,
                "imputed_df": result_df,   # caller saves this to disk
                "significant": True,
            }
        )
    except Exception as e:
        return {"error": str(e), "test_name": "MICE Imputation", "test_function": "mice"}
