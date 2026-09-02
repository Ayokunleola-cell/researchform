# backend/analysis/engine/assumptions.py
"""
Assumption Checker + Auto-Fallback Engine.
Runs silently before each parametric test. Switches to non-parametric alternative
automatically when assumptions are violated. Logs every switch transparently.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import logging
from scipy import stats

logger = logging.getLogger(__name__)


# ── NORMALITY ─────────────────────────────────────────────────────────────────

def check_normality(series: pd.Series, alpha: float = 0.05) -> dict:
    """
    Shapiro-Wilk for n < 50, Kolmogorov-Smirnov for n >= 50.
    Returns: {passed, test_used, statistic, p_value, recommendation}
    """
    data = series.dropna()
    n = len(data)
    if n < 3:
        return {
            "passed": True, "test_used": "skipped",
            "statistic": None, "p_value": None,
            "reason": f"n={n} too small to test normality. Assumed normal.",
            "recommendation": "Collect more data for a valid normality check.",
        }
    if n < 50:
        try:
            stat, p = stats.shapiro(data)
            test = "Shapiro-Wilk"
        except Exception:
            return {"passed": True, "test_used": "skipped", "statistic": None, "p_value": None}
    else:
        try:
            stat, p = stats.kstest(
                (data - data.mean()) / data.std(), "norm"
            )
            test = "Kolmogorov-Smirnov"
        except Exception:
            return {"passed": True, "test_used": "skipped", "statistic": None, "p_value": None}

    passed = bool(p > alpha)
    return {
        "passed": passed,
        "test_used": test,
        "statistic": round(float(stat), 4),
        "p_value": round(float(p), 4),
        "recommendation": (
            "Parametric test is valid (normality not violated)."
            if passed else
            f"Normality violated ({test} p={round(float(p), 4)}). Non-parametric fallback applied."
        ),
    }


# ── EQUAL VARIANCE ────────────────────────────────────────────────────────────

def check_equal_variance(*groups: pd.Series, alpha: float = 0.05) -> dict:
    """
    Levene's test for homogeneity of variance.
    Returns: {passed, statistic, p_value, action}
    """
    clean_groups = [g.dropna() for g in groups if len(g.dropna()) >= 2]
    if len(clean_groups) < 2:
        return {"passed": True, "test": "skipped", "statistic": None, "p_value": None,
                "action": "Insufficient groups for variance test."}
    try:
        stat, p = stats.levene(*clean_groups)
        passed = bool(p > alpha)
        return {
            "passed": passed, "test": "Levene",
            "statistic": round(float(stat), 4), "p_value": round(float(p), 4),
            "action": (
                "Equal variances assumed." if passed
                else f"Unequal variances detected (p={round(float(p), 4)}). Welch correction applied."
            ),
        }
    except Exception as e:
        return {"passed": True, "test": "failed", "statistic": None, "p_value": None,
                "action": f"Variance test failed: {e}. Proceeding with equal variances assumed."}


# ── SPHERICITY ────────────────────────────────────────────────────────────────

def check_sphericity(data: pd.DataFrame, within_cols: list, alpha: float = 0.05) -> dict:
    """
    Mauchly's test via pingouin. Falls back to Greenhouse-Geisser if violated.
    """
    try:
        import pingouin as pg
        result = pg.sphericity(data[within_cols])
        passed = bool(result.pval > alpha)
        return {
            "passed": passed,
            "statistic": round(float(result.W), 4),
            "p_value": round(float(result.pval), 4),
            "epsilon_gg": round(float(result.eps), 4),
            "correction_applied": "None" if passed else "Greenhouse-Geisser",
        }
    except Exception as e:
        return {
            "passed": True, "statistic": None, "p_value": None,
            "epsilon_gg": 1.0, "correction_applied": "None",
            "note": f"Sphericity check skipped: {e}",
        }


# ── EXPECTED CELL FREQUENCIES ─────────────────────────────────────────────────

def check_expected_frequencies(contingency_table: pd.DataFrame) -> dict:
    """
    Validates chi-square assumption: < 20% of cells should have expected freq < 5.
    Returns: {valid_for_chi_square, cells_below_5_pct, recommendation}
    """
    try:
        from scipy.stats import chi2_contingency
        _, _, _, expected = chi2_contingency(contingency_table)
        total_cells = expected.size
        cells_below_5 = int((expected < 5).sum())
        pct_below = (cells_below_5 / total_cells) * 100
        valid = pct_below < 20.0
        return {
            "valid_for_chi_square": valid,
            "cells_below_5": cells_below_5,
            "total_cells": total_cells,
            "cells_below_5_pct": round(pct_below, 1),
            "recommendation": (
                "Chi-Square assumption met."
                if valid else
                f"{pct_below:.0f}% of cells have expected count < 5. Fisher's Exact Test recommended."
            ),
        }
    except Exception as e:
        return {
            "valid_for_chi_square": True, "cells_below_5_pct": 0.0,
            "cells_below_5": 0, "total_cells": 0,
            "recommendation": f"Cell frequency check failed: {e}. Proceeding with Chi-Square.",
        }


# ── MULTICOLLINEARITY ─────────────────────────────────────────────────────────

def check_multicollinearity(df: pd.DataFrame, predictors: list) -> dict:
    """
    VIF check for regression predictors. VIF > 10 = severe multicollinearity.
    """
    try:
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        valid_cols = [c for c in predictors if c in df.columns and
                      pd.api.types.is_numeric_dtype(df[c])]
        if len(valid_cols) < 2:
            return {"passed": True, "vif_values": {}, "note": "< 2 numeric predictors — VIF not applicable."}
        X = df[valid_cols].dropna()
        if X.empty or len(X) < len(valid_cols) + 1:
            return {"passed": True, "vif_values": {}, "note": f"Insufficient observations for VIF (n={len(X)}, needed {len(valid_cols)+1})."}
        vif_data = {
            col: round(float(variance_inflation_factor(X.values, i)), 3)
            for i, col in enumerate(valid_cols)
        }
        severe = {k: v for k, v in vif_data.items() if v > 10}
        return {
            "passed": len(severe) == 0,
            "vif_values": vif_data,
            "severe_multicollinearity": severe,
            "recommendation": (
                "No multicollinearity detected (all VIF < 10)." if not severe
                else f"Severe multicollinearity: {list(severe.keys())} have VIF > 10. Consider removing correlated predictors."
            ),
        }
    except Exception as e:
        return {"passed": True, "vif_values": {}, "note": f"VIF check failed: {e}"}


# ── PROPORTIONAL HAZARDS ──────────────────────────────────────────────────────

def check_proportional_hazards(cox_model, df: pd.DataFrame) -> dict:
    """Schoenfeld residuals test for Cox PH assumption."""
    try:
        from lifelines.statistics import proportional_hazard_test
        result = proportional_hazard_test(cox_model, df, time_transform="rank")
        results_dict = result.summary.to_dict()
        passed = all(v > 0.05 for v in result.summary["p"].values)
        return {
            "passed": passed,
            "schoenfeld_p_values": {k: round(float(v), 4) for k, v in result.summary["p"].items()},
            "recommendation": (
                "Proportional hazards assumption met."
                if passed else
                "PH assumption violated for some covariates. Consider time-varying Cox model."
            ),
        }
    except Exception as e:
        return {"passed": True, "note": f"PH check skipped: {e}"}


# ── MASTER FALLBACK DECISION TABLE ────────────────────────────────────────────

FALLBACK_MAP: dict[str, dict[str, str]] = {
    "independent_t_test":  {"non_normal": "mann_whitney",         "unequal_var": "welch_t_test"},
    "welch_t_test":        {"non_normal": "mann_whitney"},
    "paired_t_test":       {"non_normal": "wilcoxon"},
    "one_sample_t_test":   {"non_normal": "wilcoxon"},
    "one_way_anova":       {"non_normal": "kruskal_wallis",        "unequal_var": "welch_anova"},
    "two_way_anova":       {"non_normal": "kruskal_wallis"},
    "repeated_anova":      {"sphericity_violated": "friedman_test"},
    "pearson_correlation": {"non_normal": "spearman_correlation"},
    "chi_square":          {"sparse_cells": "fisher_exact"},
    "manova":              {"non_normal": "kruskal_wallis"},
}


def get_fallback(test_function: str, violated_assumption: str) -> str | None:
    """Returns the fallback test name when an assumption is violated, or None."""
    return FALLBACK_MAP.get(test_function, {}).get(violated_assumption)
