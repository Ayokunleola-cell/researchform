#!/usr/bin/env python
"""
full_analysis_test_runner.py
============================
Runs EVERY statistical test in the ResearchForm analysis engine against the
realistic "Employee Wellbeing & Performance Survey" dataset.

This is a REAL APPLICATION END-TO-END TEST — no synthetic mini-datasets,
no mocked data. Uses the actual 350-row survey_dataset.csv with proper
variable mappings for each test type.

Output:
    full_analysis_report.txt     (detailed pass/fail per test)
    full_analysis_summary.csv    (machine-readable results)

Run:
    python full_analysis_test_runner.py
    python full_analysis_test_runner.py --verbose     (show full result dicts)
"""
import sys
import time
import traceback
import json
import warnings
import textwrap
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ─── Load Dataset ─────────────────────────────────────────────────────────────
DATASET_PATH = Path(__file__).parent / "survey_dataset.csv"
if not DATASET_PATH.exists():
    print("ERROR: survey_dataset.csv not found. Run generate_survey_dataset.py first.")
    sys.exit(1)

df = pd.read_csv(DATASET_PATH)
print(f"Loaded dataset: {df.shape[0]} rows × {df.shape[1]} columns")

# ─── Brief (mimics pipeline brief for real analysis) ──────────────────────────
BRIEF = {
    "topic": "Employee Wellbeing, Stress & Organizational Performance Study",
    "research_question": "What factors predict employee burnout, turnover intention, and performance?",
    "significance_level": 0.05,
    "test_value": 3.0,   # null hypothesis mean for one-sample tests
    "confidence_level": 0.95,
}

ALPHA = 0.05
VERBOSE = "--verbose" in sys.argv

# ─── Import all test functions ─────────────────────────────────────────────────
try:
    from analysis.engine.registry import get_registry
    REGISTRY = get_registry()
    print(f"Registry loaded: {len(REGISTRY)} tests registered")
except Exception as e:
    print(f"ERROR loading registry: {e}")
    traceback.print_exc()
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════════
# TEST PLAN — Maps every registered test → real survey variables
# Each entry: test_function → (variables, optional_brief_overrides)
# Variables are chosen to semantically match the test's requirements.
# ═══════════════════════════════════════════════════════════════════════════════
TEST_PLAN = {

    # ── DESCRIPTIVE ────────────────────────────────────────────────────────────
    "descriptive_stats":          (["age", "salary", "performance_score", "stress_score", "wellbeing_index", "burnout_total"], {}),
    "frequency_analysis":         (["department", "gender", "education", "employment_type", "stress_category"], {}),
    "mean_median_mode":           (["age", "performance_score", "wellbeing_index"], {}),
    "dispersion_extended":        (["salary", "stress_score", "productivity_pct"], {}),
    "percentiles_extended":       (["salary", "performance_score", "stress_score"], {}),
    "z_scores":                   (["salary", "stress_score", "performance_score"], {}),
    "skewness_analysis":          (["salary", "absences_count", "incidents_count"], {}),
    "kurtosis_analysis":          (["salary", "absences_count", "incidents_count"], {}),
    "variable_transformation":    (["salary", "absences_count", "incidents_count"], {}),

    # ── NORMALITY ──────────────────────────────────────────────────────────────
    "normality_check":            (["performance_score", "wellbeing_index", "stress_score", "salary"], {}),
    "shapiro_wilk_all":           (["stress_pre", "stress_post", "burnout_total"], {}),
    "kolmogorov_smirnov":         (["salary", "tenure_years"], {}),
    "anderson_darling":           (["performance_score", "stress_score"], {}),
    "jarque_bera":                (["salary", "wellbeing_index", "productivity_pct"], {}),
    "dagostino_pearson":          (["performance_score", "wellbeing_index"], {}),
    "omnibus_normality":          (["burnout_total", "satisfaction_total"], {}),

    # ── RELIABILITY ────────────────────────────────────────────────────────────
    "cronbach_alpha":             (["burnout_1", "burnout_2", "burnout_3", "burnout_4", "burnout_5"], {}),
    "mcdonald_omega":             (["satisfaction_1", "satisfaction_2", "satisfaction_3", "satisfaction_4", "satisfaction_5"], {}),
    "split_half_reliability":     (["burnout_1", "burnout_2", "burnout_3", "burnout_4", "burnout_5", "burnout_total"], {}),
    "item_analysis":              (["burnout_1", "burnout_2", "burnout_3", "burnout_4", "burnout_5"], {}),
    "icc_reliability":            (["burnout_1", "burnout_2", "burnout_3", "burnout_4", "burnout_5"], {}),
    "kr20":                       (["comp_item1", "comp_item2", "comp_item3", "comp_item4", "comp_item5", "comp_item6"], {}),

    # ── ASSUMPTION CHECKS & OUTLIERS ───────────────────────────────────────────
    "levene_test":                (["department", "performance_score"], {}),
    "bartlett_test":              (["department", "salary"], {}),
    "mauchly_test":               (["stress_pre", "stress_post", "stress_3m_followup"], {}),
    "durbin_watson":              (["performance_score", "workload_score", "autonomy_score"], {}),
    "vif_check":                  (["salary", "age", "tenure_years", "workload_score"], {}),
    "outliers_iqr":               (["salary", "absences_count", "stress_score"], {}),
    "outliers_zscore":            (["salary", "performance_score", "stress_score"], {}),
    "outliers_grubbs":            (["salary", "performance_score"], {}),
    "mahalanobis_distance":       (["salary", "age", "stress_score", "performance_score"], {}),
    "cooks_distance":             (["performance_score", "workload_score", "burnout_total"], {}),

    # ── PARAMETRIC TESTS ───────────────────────────────────────────────────────
    "one_sample_t_test":          (["performance_score"], {"test_value": 3.0}),
    "one_sample_t_cohend":        (["wellbeing_index"], {"test_value": 50.0}),
    # is_manager is strictly binary (0/1) — correct for 2-group t-tests
    "independent_t_test":         (["is_manager", "performance_score"], {}),
    "independent_t_cohend":       (["is_manager", "wellbeing_index"], {}),
    "welch_t_test":               (["is_manager", "salary"], {}),
    "paired_t_test":              (["stress_pre", "stress_post"], {}),
    "paired_t_cohend":            (["stress_pre", "stress_post"], {}),
    "one_way_anova":              (["department", "performance_score"], {}),
    "anova_eta_squared":          (["department", "salary"], {}),
    "anova_descriptives":         (["department", "wellbeing_index"], {}),
    "welch_anova":                (["department", "stress_score"], {}),
    "two_way_anova":              (["department", "gender", "performance_score"], {}),
    "two_way_eta_squared":        (["department", "gender", "wellbeing_index"], {}),
    "two_way_pairwise":           (["department", "gender", "stress_score"], {}),
    "repeated_anova":             (["stress_pre", "stress_post", "stress_3m_followup"], {}),
    "ancova":                     (["department", "performance_score", "age"], {}),
    "manova":                     (["department", "performance_score", "wellbeing_index", "stress_score"], {}),
    "manova_followup":            (["department", "performance_score", "wellbeing_index", "stress_score"], {}),

    # ── NON-PARAMETRIC ─────────────────────────────────────────────────────────
    # is_manager (0/1) is strictly binary — valid for 2-group non-parametric tests
    "mann_whitney":               (["is_manager", "performance_score"], {}),
    "mann_whitney_r":             (["is_manager", "salary"], {}),
    "mann_whitney_ci":            (["is_manager", "wellbeing_index"], {}),
    "wilcoxon":                   (["stress_pre", "stress_post"], {}),
    "wilcoxon_r":                 (["stress_pre", "stress_post"], {}),
    "kruskal_wallis":             (["department", "performance_score"], {}),
    "kruskal_wallis_eta2":        (["department", "stress_score"], {}),
    "friedman_test":              (["stress_pre", "stress_post", "stress_3m_followup"], {}),
    "sign_test":                  (["stress_pre", "stress_post"], {}),
    "chi_square":                 (["department", "gender"], {}),
    "chi_square_goodness":        (["department"], {}),
    # Fisher exact requires strict 2×2 — both columns must be binary (0/1)
    "fisher_exact":               (["received_training", "promoted"], {}),
    "mcnemar_test":               (["turnover_intent", "promoted"], {}),
    "binomial_test":              (["turnover_intent"], {}),
    "runs_test":                  (["turnover_intent"], {}),

    # ── CORRELATION ────────────────────────────────────────────────────────────
    "pearson_correlation":        (["satisfaction_total", "performance_score"], {}),
    "spearman_correlation":       (["burnout_total", "absences_count"], {}),
    "kendall_tau":                (["tenure_years", "salary"], {}),
    # point_biserial: is_manager (0/1 numeric) correlated with continuous salary
    "point_biserial":             (["is_manager", "salary"], {}),
    "phi_coefficient":            (["turnover_intent", "promoted"], {}),
    "cramers_v":                  (["department", "gender"], {}),
    "partial_correlation":        (["workload_score", "stress_score", "autonomy_score"], {}),
    "canonical_correlation":      (["burnout_total", "satisfaction_total", "engagement_1", "performance_score", "wellbeing_index"], {}),
    "correlation_matrix":         (["burnout_total", "satisfaction_total", "stress_score", "performance_score", "wellbeing_index"], {}),
    "correlation_heatmap":        (["burnout_total", "satisfaction_total", "stress_score", "performance_score"], {}),
    "correlation_significance":   (["burnout_total", "satisfaction_total", "stress_score", "performance_score"], {}),
    "correlation_effect_sizes":   (["burnout_total", "stress_score", "performance_score", "wellbeing_index"], {}),
    "correlation_splom":          (["burnout_total", "satisfaction_total", "stress_score", "performance_score"], {}),

    # ── REGRESSION ─────────────────────────────────────────────────────────────
    "simple_linear_regression":   (["burnout_total", "stress_score"], {}),
    "linear_regression":          (["burnout_total", "stress_score"], {}),
    "multiple_regression":        (["performance_score", "workload_score", "autonomy_score", "satisfaction_total"], {}),
    "logistic_regression":        (["turnover_intent", "burnout_total", "satisfaction_total", "tenure_years"], {}),
    "ordinal_regression":         (["perf_rating_1to4", "satisfaction_total", "workload_score"], {}),
    "multinomial_logistic":       (["department", "age", "salary", "satisfaction_total"], {}),
    "hierarchical_regression":    (["performance_score", "age", "tenure_years", "workload_score", "burnout_total"], {}),
    "stepwise_regression":        (["wellbeing_index", "burnout_total", "satisfaction_total", "workload_score", "autonomy_score"], {}),
    "mediation_analysis":         (["workload_score", "burnout_total", "performance_score"], {}),
    "moderation_analysis":        (["workload_score", "autonomy_score", "performance_score"], {}),
    "quantile_regression":        (["salary", "age", "tenure_years"], {}),
    "poisson_regression":         (["absences_count", "burnout_total", "workload_score", "age"], {}),
    "negative_binomial":          (["absences_count", "burnout_total", "workload_score"], {}),

    # ── ADVANCED MULTIVARIATE ──────────────────────────────────────────────────
    "pca":                        (["burnout_total", "satisfaction_total", "stress_score", "wellbeing_index", "performance_score", "workload_score", "autonomy_score"], {}),
    "factor_analysis":            (["burnout_1", "burnout_2", "burnout_3", "satisfaction_1", "satisfaction_2", "satisfaction_3", "engagement_1", "engagement_2"], {}),
    "confirmatory_fa":            (["burnout_1", "burnout_2", "burnout_3", "satisfaction_1", "satisfaction_2", "satisfaction_3"], {}),
    "discriminant_analysis":      (["department", "age", "salary", "burnout_total", "satisfaction_total"], {}),
    "cluster_analysis":           (["burnout_total", "satisfaction_total", "stress_score", "performance_score"], {}),
    "sem":                        (["burnout_1", "burnout_2", "burnout_3", "satisfaction_1", "satisfaction_2", "satisfaction_3"], {}),
    "path_analysis":              (["workload_score", "burnout_total", "satisfaction_total", "performance_score"], {}),

    # ── SURVIVAL ───────────────────────────────────────────────────────────────
    "kaplan_meier":               (["time_to_promotion", "promotion_event"], {}),
    "survival_analysis":          (["time_to_promotion", "promotion_event"], {}),
    "log_rank_test":              (["time_to_promotion", "promotion_event", "gender"], {}),
    "cox_ph_regression":          (["time_to_promotion", "promotion_event", "performance_score", "age", "burnout_total"], {}),
    "cox_regression":             (["time_to_promotion", "promotion_event", "performance_score", "tenure_years"], {}),
    "weibull_aft":                (["time_to_promotion", "promotion_event", "performance_score"], {}),
    "nelson_aalen":               (["time_to_promotion", "promotion_event"], {}),
    "life_table":                 (["time_to_promotion", "promotion_event"], {}),
    "ph_assumption_test":         (["time_to_promotion", "promotion_event", "performance_score"], {}),
    "competing_risks":            (["time_to_promotion", "promotion_event", "gender"], {}),

    # ── CAUSAL INFERENCE ───────────────────────────────────────────────────────
    "difference_in_differences":  (["received_training", "observation_month", "performance_score"], {}),
    "instrumental_variables":     (["autonomy_score", "workload_score", "performance_score"], {}),
    "propensity_score_matching":  (["received_training", "age", "tenure_years", "burnout_total", "performance_score"], {}),
    "regression_discontinuity":   (["tenure_years", "performance_score", "promoted"], {}),
    # bayesian_ab_test requires exactly 2 groups — use is_manager (0/1)
    "bayesian_ab_test":           (["is_manager", "performance_score"], {}),
    "interrupted_time_series":    (["received_training", "observation_month", "performance_score"], {}),
    # synthetic_control: outcome, time_col, unit_col + treatment_unit in brief
    "synthetic_control":          (["performance_score", "observation_month", "department"], {"treatment_unit": "Engineering"}),

    # ── TIME SERIES ────────────────────────────────────────────────────────────
    "autocorrelation":            (["kpi_score"], {}),
    "partial_autocorrelation":    (["kpi_score"], {}),
    "ljung_box":                  (["kpi_score"], {}),
    "seasonal_decompose":         (["kpi_score"], {}),
    "arima_model":                (["kpi_score"], {}),
    "time_series":                (["kpi_score"], {}),
    "sarima_model":               (["kpi_score"], {}),
    "exponential_smoothing":      (["kpi_score"], {}),
    "granger_causality":          (["kpi_score", "stress_score"], {}),
    "var_model":                  (["kpi_score", "performance_score", "stress_score"], {}),
    "mann_kendall":               (["kpi_score"], {}),

    # ── MULTILEVEL ─────────────────────────────────────────────────────────────
    # LMM: outcome=performance_score, group=team, predictors=satisfaction_total,workload_score
    "linear_mixed_model":         (["performance_score", "team", "satisfaction_total", "workload_score"], {}),
    "linear_mixed_effects":       (["wellbeing_index", "department", "burnout_total", "age"], {}),
    # GLMM: binary outcome=turnover_intent, group=department, predictors
    "glmm":                       (["turnover_intent", "department", "burnout_total", "satisfaction_total"], {}),
    # ICC: rater columns (all numeric)
    "icc":                        (["burnout_1", "burnout_2", "burnout_3", "burnout_4", "burnout_5"], {}),
    "random_effects_anova":       (["department", "performance_score"], {}),
    # cross_classified: outcome, group1, group2, predictor
    "cross_classified_mlm":       (["performance_score", "team", "department", "workload_score"], {}),
    # growth_curve: outcome, subject_col, time_col
    "growth_curve_model":         (["performance_score", "team", "observation_month"], {}),
    # multilevel_mediation: IV, mediator, DV, group
    "multilevel_mediation":       (["workload_score", "burnout_total", "performance_score", "team"], {}),
    # GEE: binary outcome, group, predictors
    "gee":                        (["turnover_intent", "department", "burnout_total", "age"], {}),
}


# ═══════════════════════════════════════════════════════════════════════════════
# RUN ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_test(fn_key, fn_callable, variables, brief_overrides):
    """Run one test; return (status, duration_ms, result_or_error)."""
    brief = {**BRIEF, **brief_overrides}
    t0 = time.perf_counter()
    try:
        result = fn_callable(df=df, variables=variables, brief=brief, alpha=ALPHA)
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        if result is None:
            return "NULL", elapsed, "Function returned None"
        if result.get("error"):
            return "SOFT_FAIL", elapsed, result.get("reason", "Unknown error")
        # Required fields check
        missing = [f for f in ("test_name", "statistic", "conclusion") if f not in result]
        if missing:
            return "MISSING_FIELD", elapsed, f"Missing: {missing}"
        return "PASS", elapsed, result
    except Exception:
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        return "ERROR", elapsed, traceback.format_exc()


def main():
    print("\n" + "═" * 78)
    print("  RESEARCHFORM — FULL ANALYSIS TEST RUNNER")
    print("  Dataset: Employee Wellbeing & Performance Survey (n=350)")
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 78)

    results = []
    counters = {"PASS": 0, "SOFT_FAIL": 0, "ERROR": 0, "NULL": 0, "MISSING_FIELD": 0, "NOT_IN_REGISTRY": 0}
    total = len(TEST_PLAN)

    for i, (fn_key, (variables, brief_overrides)) in enumerate(TEST_PLAN.items(), 1):
        if fn_key not in REGISTRY:
            status, elapsed, detail = "NOT_IN_REGISTRY", 0, f"'{fn_key}' not in registry"
            counters["NOT_IN_REGISTRY"] += 1
        else:
            entry = REGISTRY[fn_key]
            fn_callable = entry["fn"]
            status, elapsed, detail = run_test(fn_key, fn_callable, variables, brief_overrides)
            counters[status] += 1

        # Status icon
        icons = {"PASS": "✓", "SOFT_FAIL": "⚡", "ERROR": "✗", "NULL": "○",
                 "MISSING_FIELD": "⚠", "NOT_IN_REGISTRY": "—"}
        icon = icons.get(status, "?")

        # Short error msg
        err_msg = ""
        if status != "PASS":
            msg = str(detail) if isinstance(detail, str) else ""
            err_msg = " → " + msg[:90].replace("\n", " ")

        print(f"  [{i:3d}/{total}] {icon}  {fn_key:<40}  {status:<14}  {elapsed:>6.0f}ms{err_msg}")

        if VERBOSE and status == "PASS" and isinstance(detail, dict):
            pretty = json.dumps({k: v for k, v in detail.items()
                                 if k in ("statistic", "p_value", "conclusion",
                                          "effect_size_value", "ci_lower", "ci_upper")},
                                 indent=6, default=str)
            for line in pretty.split("\n"):
                print(f"         {line}")

        results.append({
            "test_function":   fn_key,
            "variables":       "|".join(variables),
            "status":          status,
            "elapsed_ms":      elapsed,
            "statistic":       detail.get("statistic") if isinstance(detail, dict) else None,
            "p_value":         detail.get("p_value") if isinstance(detail, dict) else None,
            "conclusion":      str(detail.get("conclusion", ""))[:200] if isinstance(detail, dict) else str(detail)[:200],
            "error":           str(detail)[:300] if status not in ("PASS",) else "",
        })

    # ── Summary ───────────────────────────────────────────────────────────────
    passed  = counters["PASS"]
    soft    = counters["SOFT_FAIL"]
    errors  = counters["ERROR"]
    nulls   = counters["NULL"]
    missing = counters["MISSING_FIELD"]
    not_reg = counters["NOT_IN_REGISTRY"]
    denom   = total - not_reg
    pass_rate = round(passed / denom * 100, 1) if denom > 0 else 0

    print("\n" + "═" * 78)
    print("  FULL ANALYSIS TEST SUMMARY")
    print("═" * 78)
    print(f"  ✓ PASS           : {passed}")
    print(f"  ⚡ SOFT_FAIL      : {soft}  (returned error dict — check variable mapping)")
    print(f"  ✗ ERROR          : {errors}  (exception thrown)")
    print(f"  ○ NULL           : {nulls}  (returned None)")
    print(f"  ⚠ MISSING_FIELD  : {missing}  (incomplete result schema)")
    print(f"  — NOT_IN_REGISTRY: {not_reg}  (not registered)")
    print(f"\n  Overall pass rate : {pass_rate}%  ({passed}/{denom})")
    print("═" * 78)

    if soft > 0 or errors > 0:
        print(f"\n  FAILED TESTS:")
        for r in results:
            if r["status"] not in ("PASS", "NOT_IN_REGISTRY"):
                print(f"    • [{r['status']}] {r['test_function']}: {r['error'][:100]}")

    # ── Save reports ─────────────────────────────────────────────────────────
    df_results = pd.DataFrame(results)
    csv_path = Path(__file__).parent / "full_analysis_summary.csv"
    df_results.to_csv(csv_path, index=False)

    # Detailed text report
    report_lines = [
        "RESEARCHFORM — FULL ANALYSIS TEST REPORT",
        f"Dataset: Employee Wellbeing & Performance Survey (n=350)",
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Pass Rate: {pass_rate}%  ({passed}/{denom})",
        "=" * 78,
        "",
    ]
    for r in results:
        report_lines.append(
            f"[{r['status']:<14}] {r['test_function']:<40}  {r['elapsed_ms']:>6.0f}ms"
        )
        if r["status"] == "PASS":
            report_lines.append(
                f"  Variables: {r['variables']}"
            )
            if r["p_value"] is not None:
                report_lines.append(f"  p = {r['p_value']}")
            report_lines.append(f"  {r['conclusion'][:150]}")
        else:
            report_lines.append(f"  Variables: {r['variables']}")
            report_lines.append(f"  Error: {r['error'][:200]}")
        report_lines.append("")

    txt_path = Path(__file__).parent / "full_analysis_report.txt"
    txt_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"\n  Reports saved:")
    print(f"    {csv_path}")
    print(f"    {txt_path}")
    print()

    return pass_rate


if __name__ == "__main__":
    rate = main()
    sys.exit(0 if rate >= 90 else 1)
