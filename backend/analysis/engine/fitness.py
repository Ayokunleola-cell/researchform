# backend/analysis/engine/fitness.py
"""
Test Fitness Validator
======================
Checks whether a chosen statistical test is appropriate for the given dataset.
Works without any AI — pure rule-based validation using data characteristics.

Each validator returns a dict:
  {
    "test_function": str,
    "test_name":     str,
    "fitness":       "good" | "warning" | "mismatch",
    "message":       str,         # human-readable explanation
    "suggestion":    str | None,  # what to do instead
  }
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional


# ─── Fitness levels ──────────────────────────────────────────────────────────
GOOD     = "good"
WARNING  = "warning"
MISMATCH = "mismatch"   # test is clearly inappropriate — must warn user


def _ok(fn, name):
    return {"test_function": fn, "test_name": name, "fitness": GOOD,
            "message": "Test is appropriate for the dataset.", "suggestion": None}


def _warn(fn, name, msg, suggestion=None):
    return {"test_function": fn, "test_name": name, "fitness": WARNING,
            "message": msg, "suggestion": suggestion}


def _mismatch(fn, name, msg, suggestion=None):
    return {"test_function": fn, "test_name": name, "fitness": MISMATCH,
            "message": msg, "suggestion": suggestion}


# ─── Helper utilities ─────────────────────────────────────────────────────────

def _numeric_cols(df: pd.DataFrame, variables: list) -> list:
    return [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]


def _group_counts(df: pd.DataFrame, group_col: str) -> Optional[int]:
    if group_col not in df.columns:
        return None
    return int(df[group_col].dropna().nunique())


def _is_binary(series: pd.Series) -> bool:
    vals = set(series.dropna().unique())
    return vals.issubset({0, 1, 0.0, 1.0, True, False})


def _n(df: pd.DataFrame, variables: list) -> int:
    cols = [c for c in variables if c in df.columns]
    if not cols:
        return len(df)
    return int(df[cols].dropna().shape[0])


# ─── Per-family fitness rules ─────────────────────────────────────────────────

def _check_t_tests(fn, name, df, variables, brief):
    n_obs = _n(df, variables)
    num = _numeric_cols(df, variables)
    group_col = variables[0] if variables else None
    outcome_col = variables[1] if len(variables) > 1 else None

    if fn == "one_sample_t_test":
        if not num:
            return _mismatch(fn, name, "One-sample t-test requires a numeric column.", "Select a continuous variable.")
        if n_obs < 8:
            return _warn(fn, name, f"Small sample (n={n_obs}). Results may be unreliable.", "Consider bootstrapping or sign test.")
        return _ok(fn, name)

    if fn in ("independent_t_test", "welch_t_test", "independent_t_cohend"):
        if not group_col or not outcome_col:
            return _mismatch(fn, name, "Need a grouping column and a numeric outcome column.", "Select 2 variables: group, outcome.")
        n_groups = _group_counts(df, group_col)
        if n_groups is None:
            return _mismatch(fn, name, f"Group column '{group_col}' not found.", "Check variable selection.")
        if n_groups < 2:
            return _mismatch(fn, name, f"Independent t-test requires exactly 2 groups. Found {n_groups}.", "Use a dataset with 2 group levels.")
        if n_groups > 2:
            return _mismatch(fn, name, f"Independent t-test is for 2 groups, but {n_groups} groups found.",
                             "Use One-Way ANOVA or Welch ANOVA for 3+ groups.")
        if outcome_col not in df.columns or not pd.api.types.is_numeric_dtype(df[outcome_col]):
            return _mismatch(fn, name, f"Outcome '{outcome_col}' must be numeric.", "Select a continuous outcome variable.")
        if n_obs < 10:
            return _warn(fn, name, f"Small sample (n={n_obs}). T-test is sensitive to non-normality with small n.", "Verify normality or use Mann-Whitney U.")
        return _ok(fn, name)

    if fn in ("paired_t_test", "paired_t_cohend"):
        if len(num) < 2:
            return _mismatch(fn, name, "Paired t-test requires 2 numeric columns (pre and post).", "Select pre-test and post-test columns.")
        if n_obs < 6:
            return _warn(fn, name, f"Very small paired sample (n={n_obs}).", "Consider Wilcoxon signed-rank test.")
        return _ok(fn, name)

    return _ok(fn, name)


def _check_anova(fn, name, df, variables, brief):
    num = _numeric_cols(df, variables)
    group_col = variables[0] if variables else None
    outcome_col = variables[1] if len(variables) > 1 else None
    n_obs = _n(df, variables)

    if fn in ("one_way_anova", "anova_eta_squared", "anova_descriptives", "welch_anova"):
        if not group_col or not outcome_col:
            return _mismatch(fn, name, "Need a group column and numeric outcome.", "Select 2 variables: group, outcome.")
        n_groups = _group_counts(df, group_col)
        if n_groups is not None and n_groups < 3:
            return _warn(fn, name, f"ANOVA typically needs >= 3 groups, but only {n_groups} found.",
                         "Consider using t-test for 2 groups.")
        if outcome_col and not pd.api.types.is_numeric_dtype(df.get(outcome_col, pd.Series(dtype=float))):
            return _mismatch(fn, name, f"Outcome '{outcome_col}' must be numeric.", "Select a continuous DV.")
        if n_obs < 20:
            return _warn(fn, name, f"Small total sample (n={n_obs}) across groups. Results may be unreliable.", "Collect more data.")
        return _ok(fn, name)

    if fn in ("two_way_anova", "two_way_eta_squared", "two_way_pairwise"):
        if len(variables) < 3:
            return _mismatch(fn, name, "Two-Way ANOVA needs factor1, factor2, and outcome (3 variables).", "Select 3 variables.")
        if n_obs < 30:
            return _warn(fn, name, f"Small sample (n={n_obs}) for Two-Way ANOVA.", "Collect more data for stable interaction estimates.")
        return _ok(fn, name)

    if fn == "repeated_anova":
        if len(num) < 2:
            return _mismatch(fn, name, "Repeated Measures ANOVA needs >= 2 time-point columns.", "Select numeric time-point columns.")
        return _ok(fn, name)

    if fn in ("manova", "manova_followup"):
        dv_cols = [c for c in variables[1:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(dv_cols) < 2:
            return _mismatch(fn, name, "MANOVA needs >= 2 numeric dependent variables.", "Select group + 2+ numeric DVs.")
        if n_obs < 50:
            return _warn(fn, name, f"MANOVA requires larger samples. n={n_obs} may be underpowered.", "Aim for n > 50, ideally n > 100.")
        return _ok(fn, name)

    if fn == "ancova":
        if len(variables) < 3:
            return _mismatch(fn, name, "ANCOVA needs group, outcome, and covariate (3 variables).", "Select 3 variables.")
        return _ok(fn, name)

    return _ok(fn, name)


def _check_nonparametric(fn, name, df, variables, brief):
    num = _numeric_cols(df, variables)
    group_col = variables[0] if variables else None
    n_obs = _n(df, variables)

    if fn in ("mann_whitney", "mann_whitney_r", "mann_whitney_ci"):
        n_groups = _group_counts(df, group_col) if group_col else None
        if n_groups is not None and n_groups != 2:
            return _mismatch(fn, name, f"Mann-Whitney requires exactly 2 groups. Found {n_groups}.",
                             "Use Kruskal-Wallis for 3+ groups.")
        return _ok(fn, name)

    if fn in ("wilcoxon", "wilcoxon_r"):
        if len(num) < 2:
            return _mismatch(fn, name, "Wilcoxon Signed-Rank needs 2 paired columns.", "Select pre and post numeric columns.")
        return _ok(fn, name)

    if fn in ("kruskal_wallis", "kruskal_wallis_eta2"):
        n_groups = _group_counts(df, group_col) if group_col else None
        if n_groups is not None and n_groups < 3:
            return _warn(fn, name, f"Kruskal-Wallis usually needs >= 3 groups. Found {n_groups}.",
                         "Consider Mann-Whitney U for 2 groups.")
        return _ok(fn, name)

    if fn in ("friedman_test", "kendall_w"):
        if len(num) < 3:
            return _mismatch(fn, name, "Friedman test requires >= 3 repeated measurement columns.", "Select 3+ numeric columns.")
        return _ok(fn, name)

    if fn in ("chi_square", "chi_square_extended", "chi_square_goodness_of_fit"):
        # Goodness-of-Fit only needs 1 column; Independence needs 2
        is_gof = (fn == "chi_square_goodness_of_fit" or "goodness" in (test_name or "").lower())
        if not is_gof and len(variables) < 2:
            return _mismatch(fn, name, "Chi-Square (independence) needs 2 categorical columns.",
                             "Select 2 categorical variables, or use chi_square_goodness_of_fit for a single column.")
        elif is_gof and len(variables) < 1:
            return _mismatch(fn, name, "Chi-Square Goodness of Fit needs at least 1 categorical column.",
                             "Select the categorical variable.")
        # Check variables are actually categorical (not continuous)
        cat_cols = [c for c in variables[:2] if c in df.columns]
        for col in cat_cols:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                unique_ratio = df[col].nunique() / max(len(df), 1)
                if unique_ratio > 0.2:
                    return _warn(fn, name, f"Column '{col}' looks continuous (many unique values). Chi-Square is for categorical data.",
                                 "Bin the variable into categories first, or use Pearson correlation.")
        return _ok(fn, name)

    if fn == "fisher_exact":
        if len(variables) < 2:
            return _mismatch(fn, name, "Fisher's Exact Test needs 2 binary/categorical columns.", "Select 2 categorical variables.")
        # Fisher is best for small samples / 2x2 tables
        if n_obs > 200:
            return _warn(fn, name, f"Fisher's Exact Test is designed for small samples. n={n_obs} — Chi-Square may be more efficient.",
                         "Use Chi-Square for large samples.")
        return _ok(fn, name)

    if fn == "mcnemar":
        if len(variables) < 2:
            return _mismatch(fn, name, "McNemar test needs 2 binary paired columns.", "Select 2 binary (0/1) columns.")
        bin_cols = [c for c in variables[:2] if c in df.columns and _is_binary(df[c])]
        if len(bin_cols) < 2:
            return _warn(fn, name, "McNemar test works best with binary (0/1) paired columns.", "Ensure both columns are dichotomous.")
        return _ok(fn, name)

    return _ok(fn, name)


def _check_correlation(fn, name, df, variables, brief):
    num = _numeric_cols(df, variables)
    n_obs = _n(df, variables[:2])

    if fn in ("pearson_correlation", "pearson_ci"):
        if len(num) < 2:
            return _mismatch(fn, name, "Pearson correlation requires 2 numeric columns.", "Select 2 continuous variables.")
        if n_obs < 10:
            return _warn(fn, name, f"Very small sample (n={n_obs}). Pearson r is unstable.", "Use Spearman for small or non-normal data.")
        # Check if data looks ordinal (few unique values)
        for col in variables[:2]:
            if col in df.columns and df[col].nunique() <= 5:
                return _warn(fn, name, f"'{col}' appears ordinal (Likert). Consider Spearman instead of Pearson.",
                             "Use Spearman correlation for ordinal/Likert data.")
        return _ok(fn, name)

    if fn in ("spearman_correlation",):
        if len(variables) < 2:
            return _mismatch(fn, name, "Spearman requires 2 columns.", "Select 2 variables.")
        return _ok(fn, name)

    if fn == "kendall_tau":
        if len(variables) < 2:
            return _mismatch(fn, name, "Kendall's Tau requires 2 columns.", "Select 2 variables.")
        return _ok(fn, name)

    if fn == "point_biserial":
        if len(variables) < 2:
            return _mismatch(fn, name, "Point-biserial requires 1 binary and 1 continuous column.", "Select 2 variables.")
        bin_col = variables[0]
        if bin_col in df.columns and not _is_binary(df[bin_col]):
            return _warn(fn, name, f"'{bin_col}' does not appear binary. Point-biserial needs a 0/1 column.",
                         "Ensure the first variable is binary (0 or 1).")
        return _ok(fn, name)

    if fn == "partial_correlation":
        if len(num) < 3:
            return _mismatch(fn, name, "Partial correlation requires 3 numeric columns (x, y, covariate).", "Select 3 numeric variables.")
        return _ok(fn, name)

    if fn == "canonical_correlation":
        if len(num) < 4:
            return _mismatch(fn, name, "Canonical correlation requires >= 4 numeric columns (2+ per set).", "Select 4+ numeric variables.")
        if n_obs < 50:
            return _warn(fn, name, f"Small sample (n={n_obs}) for canonical correlation.", "Canonical correlation is unstable with small n.")
        return _ok(fn, name)

    return _ok(fn, name)


def _check_regression(fn, name, df, variables, brief):
    num = _numeric_cols(df, variables)
    n_obs = _n(df, variables)
    dv = variables[0] if variables else None

    if fn in ("simple_linear_regression", "linear_regression"):
        if len(num) < 2:
            return _mismatch(fn, name, "Linear regression requires a numeric DV and at least 1 numeric IV.", "Select 2+ numeric variables.")
        return _ok(fn, name)

    if fn == "multiple_regression":
        if len(num) < 3:
            return _warn(fn, name, "Multiple regression works best with >= 3 numeric columns (DV + 2+ IVs).", "Add more predictors.")
        if n_obs < 30:
            return _warn(fn, name, f"Small sample (n={n_obs}) for multiple regression. Recommend n >= 10 per predictor.",
                         "Reduce the number of predictors or collect more data.")
        return _ok(fn, name)

    if fn == "logistic_regression":
        if not dv or dv not in df.columns:
            return _mismatch(fn, name, "Need a binary outcome variable.", "Select a 0/1 column as DV.")
        if not _is_binary(df[dv]):
            return _mismatch(fn, name, f"'{dv}' is not binary. Logistic regression requires a 0/1 outcome.",
                             "Use Ordinal or Multinomial regression for non-binary outcomes.")
        if n_obs < 30:
            return _warn(fn, name, f"Small sample (n={n_obs}) for logistic regression. Results may be unstable.", "Collect more data.")
        return _ok(fn, name)

    if fn in ("poisson_regression", "negative_binomial"):
        if not dv or dv not in df.columns:
            return _mismatch(fn, name, "Need a count outcome variable.", "Select a non-negative integer count column.")
        dv_series = df[dv].dropna()
        if dv_series.min() < 0:
            return _mismatch(fn, name, f"'{dv}' contains negative values. Poisson/NegBin requires non-negative counts.",
                             "Select a count variable or use linear regression.")
        if _is_binary(dv_series):
            return _warn(fn, name, f"'{dv}' looks binary (0/1). Poisson regression is for count data (0,1,2,3...).",
                         "Use logistic regression for binary outcomes.")
        return _ok(fn, name)

    if fn in ("ordinal_regression",):
        if not dv or dv not in df.columns:
            return _mismatch(fn, name, "Need an ordinal outcome variable.", "Select an ordinal (Likert) DV.")
        n_cats = df[dv].dropna().nunique() if dv in df.columns else 0
        if n_cats < 3:
            return _warn(fn, name, f"Ordinal regression is best for 3+ ordered categories. Found {n_cats}.",
                         "Use logistic regression for binary outcomes.")
        return _ok(fn, name)

    if fn in ("mediation_analysis",):
        if len(num) < 3:
            return _mismatch(fn, name, "Mediation analysis requires IV, Mediator, and DV (3 numeric columns).", "Select 3 numeric variables.")
        return _ok(fn, name)

    if fn in ("moderation_analysis",):
        if len(num) < 3:
            return _mismatch(fn, name, "Moderation requires IV, Moderator, and DV (3 numeric columns).", "Select 3 numeric variables.")
        return _ok(fn, name)

    return _ok(fn, name)


def _check_reliability(fn, name, df, variables, brief):
    num = _numeric_cols(df, variables)
    n_obs = _n(df, variables)

    if fn in ("cronbach_alpha", "mcdonald_omega", "split_half_reliability", "item_analysis", "icc_reliability"):
        if len(num) < 2:
            return _mismatch(fn, name, f"{name} requires >= 2 numeric item columns.", "Select Likert/scale item columns.")
        if n_obs < 20:
            return _warn(fn, name, f"Small sample (n={n_obs}) for reliability analysis. Cronbach's α may be unstable.", "Aim for n >= 50.")
        return _ok(fn, name)

    if fn == "kr20":
        non_binary = [c for c in num if not _is_binary(df[c])]
        if non_binary:
            return _mismatch(fn, name, f"KR-20 requires binary (0/1) items. Non-binary columns: {non_binary}.",
                             "Use Cronbach's Alpha for polytomous items.")
        if len(num) < 2:
            return _mismatch(fn, name, "KR-20 requires >= 2 binary item columns.", "Select 0/1 coded items.")
        return _ok(fn, name)

    return _ok(fn, name)


def _check_multilevel(fn, name, df, variables, brief):
    num = _numeric_cols(df, variables)
    n_obs = _n(df, variables)
    group_col = variables[1] if len(variables) > 1 else None

    if fn in ("linear_mixed_model", "linear_mixed_effects", "cross_classified_mlm", "growth_curve_model", "multilevel_mediation"):
        if len(variables) < 3:
            return _mismatch(fn, name, f"{name} requires outcome, group, and predictor(s).", "Select 3+ variables.")
        if group_col and group_col in df.columns:
            n_clusters = df[group_col].nunique()
            if n_clusters < 3:
                return _warn(fn, name, f"Only {n_clusters} clusters found. Multilevel models need >= 5 clusters for stability.",
                             "Use regular regression if fewer than 5 clusters.")
        if n_obs < 50:
            return _warn(fn, name, f"Small sample (n={n_obs}). Multilevel models need large samples.", "Aim for n >= 100.")
        return _ok(fn, name)

    if fn in ("glmm", "gee"):
        if len(variables) < 3:
            return _mismatch(fn, name, f"{name} requires outcome, group, and predictor(s).", "Select 3+ variables.")
        return _ok(fn, name)

    return _ok(fn, name)


def _check_survival(fn, name, df, variables, brief):
    n_obs = _n(df, variables)
    if fn in ("kaplan_meier", "survival_analysis", "log_rank_test", "cox_ph_regression",
              "cox_regression", "weibull_aft", "nelson_aalen", "life_table", "ph_assumption_test", "competing_risks"):
        if len(variables) < 2:
            return _mismatch(fn, name, "Survival analysis requires a time column and an event column.", "Select time and event variables.")
        if n_obs < 20:
            return _warn(fn, name, f"Very small sample (n={n_obs}) for survival analysis. Kaplan-Meier curves may be unstable.", "Collect more data.")
        return _ok(fn, name)
    return _ok(fn, name)


def _check_time_series(fn, name, df, variables, brief):
    num = _numeric_cols(df, variables)
    n_obs = _n(df, variables)
    if fn in ("adf_test", "kpss_test", "autocorrelation", "partial_autocorrelation",
              "ljung_box", "arima_model", "sarima_model", "exponential_smoothing",
              "seasonal_decompose", "time_series", "mann_kendall"):
        if not num:
            return _mismatch(fn, name, "Time series tests require a numeric time-series column.", "Select a numeric column ordered over time.")
        if n_obs < 20:
            return _warn(fn, name, f"Very short time series (n={n_obs}). Results may be unreliable.", "Aim for n >= 50 time points.")
        return _ok(fn, name)
    if fn in ("granger_causality", "var_model"):
        if len(num) < 2:
            return _mismatch(fn, name, f"{name} requires >= 2 time series columns.", "Select 2+ numeric columns.")
        return _ok(fn, name)
    return _ok(fn, name)


def _check_multivariate(fn, name, df, variables, brief):
    num = _numeric_cols(df, variables)
    n_obs = _n(df, variables)

    if fn in ("pca",):
        if len(num) < 3:
            return _mismatch(fn, name, "PCA requires >= 3 numeric columns.", "Select 3+ continuous variables.")
        if n_obs < len(num) * 5:
            return _warn(fn, name, f"Small sample (n={n_obs}) relative to number of variables ({len(num)}). PCA may be unstable.",
                         "Aim for n >= 5× the number of variables.")
        return _ok(fn, name)

    if fn in ("factor_analysis", "confirmatory_fa"):
        if len(num) < 4:
            return _mismatch(fn, name, "Factor analysis needs >= 4 numeric variables.", "Select 4+ scale items.")
        if n_obs < 50:
            return _warn(fn, name, f"Small sample (n={n_obs}) for factor analysis. Aim for n >= 100.", "Collect more data.")
        return _ok(fn, name)

    if fn == "discriminant_analysis":
        group_col = variables[0] if variables else None
        n_groups = _group_counts(df, group_col) if group_col else None
        if len(num) < 2:
            return _mismatch(fn, name, "Discriminant analysis needs group + >= 2 numeric predictors.", "Select group and numeric predictors.")
        if n_obs < 50:
            return _warn(fn, name, f"Small sample (n={n_obs}) for discriminant analysis.", "Aim for n >= 5× number of predictors.")
        return _ok(fn, name)

    if fn == "sem":
        if len(num) < 5:
            return _mismatch(fn, name, "SEM typically requires >= 5 observed indicator variables.", "Select 5+ numeric variables.")
        if n_obs < 100:
            return _warn(fn, name, f"Small sample (n={n_obs}) for SEM. Aim for n >= 200.", "Consider CFA or path analysis instead.")
        return _ok(fn, name)

    if fn == "cluster_analysis":
        if len(num) < 2:
            return _mismatch(fn, name, "Cluster analysis requires >= 2 numeric variables.", "Select 2+ continuous variables.")
        return _ok(fn, name)

    return _ok(fn, name)


def _check_frequencies(fn, name, df, variables, brief):
    """Fitness checker for frequency_analysis and descriptive_stats."""
    if len(variables) == 0:
        return _warn(fn, name, "No variables specified — all columns will be analysed.", None)
    # Always OK — these are baseline tests that run on any data
    return _ok(fn, name)


def _check_normality_family(fn, name, df, variables, brief):
    """Fitness checker for normality tests (Shapiro-Wilk, Jarque-Bera, etc.)."""
    n_obs = _n(df, variables[:3])
    num   = _numeric_cols(df, variables)

    if len(num) == 0:
        # Allow zero numeric — normality_check may auto-detect numeric cols
        if not variables:
            return _warn(fn, name, "No variables specified — normality will be tested on all numeric columns.", None)
        return _warn(fn, name, "No numeric variables found in selection. Normality tests require continuous data.",
                     "Select numeric (ratio/continuous) columns.")

    if fn in ("shapiro_wilk", "shapiro_wilk_all", "normality_check"):
        if n_obs > 5000:
            return _warn(fn, name,
                         f"Shapiro-Wilk becomes overly sensitive for large samples (n={n_obs}). Consider Kolmogorov-Smirnov or Q-Q plots.",
                         "For n > 5000, rely on visual inspection (Q-Q plot) and effect sizes.")
        if n_obs < 3:
            return _mismatch(fn, name, f"Normality test requires at least 3 observations (n={n_obs}).",
                             "Collect more data.")

    if fn == "jarque_bera":
        if n_obs < 20:
            return _warn(fn, name, f"Jarque-Bera is unreliable for small samples (n={n_obs}).",
                         "Use Shapiro-Wilk for n < 50.")

    return _ok(fn, name)


# ─── Family routing table ──────────────────────────────────────────────────────

_FAMILY_CHECKERS = {
    "parametric":    _check_t_tests,
    "anova":         _check_anova,
    "non_parametric": _check_nonparametric,
    "correlation":   _check_correlation,
    "regression":    _check_regression,
    "reliability":   _check_reliability,
    "multilevel":    _check_multilevel,
    "survival":      _check_survival,
    "time_series":   _check_time_series,
    "multivariate":  _check_multivariate,
    "frequencies":   _check_frequencies,
    "normality":     _check_normality_family,
}

# Map specific test functions to their checker (for tests that span families)
_FN_OVERRIDES = {
    # Parametric t-tests
    "one_sample_t_test": _check_t_tests,
    "one_sample_t_cohend": _check_t_tests,
    "independent_t_test": _check_t_tests,
    "independent_t_cohend": _check_t_tests,
    "welch_t_test": _check_t_tests,
    "paired_t_test": _check_t_tests,
    "paired_t_cohend": _check_t_tests,
    # ANOVA group
    "one_way_anova": _check_anova,
    "anova_eta_squared": _check_anova,
    "anova_descriptives": _check_anova,
    "welch_anova": _check_anova,
    "two_way_anova": _check_anova,
    "two_way_eta_squared": _check_anova,
    "two_way_pairwise": _check_anova,
    "repeated_anova": _check_anova,
    "ancova": _check_anova,
    "manova": _check_anova,
    "manova_followup": _check_anova,
    # Normality tests
    "normality_check":    _check_normality_family,
    "shapiro_wilk_all":   _check_normality_family,
    "shapiro_wilk":       _check_normality_family,
    "jarque_bera":        _check_normality_family,
    "dagostino_k2":       _check_normality_family,
    "kolmogorov_smirnov": _check_normality_family,
    "anderson_darling":   _check_normality_family,
    "lilliefors":         _check_normality_family,
    # Frequency analysis
    "frequency_analysis": _check_frequencies,
    "descriptive_stats":  _check_frequencies,  # always ok
}


def check_test_fitness(
    test_function: str,
    test_name: str,
    df: pd.DataFrame,
    variables: list,
    brief: dict,
    registry_entry: dict = None,
) -> dict:
    """
    Main entry point. Given a test and dataset, returns a fitness report dict.
    Works entirely without AI — pure data-driven rules.
    """
    # Lookup override checker by function name
    checker = _FN_OVERRIDES.get(test_function)

    # Fallback: look up by registry family
    if checker is None and registry_entry:
        family = (registry_entry.get("family") or "").lower().replace(" ", "_").replace("-", "_")
        checker = _FAMILY_CHECKERS.get(family)

    # Generic fallback
    if checker is None:
        # Route by keyword in test name
        fn_lower = test_function.lower()
        if any(k in fn_lower for k in ("t_test", "t_cohend")):
            checker = _check_t_tests
        elif any(k in fn_lower for k in ("anova", "ancova", "manova")):
            checker = _check_anova
        elif any(k in fn_lower for k in ("mann_whitney", "wilcoxon", "kruskal", "friedman", "chi_square", "fisher_exact", "mcnemar", "sign_test", "runs_test")):
            checker = _check_nonparametric
        elif any(k in fn_lower for k in ("correlation", "biserial", "phi", "cramers")):
            checker = _check_correlation
        elif any(k in fn_lower for k in ("regression", "mediation", "moderation")):
            checker = _check_regression
        elif any(k in fn_lower for k in ("cronbach", "omega", "split_half", "item_analysis", "icc", "kr20")):
            checker = _check_reliability
        elif any(k in fn_lower for k in ("mixed_model", "mixed_effects", "glmm", "gee", "multilevel", "growth_curve")):
            checker = _check_multilevel
        elif any(k in fn_lower for k in ("kaplan", "survival", "cox", "weibull", "nelson", "life_table", "competing")):
            checker = _check_survival
        elif any(k in fn_lower for k in ("adf", "kpss", "autocorrelation", "arima", "sarima", "time_series", "granger", "var_model", "kendall")):
            checker = _check_time_series
        elif any(k in fn_lower for k in ("pca", "factor_analysis", "discriminant", "cluster", "sem", "path_analysis")):
            checker = _check_multivariate
        else:
            return _ok(test_function, test_name)

    try:
        return checker(test_function, test_name, df, variables, brief)
    except Exception as e:
        # Never crash the pipeline on a fitness check error
        return _warn(test_function, test_name,
                     f"Fitness check encountered an error: {e}",
                     "Review variable selection manually.")


def check_all_tests_fitness(
    tests: list[dict],
    df: pd.DataFrame,
    brief: dict,
    registry: dict = None,
    manual_only: bool = False,
) -> list[dict]:
    """
    Run fitness checks on all tests in the test plan.

    Args:
        tests:       List of test spec dicts (from Stage 4 / _select_tests)
        df:          The dataset
        brief:       Research brief
        registry:    Optional registry dict for family lookup
        manual_only: If True, only flag manually-selected tests (skip auto-selected)

    Returns:
        List of fitness report dicts — only warnings/mismatches (no 'good' to reduce noise).
    """
    issues = []
    for spec in tests:
        fn = (spec.get("test_function") or "").strip()
        name = spec.get("test_name") or fn
        variables = [v for v in (spec.get("variables") or []) if isinstance(v, str)]

        if not fn:
            continue

        # Optionally skip auto-selected tests — only flag manual user choices
        if manual_only and not spec.get("manually_selected", False):
            continue

        reg_entry = registry.get(fn) if registry else None
        report = check_test_fitness(fn, name, df, variables, brief, reg_entry)

        if report["fitness"] in (WARNING, MISMATCH):
            report["test_spec"] = spec  # attach original spec for context
            issues.append(report)

    return issues
