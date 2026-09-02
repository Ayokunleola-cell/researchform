"""
Full QA Test Suite for the Statistical Analysis Engine.

Tests every statistical test in the registry using synthetic data designed
to meet each test's requirements. Reports pass/fail/skip per test with errors.

Usage:
    python qa_analysis_engine.py
    python qa_analysis_engine.py --quick   (just show failures)
"""
import sys
import io
# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import sys
import os
import traceback
import json
import warnings
warnings.filterwarnings("ignore")

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime

np.random.seed(42)
ALPHA = 0.05
N_BIG   = 120   # For advanced tests (PCA, SEM, etc.)
N_MED   = 50    # Medium-size
N_SMALL = 25    # Small (t-tests, etc.)

# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC DATASETS
# ─────────────────────────────────────────────────────────────────────────────

def make_big():
    """120 row dataset with all variable types."""
    rng = np.random.default_rng(42)
    n = N_BIG
    groups = np.tile(["A", "B", "C"], n // 3 + 1)[:n]
    binary = np.where(rng.random(n) > 0.5, 1, 0)
    return pd.DataFrame({
        "id":       np.arange(n),
        "age":      rng.normal(35, 10, n).clip(18, 80),
        "income":   rng.lognormal(10, 1, n),
        "score1":   rng.normal(65, 12, n).clip(0, 100),
        "score2":   rng.normal(70, 10, n).clip(0, 100),
        "score3":   rng.normal(55, 15, n).clip(0, 100),
        "likert1":  rng.integers(1, 6, n),
        "likert2":  rng.integers(1, 6, n),
        "likert3":  rng.integers(1, 6, n),
        "likert4":  rng.integers(1, 6, n),
        "likert5":  rng.integers(1, 6, n),
        # Binary item columns for KR-20 (strictly 0/1)
        "bi1":      rng.integers(0, 2, n),
        "bi2":      rng.integers(0, 2, n),
        "bi3":      rng.integers(0, 2, n),
        "bi4":      rng.integers(0, 2, n),
        # Count variable for Poisson/NegBin (non-negative integers)
        "count_var": rng.poisson(lam=5, size=n),
        "group":    groups,
        "gender":   np.where(binary == 1, "Male", "Female"),
        "binary":   binary,
        "pre":      rng.normal(50, 8, n),
        "post":     rng.normal(55, 8, n),
        "time":     np.arange(n) + rng.normal(0, 2, n),
        "event":    binary,
        "duration": rng.exponential(10, n).clip(0.1, 50),
        "county":   np.tile(["C1","C2","C3","C4","C5"], n // 5 + 1)[:n],
        "cat3":     np.tile(["X","Y","Z"], n // 3 + 1)[:n],
        "mediator": rng.normal(0, 1, n),
        "moderator":rng.normal(0, 1, n),
        "control":  rng.normal(0, 1, n),
    })


def make_small():
    """25 row dataset for smaller tests."""
    rng = np.random.default_rng(7)
    n = N_SMALL
    groups = np.tile(["A", "B"], n // 2 + 1)[:n]
    return pd.DataFrame({
        "id":      np.arange(n),
        "x":       rng.normal(50, 10, n),
        "y":       rng.normal(55, 10, n),
        "z":       rng.normal(48, 12, n),
        "group":   groups,
        "gender":  np.where(rng.random(n) > 0.5, "Male", "Female"),
        "binary":  (rng.random(n) > 0.5).astype(int),
        "likert1": rng.integers(1, 6, n),
        "likert2": rng.integers(1, 6, n),
        "likert3": rng.integers(1, 6, n),
        "cat":     np.tile(["P","Q","R"], n // 3 + 1)[:n],
    })


BIG_DF   = make_big()
SMALL_DF = make_small()

BRIEF_BASE = {
    "topic": "QA Test Study",
    "significance_level": ALPHA,
    "test_value": 50,
}

# ─────────────────────────────────────────────────────────────────────────────
# TEST CONFIGURATION
# Maps each test_function → (df_to_use, variables, extra_brief)
# ─────────────────────────────────────────────────────────────────────────────

TEST_CONFIG = {
    # ── DESCRIPTIVE ──────────────────────────────────────────────────────────
    "descriptive_stats":       (BIG_DF,   ["age","income","score1","likert1","group"]),
    "frequency_analysis":      (BIG_DF,   ["group","gender","cat3"]),
    "mean_median_mode":        (BIG_DF,   ["age","score1","score2"]),
    "dispersion_extended":     (BIG_DF,   ["age","income","score1"]),
    "percentiles_extended":    (BIG_DF,   ["age","income","score1"]),
    "z_scores":                (BIG_DF,   ["age","income","score1"]),
    "skewness_analysis":       (BIG_DF,   ["age","income","score1"]),
    "kurtosis_analysis":       (BIG_DF,   ["age","income","score1"]),
    "variable_transformation": (BIG_DF,   ["age","income","score1"]),

    # ── NORMALITY ─────────────────────────────────────────────────────────────
    "normality_check":         (BIG_DF,   ["age","score1","score2","income"]),
    "shapiro_wilk_all":        (SMALL_DF, ["x","y","z"]),
    "kolmogorov_smirnov":      (BIG_DF,   ["age","income"]),
    "anderson_darling":        (BIG_DF,   ["age","score1"]),
    "jarque_bera":             (BIG_DF,   ["age","income","score1"]),
    "dagostino_pearson":       (BIG_DF,   ["age","score1"]),
    "omnibus_normality":       (BIG_DF,   ["age","score1"]),

    # ── RELIABILITY ───────────────────────────────────────────────────────────
    "cronbach_alpha":          (BIG_DF,   ["likert1","likert2","likert3","likert4","likert5"]),
    "mcdonald_omega":          (BIG_DF,   ["likert1","likert2","likert3","likert4","likert5"]),
    "split_half_reliability":  (BIG_DF,   ["likert1","likert2","likert3","likert4"]),
    "item_analysis":           (BIG_DF,   ["likert1","likert2","likert3","likert4","likert5"]),
    "icc_reliability":         (BIG_DF,   ["likert1","likert2","likert3"]),
    # KR-20 requires strictly binary (0/1) items — use dedicated bi1/bi2/bi3 columns
    "kr20":                    (BIG_DF,   ["bi1","bi2","bi3","bi4"]),

    # ── ASSUMPTION CHECKS ─────────────────────────────────────────────────────
    "levene_test":             (BIG_DF,   ["group","score1"]),
    "bartlett_test":           (BIG_DF,   ["group","score1"]),
    "mauchly_test":            (BIG_DF,   ["likert1","likert2","likert3","likert4"]),
    "durbin_watson":           (BIG_DF,   ["age","income","score1"]),
    "vif_check":               (BIG_DF,   ["score1","age","income","score2"]),
    "outliers_iqr":            (BIG_DF,   ["age","income","score1"]),
    "outliers_zscore":         (BIG_DF,   ["age","income","score1"]),
    "outliers_grubbs":         (BIG_DF,   ["age","score1"]),
    "mahalanobis_distance":    (BIG_DF,   ["age","income","score1","score2"]),
    "cooks_distance":          (BIG_DF,   ["score1","age","income"]),

    # ── PARAMETRIC ────────────────────────────────────────────────────────────
    "one_sample_t_test":       (BIG_DF,   ["score1"]),
    "one_sample_t_cohend":     (BIG_DF,   ["score1"]),
    "independent_t_test":      (BIG_DF,   ["gender","score1"]),
    "independent_t_cohend":    (BIG_DF,   ["gender","score1"]),
    "welch_t_test":            (BIG_DF,   ["gender","score1"]),
    "paired_t_test":           (BIG_DF,   ["pre","post"]),
    "paired_t_cohend":         (BIG_DF,   ["pre","post"]),
    "one_way_anova":           (BIG_DF,   ["group","score1"]),
    "anova_eta_squared":       (BIG_DF,   ["group","score1"]),
    "anova_descriptives":      (BIG_DF,   ["group","score1"]),
    "welch_anova":             (BIG_DF,   ["group","score1"]),
    "two_way_anova":           (BIG_DF,   ["group","gender","score1"]),
    "two_way_eta_squared":     (BIG_DF,   ["group","gender","score1"]),
    "two_way_pairwise":        (BIG_DF,   ["group","gender","score1"]),
    "repeated_anova":          (BIG_DF,   ["likert1","likert2","likert3"]),
    "ancova":                  (BIG_DF,   ["group","score1","age"]),
    "manova":                  (BIG_DF,   ["group","score1","score2","score3"]),
    "manova_followup":         (BIG_DF,   ["group","score1","score2","score3"]),

    # ── NON-PARAMETRIC ────────────────────────────────────────────────────────
    "mann_whitney":            (BIG_DF,   ["gender","score1"]),
    "mann_whitney_r":          (BIG_DF,   ["gender","score1"]),
    "mann_whitney_ci":         (BIG_DF,   ["gender","score1"]),
    "wilcoxon":                (BIG_DF,   ["pre","post"]),
    "wilcoxon_r":              (BIG_DF,   ["pre","post"]),
    "kruskal_wallis":          (BIG_DF,   ["group","score1"]),
    "kruskal_wallis_eta2":     (BIG_DF,   ["group","score1"]),
    "friedman_test":           (BIG_DF,   ["likert1","likert2","likert3"]),
    "kendall_w":               (BIG_DF,   ["likert1","likert2","likert3"]),
    "mcnemar":                 (BIG_DF,   ["binary","event"]),
    "chi_square":              (BIG_DF,   ["group","gender"]),
    "chi_square_extended":     (BIG_DF,   ["group","gender"]),
    "fisher_exact":            (BIG_DF,   ["gender","binary"]),
    "sign_test":               (BIG_DF,   ["pre","post"]),
    "runs_test":               (BIG_DF,   ["score1"]),

    # ── POST-HOC ──────────────────────────────────────────────────────────────
    "tukey_hsd":               (BIG_DF,   ["group","score1"]),
    "bonferroni_test":         (BIG_DF,   ["group","score1"]),
    "dunn_test":               (BIG_DF,   ["group","score1"]),
    "scheffe_test":            (BIG_DF,   ["group","score1"]),
    "newman_keuls":            (BIG_DF,   ["group","score1"]),
    "fisher_lsd":              (BIG_DF,   ["group","score1"]),
    "dunnett_test":            (BIG_DF,   ["group","score1"]),

    # ── CORRELATION ───────────────────────────────────────────────────────────
    "pearson_correlation":     (BIG_DF,   ["age","income"]),
    "pearson_ci":              (BIG_DF,   ["age","income"]),
    "spearman_correlation":    (BIG_DF,   ["likert1","likert2"]),
    "kendall_tau":             (BIG_DF,   ["likert1","likert2"]),
    "point_biserial":          (BIG_DF,   ["binary","score1"]),
    "phi_coefficient":         (BIG_DF,   ["binary","event"]),
    "cramers_v":               (BIG_DF,   ["group","gender"]),
    "partial_correlation":     (BIG_DF,   ["age","income","score1"]),
    "canonical_correlation":   (BIG_DF,   ["age","score1","score2","income","score3"]),
    "correlation_matrix":      (BIG_DF,   ["age","income","score1","score2","score3"]),
    "correlation_heatmap":     (BIG_DF,   ["age","income","score1","score2"]),
    "correlation_significance": (BIG_DF,  ["age","income","score1","score2"]),
    "correlation_effect_sizes": (BIG_DF,  ["age","income","score1","score2"]),
    "correlation_splom":       (BIG_DF,   ["age","income","score1","score2"]),

    # ── REGRESSION ────────────────────────────────────────────────────────────
    "simple_linear_regression":(BIG_DF,   ["age","income"]),
    "linear_regression":       (BIG_DF,   ["age","income"]),
    "multiple_regression":     (BIG_DF,   ["score1","age","income","score2"]),
    "logistic_regression":     (BIG_DF,   ["binary","age","income","score1"]),
    "ordinal_regression":      (BIG_DF,   ["likert1","age","income"]),
    "multinomial_logistic":    (BIG_DF,   ["group","age","income","score1"]),
    "hierarchical_regression": (BIG_DF,   ["score1","age","income","score2","score3"]),
    "stepwise_regression":     (BIG_DF,   ["score1","age","income","score2","score3"]),
    "mediation_analysis":      (BIG_DF,   ["age","mediator","score1"]),
    "moderation_analysis":     (BIG_DF,   ["age","moderator","score1"]),
    "quantile_regression":     (BIG_DF,   ["score1","age","income"]),
    # Poisson/NegBin require non-negative INTEGER count DVs — use count_var column
    "poisson_regression":      (BIG_DF,   ["count_var","age","income"]),
    "negative_binomial":       (BIG_DF,   ["count_var","age","income"]),

    # ── ADVANCED MULTIVARIATE ─────────────────────────────────────────────────
    "pca":                     (BIG_DF,   ["age","income","score1","score2","score3","likert1","likert2"]),
    "factor_analysis":         (BIG_DF,   ["likert1","likert2","likert3","likert4","likert5"]),
    "confirmatory_fa":         (BIG_DF,   ["likert1","likert2","likert3","likert4","likert5"]),
    "discriminant_analysis":   (BIG_DF,   ["group","age","income","score1"]),
    "cluster_analysis":        (BIG_DF,   ["age","income","score1","score2"]),
    "sem":                     (BIG_DF,   ["likert1","likert2","likert3","likert4","likert5"]),
    "path_analysis":           (BIG_DF,   ["age","income","score1","score2"]),

    # ── SURVIVAL ──────────────────────────────────────────────────────────────
    "kaplan_meier":            (BIG_DF,   ["duration","event"]),
    "survival_analysis":       (BIG_DF,   ["duration","event"]),
    "log_rank_test":           (BIG_DF,   ["duration","event","gender"]),
    "cox_ph_regression":       (BIG_DF,   ["duration","event","age","income"]),
    "cox_regression":          (BIG_DF,   ["duration","event","age","income"]),
    "weibull_aft":             (BIG_DF,   ["duration","event","age"]),
    "nelson_aalen":            (BIG_DF,   ["duration","event"]),
    "life_table":              (BIG_DF,   ["duration","event"]),
    "ph_assumption_test":      (BIG_DF,   ["duration","event","age"]),
    "competing_risks":         (BIG_DF,   ["duration","event","gender"]),

    # ── CAUSAL INFERENCE ─────────────────────────────────────────────────────
    "difference_in_differences":(BIG_DF,  ["binary","time","score1"]),
    "instrumental_variables":  (BIG_DF,   ["mediator","age","score1"]),
    "propensity_score_matching":(BIG_DF,  ["binary","age","income","score1"]),
    "regression_discontinuity":(BIG_DF,   ["age","score1","binary"]),
    "bayesian_ab_test":        (BIG_DF,   ["gender","score1"]),
    "synthetic_control":       (BIG_DF,   ["time","score1","group"]),
    "sensitivity_analysis":    (BIG_DF,   ["age","score1","income"]),

    # ── TIME SERIES ───────────────────────────────────────────────────────────
    "adf_test":                (BIG_DF,   ["time"]),
    "kpss_test":               (BIG_DF,   ["time"]),
    "autocorrelation":         (BIG_DF,   ["time"]),
    "partial_autocorrelation": (BIG_DF,   ["time"]),
    "ljung_box":               (BIG_DF,   ["time"]),
    "seasonal_decompose":      (BIG_DF,   ["time"]),
    "arima_model":             (BIG_DF,   ["time"]),
    "time_series":             (BIG_DF,   ["time"]),
    "sarima_model":            (BIG_DF,   ["time"]),
    "exponential_smoothing":   (BIG_DF,   ["time"]),
    "granger_causality":       (BIG_DF,   ["score1","score2"]),
    "var_model":               (BIG_DF,   ["score1","score2","score3"]),
    "mann_kendall":            (BIG_DF,   ["time"]),

    # ── MULTILEVEL ───────────────────────────────────────────────────────────
    # LMM/LME: variables[0]=outcome(numeric), variables[1]=group, variables[2+]=predictors
    "linear_mixed_model":      (BIG_DF,   ["score1","county","age"]),
    "linear_mixed_effects":    (BIG_DF,   ["score1","county","age"]),
    # GLMM/GEE: variables[0]=binary outcome, variables[1]=group, variables[2+]=predictors
    "glmm":                    (BIG_DF,   ["binary","county","age"]),
    # ICC: wide rater columns (all numeric)
    "icc":                     (BIG_DF,   ["likert1","likert2","score1"]),
    "random_effects_anova":    (BIG_DF,   ["county","score1"]),
    # cross_classified: outcome, group1, group2, predictor
    "cross_classified_mlm":    (BIG_DF,   ["score1","county","group","age"]),
    # growth_curve: outcome, subject, time  (note: time must be numeric)
    "growth_curve_model":      (BIG_DF,   ["score1","county","time"]),

    # multilevel_mediation: IV, mediator, DV, group
    "multilevel_mediation":    (BIG_DF,   ["age","score1","income","county"]),
    # GEE: outcome, group, predictors
    "gee":                     (BIG_DF,   ["binary","county","age"]),
}


# ─────────────────────────────────────────────────────────────────────────────
# RUN TESTS
# ─────────────────────────────────────────────────────────────────────────────

def run_single(test_fn, fn_callable, df, variables, brief):
    """Run one test, return (status, result_or_error)."""
    try:
        result = fn_callable(df=df, variables=variables, brief=brief, alpha=ALPHA)
        if result is None:
            return "NULL_RESULT", "Function returned None"
        if result.get("error"):
            return "SOFT_FAIL", result.get("reason", "Unknown error")
        # Check required fields
        for field in ("test_name", "statistic", "conclusion"):
            if field not in result:
                return "MISSING_FIELD", f"Missing field: {field}"
        return "PASS", result
    except Exception as e:
        return "ERROR", traceback.format_exc()


def main():
    quick_mode = "--quick" in sys.argv

    from analysis.engine.registry import get_registry
    registry = get_registry()

    print(f"\n{'═'*72}")
    print(f"  RESEARCHFORM STATISTICAL ENGINE — FULL QA TEST SUITE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {len(registry)} tests registered")
    print(f"{'═'*72}\n")

    results = {"PASS": [], "SOFT_FAIL": [], "ERROR": [], "NULL_RESULT": [],
               "MISSING_FIELD": [], "NOT_CONFIGURED": [], "NOT_REGISTERED": []}

    # Check which registry tests are NOT in our config
    for key in registry:
        if key not in TEST_CONFIG:
            results["NOT_CONFIGURED"].append(key)

    # Check which configured tests are NOT in registry
    for key in TEST_CONFIG:
        if key not in registry:
            results["NOT_REGISTERED"].append(key)

    total = len(TEST_CONFIG)
    done = 0

    for test_fn, (df, variables, *extra) in TEST_CONFIG.items():
        done += 1
        brief = {**BRIEF_BASE, **(extra[0] if extra else {})}

        if test_fn not in registry:
            if not quick_mode:
                print(f"  [{done:3d}/{total}] ⚠  {test_fn:<45} NOT IN REGISTRY")
            continue

        entry = registry[test_fn]
        fn = entry["fn"]

        status, payload = run_single(test_fn, fn, df, variables, brief)
        results[status].append(test_fn)

        if not quick_mode or status != "PASS":
            icon = {"PASS":"✓", "SOFT_FAIL":"⚡", "ERROR":"✗",
                    "NULL_RESULT":"○", "MISSING_FIELD":"⚠"}.get(status, "?")
            msg = ""
            if status == "SOFT_FAIL":
                msg = f"  → {payload}"
            elif status == "ERROR":
                lines = payload.strip().split("\n")
                msg = f"  → {lines[-1]}"
            print(f"  [{done:3d}/{total}] {icon}  {test_fn:<45} {status}{msg}")

    # ── SUMMARY ─────────────────────────────────────────────────────────────
    print(f"\n{'═'*72}")
    print(f"  QA SUMMARY")
    print(f"{'═'*72}")
    print(f"  ✓ PASS           : {len(results['PASS'])}")
    print(f"  ⚡ SOFT_FAIL      : {len(results['SOFT_FAIL'])}  (ran but returned error dict)")
    print(f"  ✗ ERROR          : {len(results['ERROR'])}  (exception thrown)")
    print(f"  ○ NULL_RESULT    : {len(results['NULL_RESULT'])}  (returned None)")
    print(f"  ⚠ MISSING_FIELD  : {len(results['MISSING_FIELD'])}  (incomplete schema)")
    print(f"  — NOT_CONFIGURED : {len(results['NOT_CONFIGURED'])}  (in registry, not in QA config)")
    print(f"  — NOT_REGISTERED : {len(results['NOT_REGISTERED'])}  (in QA config, not in registry)")

    if results["SOFT_FAIL"]:
        print(f"\n  SOFT_FAIL tests (data mismatch — expected, check variables):")
        for t in results["SOFT_FAIL"]:
            print(f"    • {t}")

    if results["ERROR"]:
        print(f"\n  ERROR tests (need fixing):")
        for t in results["ERROR"]:
            print(f"    • {t}")

    if results["NOT_CONFIGURED"]:
        print(f"\n  Tests in registry but not in QA config (add configs to cover them):")
        for t in results["NOT_CONFIGURED"]:
            print(f"    • {t}")

    total_run = total
    pass_rate = len(results["PASS"]) / max(total_run, 1) * 100
    print(f"\n  Overall pass rate: {pass_rate:.1f}%  ({len(results['PASS'])}/{total_run})")
    print(f"{'═'*72}\n")

    return results


if __name__ == "__main__":
    main()
