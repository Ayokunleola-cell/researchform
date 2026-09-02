# backend/analysis/engine/registry.py
"""
TEST_REGISTRY — The single source of truth for every statistical test.
Maps test_function names (strings from LLM/frontend) to pre-built Python functions.

Adding a new test: register it here. Nothing else changes.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# Lazy imports — loaded on first access to avoid circular imports and speed up startup
_REGISTRY: dict | None = None


def _build_registry() -> dict:
    """
    Build the full registry. Called once on first get_registry() call.
    Each entry: {"fn": callable, "family": str, "min_n": int, "phase": int,
                 "assumptions": list, "fallback": str|None}
    """
    from analysis.engine.tests import (
        descriptive, normality, reliability, outliers,
        parametric, nonparametric, correlation, regression,
        posthoc, advanced, survival, causal, timeseries, multilevel,
        power_analysis, missing_data,
    )

    return {

        # ══════════════════════════════════════════════════════════════════════
        # TIER 1 — DESCRIPTIVE & FREQUENCY
        # ══════════════════════════════════════════════════════════════════════
        "descriptive_stats":          {"fn": descriptive.run_descriptive_stats,        "family": "descriptive",  "min_n": 1,   "phase": 1, "assumptions": [], "fallback": None},
        "frequency_analysis":         {"fn": descriptive.run_frequency_analysis,       "family": "frequencies", "min_n": 1,   "phase": 1, "assumptions": [], "fallback": None},
        "mean_median_mode":           {"fn": descriptive.run_mean_median_mode,         "family": "descriptive",  "min_n": 1,   "phase": 1, "assumptions": [], "fallback": None},
        "dispersion_extended":        {"fn": descriptive.run_dispersion_extended,      "family": "descriptive",  "min_n": 1,   "phase": 1, "assumptions": [], "fallback": None},
        "percentiles_extended":       {"fn": descriptive.run_percentiles_extended,     "family": "descriptive",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "z_scores":                   {"fn": descriptive.run_z_scores,                 "family": "descriptive",  "min_n": 3,   "phase": 1, "assumptions": [], "fallback": None},
        "skewness_analysis":          {"fn": descriptive.run_skewness_analysis,        "family": "descriptive",  "min_n": 3,   "phase": 1, "assumptions": [], "fallback": None},
        "kurtosis_analysis":          {"fn": descriptive.run_kurtosis_analysis,        "family": "descriptive",  "min_n": 3,   "phase": 1, "assumptions": [], "fallback": None},
        "variable_transformation":    {"fn": descriptive.run_variable_transformation,  "family": "descriptive",  "min_n": 3,   "phase": 1, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # TIER 1 — NORMALITY TESTS
        # ══════════════════════════════════════════════════════════════════════
        "normality_check":            {"fn": normality.run_normality_check,            "family": "normality",   "min_n": 3,   "phase": 1, "assumptions": [], "fallback": None},
        "shapiro_wilk_all":           {"fn": normality.run_shapiro_wilk_all,           "family": "normality",   "min_n": 3,   "phase": 1, "assumptions": [], "fallback": None},
        "shapiro_wilk":               {"fn": normality.run_normality_check,            "family": "normality",   "min_n": 3,   "phase": 1, "assumptions": [], "fallback": None},
        "kolmogorov_smirnov":         {"fn": normality.run_ks_test,                    "family": "normality",   "min_n": 10,  "phase": 1, "assumptions": [], "fallback": None},
        "anderson_darling":           {"fn": normality.run_anderson_darling,           "family": "normality",   "min_n": 3,   "phase": 1, "assumptions": [], "fallback": None},
        "jarque_bera":                {"fn": normality.run_jarque_bera,                "family": "normality",   "min_n": 3,   "phase": 1, "assumptions": [], "fallback": None},
        "dagostino_pearson":          {"fn": normality.run_dagostino_pearson,          "family": "normality",   "min_n": 8,   "phase": 1, "assumptions": [], "fallback": None},
        "dagostino_k2":               {"fn": normality.run_dagostino_pearson,          "family": "normality",   "min_n": 8,   "phase": 1, "assumptions": [], "fallback": None},
        "omnibus_normality":          {"fn": normality.run_omnibus_normality,          "family": "normality",   "min_n": 3,   "phase": 1, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # TIER 1 — RELIABILITY
        # ══════════════════════════════════════════════════════════════════════
        "cronbach_alpha":             {"fn": reliability.run_cronbach_alpha,           "family": "reliability",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "mcdonald_omega":             {"fn": reliability.run_mcdonald_omega,           "family": "reliability",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "split_half_reliability":     {"fn": reliability.run_split_half,               "family": "reliability",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "item_analysis":              {"fn": reliability.run_item_analysis,            "family": "reliability",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "icc_reliability":            {"fn": reliability.run_icc,                      "family": "reliability",  "min_n": 10,  "phase": 1, "assumptions": [], "fallback": None},
        "kr20":                       {"fn": reliability.run_kr20,                     "family": "reliability",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # TIER 1/2 — ASSUMPTION CHECKS & OUTLIERS
        # ══════════════════════════════════════════════════════════════════════
        "levene_test":                {"fn": outliers.run_levene_test,                 "family": "assumption",   "min_n": 6,   "phase": 1, "assumptions": [], "fallback": None},
        "bartlett_test":              {"fn": outliers.run_bartlett_test,               "family": "assumption",   "min_n": 6,   "phase": 1, "assumptions": [], "fallback": None},
        "mauchly_test":               {"fn": outliers.run_mauchly_test,                "family": "assumption",   "min_n": 6,   "phase": 1, "assumptions": [], "fallback": None},
        "durbin_watson":              {"fn": regression.run_durbin_watson,             "family": "assumption",   "min_n": 10,  "phase": 1, "assumptions": [], "fallback": None},
        "vif_check":                  {"fn": regression.run_vif_check,                 "family": "assumption",   "min_n": 10,  "phase": 1, "assumptions": [], "fallback": None},
        "outliers_iqr":               {"fn": outliers.run_iqr_outliers,                "family": "descriptive",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "outliers_zscore":            {"fn": outliers.run_zscore_outliers,             "family": "descriptive",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "outliers_grubbs":            {"fn": outliers.run_grubbs_test,                 "family": "descriptive",  "min_n": 5,   "phase": 1, "assumptions": ["normality"], "fallback": None},
        "mahalanobis_distance":       {"fn": outliers.run_mahalanobis,                 "family": "multivariate", "min_n": 10,  "phase": 1, "assumptions": [], "fallback": None},
        "cooks_distance":             {"fn": outliers.run_cooks_distance,              "family": "regression",   "min_n": 10,  "phase": 1, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # TIER 3 — PARAMETRIC COMPARISON
        # ══════════════════════════════════════════════════════════════════════
        "one_sample_t_test":          {"fn": parametric.run_one_sample_t,              "family": "comparison",   "min_n": 5,   "phase": 1, "assumptions": ["normality"], "fallback": "wilcoxon"},
        "one_sample_t_cohend":        {"fn": parametric.run_one_sample_t_cohend,       "family": "comparison",   "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "independent_t_test":         {"fn": parametric.run_independent_t,             "family": "comparison",   "min_n": 6,   "phase": 1, "assumptions": ["normality", "equal_variance"], "fallback": "mann_whitney"},
        "independent_t_cohend":       {"fn": parametric.run_cohens_d_independent,      "family": "comparison",   "min_n": 6,   "phase": 1, "assumptions": [], "fallback": None},
        "welch_t_test":               {"fn": parametric.run_welch_t,                   "family": "comparison",   "min_n": 6,   "phase": 1, "assumptions": ["normality"], "fallback": "mann_whitney"},
        "paired_t_test":              {"fn": parametric.run_paired_t,                  "family": "comparison",   "min_n": 5,   "phase": 1, "assumptions": ["normality"], "fallback": "wilcoxon"},
        "paired_t_cohend":            {"fn": parametric.run_cohens_d_paired,           "family": "comparison",   "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "one_way_anova":              {"fn": parametric.run_one_way_anova,             "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": ["normality", "equal_variance"], "fallback": "kruskal_wallis"},
        "anova_eta_squared":          {"fn": parametric.run_eta_squared,               "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},
        "anova_descriptives":         {"fn": parametric.run_one_way_anova,             "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},
        "planned_contrasts":          {"fn": parametric.run_planned_contrasts,         "family": "comparison",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "welch_anova":                {"fn": parametric.run_welch_anova,               "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": ["normality"], "fallback": "kruskal_wallis"},
        "two_way_anova":              {"fn": parametric.run_two_way_anova,             "family": "comparison",   "min_n": 12,  "phase": 1, "assumptions": ["normality"], "fallback": None},
        "two_way_eta_squared":        {"fn": parametric.run_two_way_eta_squared,       "family": "comparison",   "min_n": 12,  "phase": 1, "assumptions": [], "fallback": None},
        "two_way_pairwise":           {"fn": parametric.run_two_way_anova,             "family": "comparison",   "min_n": 12,  "phase": 1, "assumptions": [], "fallback": None},
        "repeated_anova":             {"fn": parametric.run_repeated_anova,            "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": ["sphericity"], "fallback": "friedman_test"},
        "ancova":                     {"fn": parametric.run_ancova,                    "family": "comparison",   "min_n": 15,  "phase": 1, "assumptions": ["normality", "equal_variance"], "fallback": None},
        "manova":                     {"fn": parametric.run_manova,                    "family": "comparison",   "min_n": 20,  "phase": 2, "assumptions": ["normality"], "fallback": None},
        "manova_followup":            {"fn": parametric.run_manova,                    "family": "comparison",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # TIER 3 — NON-PARAMETRIC
        # ══════════════════════════════════════════════════════════════════════
        "mann_whitney":               {"fn": nonparametric.run_mann_whitney,           "family": "comparison",   "min_n": 6,   "phase": 1, "assumptions": [], "fallback": None},
        "mann_whitney_r":             {"fn": nonparametric.run_mann_whitney_r,         "family": "comparison",   "min_n": 6,   "phase": 1, "assumptions": [], "fallback": None},
        "mann_whitney_ci":            {"fn": nonparametric.run_mann_whitney,           "family": "comparison",   "min_n": 6,   "phase": 1, "assumptions": [], "fallback": None},
        "wilcoxon":                   {"fn": nonparametric.run_wilcoxon,               "family": "comparison",   "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "wilcoxon_r":                 {"fn": nonparametric.run_wilcoxon_r,             "family": "comparison",   "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "kruskal_wallis":             {"fn": nonparametric.run_kruskal_wallis,         "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},
        "kruskal_wallis_eta2":        {"fn": nonparametric.run_kruskal_eta2,           "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},
        "friedman_test":              {"fn": nonparametric.run_friedman,               "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},
        "kendall_w":                  {"fn": nonparametric.run_kendall_w,              "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},
        "mcnemar":                    {"fn": nonparametric.run_mcnemar,                "family": "comparison",   "min_n": 10,  "phase": 1, "assumptions": [], "fallback": None},
        "chi_square":                 {"fn": nonparametric.run_chi_square,                     "family": "comparison",   "min_n": 5,   "phase": 1, "assumptions": ["expected_freq"], "fallback": "fisher_exact"},
        "chi_square_extended":        {"fn": nonparametric.run_chi_square_extended,            "family": "comparison",   "min_n": 5,   "phase": 1, "assumptions": ["expected_freq"], "fallback": "fisher_exact"},
        "chi_square_goodness_of_fit": {"fn": nonparametric.run_chi_square_goodness_of_fit,    "family": "comparison",   "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "fisher_exact":               {"fn": nonparametric.run_fisher_exact,           "family": "comparison",   "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "sign_test":                  {"fn": nonparametric.run_sign_test,              "family": "comparison",   "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "runs_test":                  {"fn": nonparametric.run_runs_test,              "family": "assumption",   "min_n": 10,  "phase": 1, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # TIER 4 — POST-HOC
        # ══════════════════════════════════════════════════════════════════════
        "tukey_hsd":                  {"fn": posthoc.run_tukey_hsd,                    "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},
        "bonferroni_test":            {"fn": posthoc.run_bonferroni,                   "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},
        "dunn_test":                  {"fn": posthoc.run_dunn,                         "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},
        "scheffe_test":               {"fn": posthoc.run_scheffe,                      "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},
        "newman_keuls":               {"fn": posthoc.run_newman_keuls,                 "family": "comparison",   "min_n": 9,   "phase": 2, "assumptions": [], "fallback": None},
        "fisher_lsd":                 {"fn": posthoc.run_fisher_lsd,                   "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},
        "dunnett_test":               {"fn": posthoc.run_tukey_hsd,                    "family": "comparison",   "min_n": 9,   "phase": 1, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # TIER 3 — CORRELATION
        # ══════════════════════════════════════════════════════════════════════
        "pearson_correlation":        {"fn": correlation.run_pearson,                  "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": ["normality"], "fallback": "spearman_correlation"},
        "pearson_ci":                 {"fn": correlation.run_pearson,                  "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "spearman_correlation":       {"fn": correlation.run_spearman,                 "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "kendall_tau":                {"fn": correlation.run_kendall_tau,              "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "point_biserial":             {"fn": correlation.run_point_biserial,           "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "phi_coefficient":            {"fn": correlation.run_phi,                      "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "cramers_v":                  {"fn": correlation.run_cramers_v,                "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "partial_correlation":        {"fn": correlation.run_partial_correlation,      "family": "correlation",  "min_n": 10,  "phase": 1, "assumptions": [], "fallback": None},
        "canonical_correlation":      {"fn": correlation.run_canonical_correlation,    "family": "correlation",  "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "correlation_matrix":         {"fn": correlation.run_correlation_matrix,       "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "correlation_heatmap":        {"fn": correlation.run_correlation_matrix,       "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "correlation_significance":   {"fn": correlation.run_correlation_significance, "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "correlation_effect_sizes":   {"fn": correlation.run_correlation_significance, "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},
        "correlation_splom":          {"fn": correlation.run_correlation_matrix,       "family": "correlation",  "min_n": 5,   "phase": 1, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # TIER 3 — REGRESSION
        # ══════════════════════════════════════════════════════════════════════
        "simple_linear_regression":   {"fn": regression.run_simple_linear,            "family": "regression",   "min_n": 10,  "phase": 1, "assumptions": ["normality"], "fallback": None},
        "linear_regression":          {"fn": regression.run_simple_linear,            "family": "regression",   "min_n": 10,  "phase": 1, "assumptions": [], "fallback": None},
        "multiple_regression":        {"fn": regression.run_multiple_regression,      "family": "regression",   "min_n": 20,  "phase": 1, "assumptions": ["normality", "vif"], "fallback": None},
        "logistic_regression":        {"fn": regression.run_logistic_regression,      "family": "regression",   "min_n": 20,  "phase": 1, "assumptions": [], "fallback": None},
        "ordinal_regression":         {"fn": regression.run_ordinal_regression,       "family": "regression",   "min_n": 20,  "phase": 1, "assumptions": [], "fallback": None},
        "multinomial_logistic":       {"fn": regression.run_multinomial_logistic,     "family": "regression",   "min_n": 30,  "phase": 1, "assumptions": [], "fallback": None},
        "hierarchical_regression":    {"fn": regression.run_hierarchical_regression,  "family": "regression",   "min_n": 30,  "phase": 1, "assumptions": ["normality", "vif"], "fallback": None},
        "stepwise_regression":        {"fn": regression.run_stepwise_regression,      "family": "regression",   "min_n": 30,  "phase": 1, "assumptions": ["normality"], "fallback": None},
        "mediation_analysis":         {"fn": regression.run_mediation_analysis,       "family": "regression",   "min_n": 30,  "phase": 2, "assumptions": [], "fallback": None},
        "moderation_analysis":        {"fn": regression.run_moderation_analysis,      "family": "regression",   "min_n": 30,  "phase": 2, "assumptions": [], "fallback": None},
        "moderated_mediation":        {"fn": regression.run_moderated_mediation,      "family": "regression",   "min_n": 40,  "phase": 2, "assumptions": [], "fallback": None},
        "quantile_regression":        {"fn": regression.run_quantile_regression,      "family": "regression",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "poisson_regression":         {"fn": regression.run_poisson_regression,       "family": "regression",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "negative_binomial":          {"fn": regression.run_negative_binomial,        "family": "regression",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # TIER 5 — ADVANCED MULTIVARIATE
        # ══════════════════════════════════════════════════════════════════════
        "pca":                        {"fn": advanced.run_pca,                         "family": "multivariate", "min_n": 50,  "phase": 2, "assumptions": [], "fallback": None},
        "factor_analysis":            {"fn": advanced.run_efa,                         "family": "multivariate", "min_n": 50,  "phase": 2, "assumptions": [], "fallback": None},
        "confirmatory_fa":            {"fn": advanced.run_cfa,                         "family": "multivariate", "min_n": 100, "phase": 3, "assumptions": [], "fallback": None},
        "discriminant_analysis":      {"fn": advanced.run_discriminant_analysis,       "family": "multivariate", "min_n": 30,  "phase": 2, "assumptions": ["normality"], "fallback": None},
        "cluster_analysis":           {"fn": advanced.run_cluster_analysis,            "family": "multivariate", "min_n": 30,  "phase": 2, "assumptions": [], "fallback": None},
        "sem":                        {"fn": advanced.run_sem,                         "family": "multivariate", "min_n": 100, "phase": 3, "assumptions": [], "fallback": None},
        "path_analysis":              {"fn": advanced.run_path_analysis,               "family": "multivariate", "min_n": 50,  "phase": 3, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # SURVIVAL ANALYSIS
        # ══════════════════════════════════════════════════════════════════════
        "kaplan_meier":               {"fn": survival.run_kaplan_meier,                "family": "survival",     "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "survival_analysis":          {"fn": survival.run_kaplan_meier,                "family": "survival",     "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "log_rank_test":              {"fn": survival.run_log_rank_test,               "family": "survival",     "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "cox_ph_regression":          {"fn": survival.run_cox_ph,                      "family": "survival",     "min_n": 30,  "phase": 2, "assumptions": [], "fallback": None},
        "cox_regression":             {"fn": survival.run_cox_ph,                      "family": "survival",     "min_n": 30,  "phase": 2, "assumptions": [], "fallback": None},
        "weibull_aft":                {"fn": survival.run_weibull_aft,                 "family": "survival",     "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "nelson_aalen":               {"fn": survival.run_nelson_aalen,               "family": "survival",     "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "life_table":                 {"fn": survival.run_life_table,                  "family": "survival",     "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "ph_assumption_test":         {"fn": survival.run_ph_assumption,               "family": "survival",     "min_n": 30,  "phase": 2, "assumptions": [], "fallback": None},
        "competing_risks":            {"fn": survival.run_competing_risks,             "family": "survival",     "min_n": 30,  "phase": 3, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # CAUSAL INFERENCE
        # ══════════════════════════════════════════════════════════════════════
        "difference_in_differences":  {"fn": causal.run_difference_in_differences,    "family": "causal",       "min_n": 30,  "phase": 3, "assumptions": [], "fallback": None},
        "instrumental_variables":     {"fn": causal.run_instrumental_variables,       "family": "causal",       "min_n": 30,  "phase": 3, "assumptions": [], "fallback": None},
        "propensity_score_matching":  {"fn": causal.run_propensity_score_matching,    "family": "causal",       "min_n": 50,  "phase": 3, "assumptions": [], "fallback": None},
        "regression_discontinuity":   {"fn": causal.run_rdd,                          "family": "causal",       "min_n": 50,  "phase": 3, "assumptions": [], "fallback": None},
        "bayesian_ab_test":           {"fn": causal.run_bayesian_ab,                  "family": "causal",       "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "synthetic_control":          {"fn": causal.run_synthetic_control,            "family": "causal",       "min_n": 30,  "phase": 3, "assumptions": [], "fallback": None},
        "sensitivity_analysis":       {"fn": causal.run_sensitivity_analysis,         "family": "causal",       "min_n": 10,  "phase": 3, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # TIME SERIES
        # ══════════════════════════════════════════════════════════════════════
        "adf_test":                   {"fn": timeseries.run_adf_test,                  "family": "timeseries",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "kpss_test":                  {"fn": timeseries.run_kpss_test,                 "family": "timeseries",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "autocorrelation":            {"fn": timeseries.run_autocorrelation,           "family": "timeseries",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "partial_autocorrelation":    {"fn": timeseries.run_partial_autocorrelation,   "family": "timeseries",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "ljung_box":                  {"fn": timeseries.run_ljung_box,                 "family": "timeseries",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "seasonal_decompose":         {"fn": timeseries.run_seasonal_decompose,        "family": "timeseries",   "min_n": 24,  "phase": 2, "assumptions": [], "fallback": None},
        "arima_model":                {"fn": timeseries.run_arima,                     "family": "timeseries",   "min_n": 30,  "phase": 2, "assumptions": [], "fallback": None},
        "time_series":                {"fn": timeseries.run_arima,                     "family": "timeseries",   "min_n": 30,  "phase": 2, "assumptions": [], "fallback": None},
        "sarima_model":               {"fn": timeseries.run_sarima,                    "family": "timeseries",   "min_n": 50,  "phase": 3, "assumptions": [], "fallback": None},
        "exponential_smoothing":      {"fn": timeseries.run_ets,                       "family": "timeseries",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "granger_causality":          {"fn": timeseries.run_granger_causality,         "family": "timeseries",   "min_n": 30,  "phase": 3, "assumptions": [], "fallback": None},
        "var_model":                  {"fn": timeseries.run_var_model,                 "family": "timeseries",   "min_n": 50,  "phase": 3, "assumptions": [], "fallback": None},
        "mann_kendall":               {"fn": timeseries.run_mann_kendall,              "family": "timeseries",   "min_n": 8,   "phase": 2, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # MULTILEVEL / MIXED-EFFECTS / LONGITUDINAL
        # ══════════════════════════════════════════════════════════════════════
        "linear_mixed_model":         {"fn": multilevel.run_lmm,                       "family": "multilevel",   "min_n": 30,  "phase": 2, "assumptions": [], "fallback": None},
        "linear_mixed_effects":       {"fn": multilevel.run_lmm,                       "family": "multilevel",   "min_n": 30,  "phase": 3, "assumptions": [], "fallback": None},
        "glmm":                       {"fn": multilevel.run_glmm,                      "family": "multilevel",   "min_n": 30,  "phase": 3, "assumptions": [], "fallback": None},
        "icc":                        {"fn": multilevel.run_icc,                        "family": "multilevel",   "min_n": 10,  "phase": 1, "assumptions": [], "fallback": None},
        "random_effects_anova":       {"fn": multilevel.run_random_effects_anova,      "family": "multilevel",   "min_n": 20,  "phase": 2, "assumptions": [], "fallback": None},
        "cross_classified_mlm":       {"fn": multilevel.run_cross_classified_mlm,      "family": "multilevel",   "min_n": 50,  "phase": 3, "assumptions": [], "fallback": None},
        "growth_curve_model":         {"fn": multilevel.run_growth_curve_model,        "family": "multilevel",   "min_n": 30,  "phase": 3, "assumptions": [], "fallback": None},
        "multilevel_mediation":       {"fn": multilevel.run_multilevel_mediation,      "family": "multilevel",   "min_n": 50,  "phase": 3, "assumptions": [], "fallback": None},
        "gee":                        {"fn": multilevel.run_glmm,                      "family": "multilevel",   "min_n": 30,  "phase": 3, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # POWER ANALYSIS
        # ══════════════════════════════════════════════════════════════════════
        "power_t_independent":        {"fn": power_analysis.run_power_t_independent,  "family": "power",        "min_n": 1,   "phase": 0, "assumptions": [], "fallback": None},
        "power_t_paired":             {"fn": power_analysis.run_power_t_paired,        "family": "power",        "min_n": 1,   "phase": 0, "assumptions": [], "fallback": None},
        "power_anova":                {"fn": power_analysis.run_power_anova,           "family": "power",        "min_n": 1,   "phase": 0, "assumptions": [], "fallback": None},
        "power_correlation":          {"fn": power_analysis.run_power_correlation,     "family": "power",        "min_n": 1,   "phase": 0, "assumptions": [], "fallback": None},
        "power_chi_square":           {"fn": power_analysis.run_power_chi_square,      "family": "power",        "min_n": 1,   "phase": 0, "assumptions": [], "fallback": None},
        "power_regression":           {"fn": power_analysis.run_power_regression,      "family": "power",        "min_n": 1,   "phase": 0, "assumptions": [], "fallback": None},
        "sample_size_calculator":     {"fn": power_analysis.run_sample_size_calculator,"family": "power",        "min_n": 1,   "phase": 0, "assumptions": [], "fallback": None},

        # ══════════════════════════════════════════════════════════════════════
        # MISSING DATA
        # ══════════════════════════════════════════════════════════════════════
        "missing_analysis":           {"fn": missing_data.run_missing_analysis,        "family": "missing",      "min_n": 1,   "phase": 0, "assumptions": [], "fallback": None},
        "mice_imputation":            {"fn": missing_data.run_mice_imputation,          "family": "missing",      "min_n": 5,   "phase": 0, "assumptions": [], "fallback": None},
    }


def get_registry() -> dict:
    """Thread-safe lazy registry loader."""
    global _REGISTRY
    if _REGISTRY is None:
        try:
            _REGISTRY = _build_registry()
            logger.info(f"[Registry] Loaded {len(_REGISTRY)} statistical tests.")
        except Exception as e:
            logger.error(f"[Registry] Failed to build: {e}", exc_info=True)
            _REGISTRY = {}
    return _REGISTRY


def lookup(test_function: str) -> dict | None:
    """Look up a test entry. Returns None if not registered."""
    return get_registry().get(test_function)


def list_all() -> list[str]:
    """Return all registered test_function names."""
    return sorted(get_registry().keys())


def count() -> int:
    return len(get_registry())
