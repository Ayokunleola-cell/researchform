# backend/analysis/engine/validator.py
"""
Pre-Validation Health Check — runs before any statistical test.
Catches data quality problems early so the engine never runs on garbage.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class DataHealthReport:
    def __init__(self):
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.suggestions: list[str] = []
        self.auto_fixes: list[str] = []
        self.passed: bool = True


def run_health_check(df: pd.DataFrame, tests: list, brief: dict) -> DataHealthReport:
    """
    Full pre-flight data validation. Returns a DataHealthReport.
    If report.passed is False, the dispatcher aborts cleanly.
    """
    report = DataHealthReport()

    # ── 1. MISSING DATA AUDIT ─────────────────────────────────────────────────
    for col in df.columns:
        missing_pct = df[col].isna().mean() * 100
        if missing_pct > 50:
            report.errors.append(
                f"Column '{col}' has {missing_pct:.0f}% missing values. "
                "This column cannot be used reliably in any analysis."
            )
            report.suggestions.append(
                f"Remove '{col}' or collect more data before re-uploading."
            )
            report.passed = False
        elif missing_pct > 20:
            report.warnings.append(
                f"Column '{col}' has {missing_pct:.1f}% missing values. "
                "Results may be unreliable. Consider multiple imputation."
            )

    # ── 2. VARIABLE TYPE CONFLICTS (numbers stored as strings) ───────────────
    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna().astype(str).head(30)
        if len(sample) == 0:
            continue
        numeric_hits = sum(
            1 for v in sample
            if v.replace(".", "").replace("-", "").replace(",", "").isdigit()
        )
        if numeric_hits / len(sample) > 0.8:
            try:
                df[col] = pd.to_numeric(df[col].str.replace(",", ""), errors="coerce")
                report.auto_fixes.append(
                    f"Auto-converted column '{col}' from text to numeric "
                    f"({numeric_hits}/{len(sample)} values looked numeric)."
                )
                report.warnings.append(
                    f"Column '{col}' was stored as text but contained numbers. "
                    "Auto-converted — please verify the conversion is correct."
                )
            except Exception:
                report.warnings.append(
                    f"Column '{col}' appears to contain numbers stored as text "
                    "but automatic conversion failed. Please clean this column manually."
                )

    # ── 3. CONSTANT COLUMNS (zero variance — crashes every test) ─────────────
    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].dropna().nunique() <= 1:
            report.warnings.append(
                f"Column '{col}' has no variation (all values are identical or all missing). "
                "Statistical tests require variation — this column will be skipped."
            )

    # ── 4. SAMPLE SIZE WARNINGS PER TEST FAMILY ──────────────────────────────
    n = len(df)
    test_functions = {t.get("test_function", "") for t in tests}

    if n < 5:
        report.errors.append(
            f"Dataset has only {n} rows. A minimum of 5 observations is required "
            "for any meaningful statistical analysis."
        )
        report.passed = False

    if any(f in test_functions for f in ("sem", "cfa", "confirmatory_fa")) and n < 100:
        report.warnings.append(
            f"SEM/CFA typically requires n ≥ 100 for stable estimates. "
            f"Your n = {n}. Interpret results with caution."
        )

    if any(f in test_functions for f in ("factor_analysis", "pca")) and n < 50:
        report.warnings.append(
            f"Factor Analysis / PCA requires n ≥ 50 (ideally 5-10× the number of items). "
            f"Your n = {n}. Results may be unstable."
        )

    if any(f in test_functions for f in ("multiple_regression", "logistic_regression",
                                          "hierarchical_regression")) and n < 30:
        report.warnings.append(
            f"Regression analysis with n = {n} is very underpowered. "
            "A minimum of 10-20 cases per predictor is recommended."
        )

    if any(f in test_functions for f in ("cox_regression", "survival_analysis")) and n < 30:
        report.warnings.append(
            f"Survival analysis with n = {n} may produce unreliable hazard estimates. "
            "A minimum of 30 events is recommended."
        )

    if any(f in test_functions for f in ("linear_mixed_effects", "gee")) and n < 30:
        report.warnings.append(
            f"Mixed-effects models with n = {n} may not converge reliably. "
            "Minimum 30+ observations is recommended."
        )

    # ── 5. EXTREME OUTLIER SCAN (quick IQR sweep) ────────────────────────────
    for col in df.select_dtypes(include=[np.number]).columns:
        clean = df[col].dropna()
        if len(clean) < 4:
            continue
        q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        n_extreme = int(((clean < q1 - 3 * iqr) | (clean > q3 + 3 * iqr)).sum())
        if n_extreme > 0:
            report.warnings.append(
                f"Column '{col}' has {n_extreme} extreme outlier(s) (beyond 3×IQR). "
                "Review the outlier detection results carefully before drawing conclusions."
            )

    # ── 6. DUPLICATE ROWS CHECK ───────────────────────────────────────────────
    n_dupes = df.duplicated().sum()
    if n_dupes > 0:
        pct_dupes = (n_dupes / len(df)) * 100
        report.warnings.append(
            f"Dataset contains {n_dupes} duplicate rows ({pct_dupes:.1f}%). "
            "Duplicates may inflate sample sizes and distort results."
        )

    logger.info(
        f"[HealthCheck] passed={report.passed}, "
        f"errors={len(report.errors)}, warnings={len(report.warnings)}, "
        f"auto_fixes={len(report.auto_fixes)}"
    )
    return report
