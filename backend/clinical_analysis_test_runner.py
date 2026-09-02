#!/usr/bin/env python
"""
clinical_analysis_test_runner.py
=================================
Runs ALL 131 registered statistical tests against the
Clinical Patient Outcomes & Mental Health Study dataset (n=400).

Study: Multisite RCT — CBT+Pharmacotherapy vs Standard Care
       for Anxiety & Depression across 6 NHS Trusts

Run:
    python clinical_analysis_test_runner.py
    python clinical_analysis_test_runner.py --verbose
"""
import sys, time, traceback, json, warnings
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

DATASET_PATH = Path(__file__).parent / "clinical_dataset.csv"
if not DATASET_PATH.exists():
    print("ERROR: clinical_dataset.csv not found. Run generate_clinical_dataset.py first.")
    sys.exit(1)

df = pd.read_csv(DATASET_PATH)
print(f"Loaded: {df.shape[0]} rows × {df.shape[1]} columns")

BRIEF = {
    "topic": "Multisite RCT: CBT+Pharmacotherapy vs Standard Care for Anxiety & Depression",
    "research_question": "Does CBT+Pharmacotherapy produce superior remission rates vs standard care?",
    "significance_level": 0.05,
    "test_value": 10.0,       # null mean for one-sample (PHQ-9 baseline = 10 = moderate)
    "confidence_level": 0.95,
}
ALPHA = 0.05
VERBOSE = "--verbose" in sys.argv

try:
    from analysis.engine.registry import get_registry
    REGISTRY = get_registry()
    print(f"Registry: {len(REGISTRY)} tests")
except Exception as e:
    print(f"ERROR loading registry: {e}")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════════
# TEST PLAN — clinical variable mappings for all 131 tests
# ═══════════════════════════════════════════════════════════════════════════════
TEST_PLAN = {

    # ── DESCRIPTIVE ────────────────────────────────────────────────────────────
    "descriptive_stats":       (["age", "bmi", "phq9_total_pre", "gad7_total_pre", "cortisol_am", "bdnf_pg_ml"], {}),
    "frequency_analysis":      (["treatment_arm", "diagnosis", "sex", "ethnicity", "education"], {}),
    "mean_median_mode":        (["phq9_12mo", "gad7_12mo", "vitality_score"], {}),
    "dispersion_extended":     (["phq9_total_pre", "cortisol_am", "hospital_visits"], {}),
    "percentiles_extended":    (["phq9_total_pre", "gad7_total_pre", "days_to_remission"], {}),
    "z_scores":                (["phq9_total_pre", "cortisol_am", "bdnf_pg_ml"], {}),
    "skewness_analysis":       (["cortisol_am", "crp_mg_l", "hospital_visits"], {}),
    "kurtosis_analysis":       (["cortisol_am", "crp_mg_l", "days_to_remission"], {}),
    "variable_transformation": (["cortisol_am", "crp_mg_l", "hospital_visits"], {}),

    # ── NORMALITY ──────────────────────────────────────────────────────────────
    "normality_check":         (["phq9_12mo", "gad7_12mo", "cortisol_am", "bdnf_pg_ml"], {}),
    "shapiro_wilk_all":        (["phq9_baseline", "phq9_6wk", "phq9_6mo"], {}),
    "kolmogorov_smirnov":      (["cortisol_am", "bmi"], {}),
    "anderson_darling":        (["phq9_12mo", "gad7_12mo"], {}),
    "jarque_bera":             (["cortisol_am", "bdnf_pg_ml", "crp_mg_l"], {}),
    "dagostino_pearson":       (["phq9_total_pre", "gad7_total_pre"], {}),
    "omnibus_normality":       (["phq9_12mo", "gad7_12mo"], {}),

    # ── RELIABILITY ────────────────────────────────────────────────────────────
    "cronbach_alpha":          (["phq9_1","phq9_2","phq9_3","phq9_4","phq9_5","phq9_6","phq9_7","phq9_8","phq9_9"], {}),
    "mcdonald_omega":          (["gad7_1","gad7_2","gad7_3","gad7_4","gad7_5","gad7_6","gad7_7"], {}),
    "split_half_reliability":  (["phq9_1","phq9_2","phq9_3","phq9_4","phq9_5","phq9_6","phq9_7","phq9_8","phq9_9"], {}),
    "item_analysis":           (["phq9_1","phq9_2","phq9_3","phq9_4","phq9_5","phq9_6","phq9_7","phq9_8","phq9_9"], {}),
    "icc_reliability":         (["phq9_1","phq9_2","phq9_3","phq9_4","phq9_5"], {}),
    "kr20":                    (["sym_item1","sym_item2","sym_item3","sym_item4","sym_item5","sym_item6","sym_item7","sym_item8"], {}),

    # ── ASSUMPTION CHECKS ──────────────────────────────────────────────────────
    "levene_test":             (["treatment_arm", "phq9_12mo"], {}),
    "bartlett_test":           (["treatment_arm", "phq9_12mo"], {}),
    "mauchly_test":            (["phq9_baseline","phq9_6wk","phq9_6mo"], {}),
    "durbin_watson":           (["phq9_12mo","phq9_baseline","age"], {}),
    "vif_check":               (["phq9_total_pre","age","bmi","comorbidities"], {}),
    "outliers_iqr":            (["cortisol_am","crp_mg_l","hospital_visits"], {}),
    "outliers_zscore":         (["phq9_total_pre","cortisol_am","bdnf_pg_ml"], {}),
    "outliers_grubbs":         (["cortisol_am","bdnf_pg_ml"], {}),
    "mahalanobis_distance":    (["phq9_total_pre","gad7_total_pre","cortisol_am","bmi"], {}),
    "cooks_distance":          (["phq9_12mo","phq9_baseline","age"], {}),

    # ── PARAMETRIC ─────────────────────────────────────────────────────────────
    "one_sample_t_test":       (["phq9_total_pre"], {"test_value": 14.0}),
    "one_sample_t_cohend":     (["gad7_total_pre"], {"test_value": 10.0}),
    # treatment_arm is binary (2 groups) ✓
    "independent_t_test":      (["treatment_arm", "phq9_12mo"], {}),
    "independent_t_cohend":    (["treatment_arm", "gad7_12mo"], {}),
    "welch_t_test":            (["treatment_arm", "phq9_total_pre"], {}),
    # paired: baseline vs 6-week
    "paired_t_test":           (["phq9_baseline", "phq9_6wk"], {}),
    "paired_t_cohend":         (["gad7_baseline", "gad7_6wk"], {}),
    "one_way_anova":           (["diagnosis", "phq9_total_pre"], {}),
    "anova_eta_squared":       (["diagnosis", "gad7_total_pre"], {}),
    "anova_descriptives":      (["hospital", "phq9_12mo"], {}),
    "welch_anova":             (["hospital", "phq9_12mo"], {}),
    "two_way_anova":           (["treatment_arm", "sex", "phq9_12mo"], {}),
    "two_way_eta_squared":     (["treatment_arm", "sex", "gad7_12mo"], {}),
    "two_way_pairwise":        (["treatment_arm", "sex", "vitality_score"], {}),
    "repeated_anova":          (["phq9_baseline","phq9_6wk","phq9_6mo","phq9_12mo"], {}),
    "ancova":                  (["treatment_arm", "phq9_12mo", "phq9_baseline"], {}),
    "manova":                  (["treatment_arm","phq9_12mo","gad7_12mo","vitality_score"], {}),
    "manova_followup":         (["treatment_arm","phq9_12mo","gad7_12mo","vitality_score"], {}),

    # ── NON-PARAMETRIC ─────────────────────────────────────────────────────────
    # treatment_arm binary (2 groups) ✓
    "mann_whitney":            (["treatment_arm", "phq9_12mo"], {}),
    "mann_whitney_r":          (["treatment_arm", "days_to_remission"], {}),
    "mann_whitney_ci":         (["treatment_arm", "gad7_12mo"], {}),
    "wilcoxon":                (["phq9_baseline", "phq9_6wk"], {}),
    "wilcoxon_r":              (["gad7_baseline", "gad7_6wk"], {}),
    "kruskal_wallis":          (["diagnosis", "phq9_total_pre"], {}),
    "kruskal_wallis_eta2":     (["hospital", "phq9_12mo"], {}),
    "friedman_test":           (["phq9_baseline","phq9_6wk","phq9_6mo","phq9_12mo"], {}),
    "sign_test":               (["phq9_baseline", "phq9_6wk"], {}),
    "chi_square":              (["treatment_arm", "diagnosis"], {}),
    "chi_square_goodness":     (["diagnosis"], {}),
    # fisher_exact: both binary (0/1) — readmitted × adverse_event ✓
    "fisher_exact":            (["readmitted", "adverse_event"], {}),
    "mcnemar_test":            (["readmitted", "adverse_event"], {}),
    "binomial_test":           (["readmitted"], {}),
    "runs_test":               (["readmitted"], {}),

    # ── CORRELATION ────────────────────────────────────────────────────────────
    "pearson_correlation":     (["phq9_12mo", "mental_health_sf"], {}),
    "spearman_correlation":    (["phq9_total_pre", "hospital_visits"], {}),
    "kendall_tau":             (["gad7_total_pre", "days_to_remission"], {}),
    # remission is binary (0/1 numeric, ~40% rate) ✓
    "point_biserial":          (["readmitted", "phq9_12mo"], {}),
    "phi_coefficient":         (["readmitted", "adverse_event"], {}),
    "cramers_v":               (["treatment_arm", "diagnosis"], {}),
    "partial_correlation":     (["phq9_12mo", "mental_health_sf", "age"], {}),
    "canonical_correlation":   (["phq9_total_pre","gad7_total_pre","cortisol_am","mental_health_sf","vitality_score"], {}),
    "correlation_matrix":      (["phq9_12mo","gad7_12mo","mental_health_sf","vitality_score","bdnf_pg_ml"], {}),
    "correlation_heatmap":     (["phq9_12mo","gad7_12mo","mental_health_sf","vitality_score"], {}),
    "correlation_significance":(["phq9_12mo","gad7_12mo","mental_health_sf","vitality_score"], {}),
    "correlation_effect_sizes":(["phq9_12mo","cortisol_am","bdnf_pg_ml","mental_health_sf"], {}),
    "correlation_splom":       (["phq9_12mo","gad7_12mo","mental_health_sf","vitality_score"], {}),

    # ── REGRESSION ─────────────────────────────────────────────────────────────
    "simple_linear_regression":(["phq9_baseline", "phq9_12mo"], {}),
    "linear_regression":       (["phq9_baseline", "phq9_12mo"], {}),
    "multiple_regression":     (["phq9_12mo","phq9_baseline","age","comorbidities","bdnf_pg_ml"], {}),
    "logistic_regression":     (["remission","phq9_baseline","age","comorbidities","gad7_baseline"], {}),
    "ordinal_regression":      (["severity_grade","phq9_total_pre","age","bmi"], {}),
    "multinomial_logistic":    (["diagnosis","age","bmi","phq9_total_pre","gad7_total_pre"], {}),
    "hierarchical_regression": (["phq9_12mo","age","bmi","phq9_baseline","gad7_baseline","cortisol_am"], {}),
    "stepwise_regression":     (["phq9_12mo","phq9_baseline","gad7_baseline","age","cortisol_am","bdnf_pg_ml"], {}),
    "mediation_analysis":      (["phq9_baseline","bdnf_pg_ml","phq9_12mo"], {}),
    "moderation_analysis":     (["phq9_baseline","gad7_baseline","phq9_12mo"], {}),
    "quantile_regression":     (["days_to_remission","age","phq9_baseline"], {}),
    "poisson_regression":      (["hospital_visits","comorbidities","phq9_baseline","age"], {}),
    "negative_binomial":       (["hospital_visits","comorbidities","medications_count"], {}),

    # ── ADVANCED MULTIVARIATE ──────────────────────────────────────────────────
    "pca":                     (["phq9_total_pre","gad7_total_pre","cortisol_am","bdnf_pg_ml","crp_mg_l","mental_health_sf","vitality_score"], {}),
    "factor_analysis":         (["phq9_1","phq9_2","phq9_3","gad7_1","gad7_2","gad7_3","phq9_4","phq9_5"], {}),
    # CFA: auto-generates 1-factor model from 6 numeric PHQ items (semopy)
    "confirmatory_fa":         (["phq9_1","phq9_2","phq9_3","phq9_4","phq9_5","phq9_6"], {}),
    "discriminant_analysis":   (["treatment_arm","phq9_baseline","gad7_baseline","age","bmi","cortisol_am"], {}),
    "cluster_analysis":        (["phq9_total_pre","gad7_total_pre","cortisol_am","bdnf_pg_ml"], {}),
    # SEM: mediation chain phq9_baseline→bdnf_pg_ml→phq9_12mo
    "sem":                     (["phq9_baseline","bdnf_pg_ml","phq9_12mo"], {}),
    "path_analysis":           (["phq9_baseline","cortisol_am","bdnf_pg_ml","phq9_12mo"], {}),

    # ── SURVIVAL ───────────────────────────────────────────────────────────────
    "kaplan_meier":            (["days_to_remission","remission_event"], {}),
    "survival_analysis":       (["days_to_remission","remission_event"], {}),
    "log_rank_test":           (["days_to_remission","remission_event","treatment_arm"], {}),
    # Cox: avoid collinear predictors (phq9_baseline already captures phq9_total_pre)
    "cox_ph_regression":       (["days_to_remission","remission_event","phq9_baseline","age","bmi"], {}),
    "cox_regression":          (["days_to_remission","remission_event","gad7_baseline","bmi"], {}),
    "weibull_aft":             (["days_to_remission","remission_event","phq9_baseline"], {}),
    "nelson_aalen":            (["days_to_remission","remission_event"], {}),
    "life_table":              (["days_to_remission","remission_event"], {}),
    "ph_assumption_test":      (["days_to_remission","remission_event","gad7_baseline"], {}),
    "competing_risks":         (["days_to_remission","remission_event","sex"], {}),

    # ── CAUSAL INFERENCE ───────────────────────────────────────────────────────
    # DiD: treatment_numeric (0/1 int), study_month (time), phq9_12mo (outcome)
    "difference_in_differences":(["treatment_numeric","study_month","phq9_12mo"], {}),
    "instrumental_variables":  (["therapy_sessions","phq9_baseline","phq9_12mo"], {}),
    # propensity_score_matching: outcome=remission (now ~40%), covariates
    "propensity_score_matching":(["remission","age","bmi","phq9_baseline","comorbidities","gad7_baseline"], {}),
    "regression_discontinuity":(["phq9_baseline","phq9_12mo","remission"], {}),
    # treatment_arm is binary (2 groups) ✓
    "bayesian_ab_test":        (["treatment_arm","phq9_12mo"], {}),
    "interrupted_time_series": (["treatment_arm","study_month","phq9_12mo"], {}),
    # synthetic_control: treatment_unit = NHS_North (intervention hospital)
    "synthetic_control":       (["phq9_12mo","study_month","hospital"], {"treatment_unit": "NHS_North"}),

    # ── TIME SERIES ────────────────────────────────────────────────────────────
    "autocorrelation":         (["daily_steps"], {}),
    "partial_autocorrelation": (["daily_steps"], {}),
    "ljung_box":               (["daily_steps"], {}),
    "seasonal_decompose":      (["daily_steps"], {}),
    "arima_model":             (["daily_steps"], {}),
    "time_series":             (["daily_steps"], {}),
    "sarima_model":            (["daily_steps"], {}),
    "exponential_smoothing":   (["daily_steps"], {}),
    "granger_causality":       (["daily_steps","phq9_12mo"], {}),
    "var_model":               (["daily_steps","phq9_12mo","gad7_12mo"], {}),
    "mann_kendall":            (["daily_steps"], {}),

    # ── MULTILEVEL ─────────────────────────────────────────────────────────────
    # LMM: outcome, group, predictors
    "linear_mixed_model":      (["phq9_12mo","hospital","phq9_baseline","age"], {}),
    "linear_mixed_effects":    (["gad7_12mo","ward","gad7_baseline","comorbidities"], {}),
    # GLMM: binary outcome, group, predictors
    "glmm":                    (["remission","hospital","phq9_baseline","age"], {}),
    # ICC: 5 parallel rater columns (PHQ-9 items 1–5)
    "icc":                     (["phq9_1","phq9_2","phq9_3","phq9_4","phq9_5"], {}),
    "random_effects_anova":    (["hospital","phq9_12mo"], {}),
    # cross_classified: outcome, group1, group2, predictor
    "cross_classified_mlm":    (["phq9_12mo","hospital","ward","phq9_baseline"], {}),
    # growth_curve: outcome, subject, time
    "growth_curve_model":      (["phq9_12mo","hospital","study_month"], {}),
    # multilevel_mediation: IV, mediator, DV, group
    "multilevel_mediation":    (["phq9_baseline","bdnf_pg_ml","phq9_12mo","hospital"], {}),
    # GEE: binary outcome, group, predictors
    "gee":                     (["remission","ward","phq9_baseline","age"], {}),
}


def run_test(fn_key, fn_callable, variables, brief_overrides):
    brief = {**BRIEF, **brief_overrides}
    t0 = time.perf_counter()
    try:
        result = fn_callable(df=df, variables=variables, brief=brief, alpha=ALPHA)
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        if result is None:
            return "NULL", elapsed, "Returned None"
        if result.get("error"):
            return "SOFT_FAIL", elapsed, result.get("reason", "Unknown")
        missing = [f for f in ("test_name","statistic","conclusion") if f not in result]
        if missing:
            return "MISSING_FIELD", elapsed, f"Missing: {missing}"
        return "PASS", elapsed, result
    except Exception:
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        return "ERROR", elapsed, traceback.format_exc()


def main():
    print("\n" + "═"*76)
    print("  RESEARCHFORM — CLINICAL ANALYSIS FULL TEST RUNNER")
    print("  Dataset: Multisite RCT — CBT+Pharmacotherapy vs Standard Care (n=400)")
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═"*76)

    results = []
    counters = {"PASS":0,"SOFT_FAIL":0,"ERROR":0,"NULL":0,"MISSING_FIELD":0,"NOT_IN_REGISTRY":0}
    total = len(TEST_PLAN)
    icons = {"PASS":"✓","SOFT_FAIL":"⚡","ERROR":"✗","NULL":"○","MISSING_FIELD":"⚠","NOT_IN_REGISTRY":"—"}

    for i, (fn_key, (variables, brief_overrides)) in enumerate(TEST_PLAN.items(), 1):
        if fn_key not in REGISTRY:
            status, elapsed, detail = "NOT_IN_REGISTRY", 0, f"'{fn_key}' not in registry"
        else:
            fn_callable = REGISTRY[fn_key]["fn"]
            status, elapsed, detail = run_test(fn_key, fn_callable, variables, brief_overrides)
        counters[status] += 1
        err_msg = ""
        if status != "PASS":
            err_msg = " → " + str(detail)[:90].replace("\n"," ")
        print(f"  [{i:3d}/{total}] {icons.get(status,'?')}  {fn_key:<42}  {status:<14}  {elapsed:>6.0f}ms{err_msg}")

        if VERBOSE and status == "PASS" and isinstance(detail, dict):
            snippet = {k:v for k,v in detail.items()
                       if k in ("statistic","p_value","conclusion","effect_size_value")}
            for line in json.dumps(snippet, default=str, indent=4).split("\n"):
                print(f"       {line}")

        results.append({
            "test_function": fn_key,
            "variables":     "|".join(variables),
            "status":        status,
            "elapsed_ms":    elapsed,
            "statistic":     detail.get("statistic") if isinstance(detail,dict) else None,
            "p_value":       detail.get("p_value")   if isinstance(detail,dict) else None,
            "conclusion":    str(detail.get("conclusion",""))[:200] if isinstance(detail,dict) else str(detail)[:200],
            "error":         str(detail)[:300] if status != "PASS" else "",
        })

    passed   = counters["PASS"]
    soft     = counters["SOFT_FAIL"]
    errors   = counters["ERROR"]
    not_reg  = counters["NOT_IN_REGISTRY"]
    denom    = total - not_reg
    rate     = round(passed / denom * 100, 1) if denom else 0

    print("\n" + "═"*76)
    print("  CLINICAL ANALYSIS TEST SUMMARY")
    print("═"*76)
    print(f"  ✓ PASS           : {passed}")
    print(f"  ⚡ SOFT_FAIL      : {soft}")
    print(f"  ✗ ERROR          : {errors}")
    print(f"  ○ NULL           : {counters['NULL']}")
    print(f"  ⚠ MISSING_FIELD  : {counters['MISSING_FIELD']}")
    print(f"  — NOT_IN_REGISTRY: {not_reg}")
    print(f"\n  Overall pass rate : {rate}%  ({passed}/{denom})")
    print("═"*76)

    if soft or errors:
        print(f"\n  FAILED:")
        for r in results:
            if r["status"] not in ("PASS","NOT_IN_REGISTRY"):
                print(f"    • [{r['status']}] {r['test_function']}: {r['error'][:100]}")

    csv_path = Path(__file__).parent / "clinical_analysis_summary.csv"
    pd.DataFrame(results).to_csv(csv_path, index=False)
    print(f"\n  Results: {csv_path}")
    return rate

if __name__ == "__main__":
    rate = main()
    sys.exit(0 if rate >= 90 else 1)
