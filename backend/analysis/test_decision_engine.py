# backend/analysis/test_decision_engine.py
"""
Statistical Test Decision Engine — The Golden Rule Implementation.

Mandatory reasoning chain (never skip a step):
  Research Question
    → Outcome Variable        (What are we measuring?)
    → Predictor/Grouping Var  (What are we comparing or relating?)
    → Variable Type           (Continuous? Categorical? Ordinal? Binary?)
    → Study Design            (Independent? Paired? Repeated? Factorial?)
    → Number of Groups/Levels (2? 3+? 2×3 factorial?)
    → Assumptions             (Normality? Homogeneity? Independence?)
    → Statistical Test        (Determined — not guessed)
    → Effect Size             (Cohen\'s d / η² / r / Cramér\'s V — always)
    → Interpretation          (Evidence? Effect magnitude? RQ answer?)

Master Statistical Test Reference Table (source of truth):
  Describe categorical variable             → Frequency / %
  Describe continuous variable              → Mean/SD or Median/IQR
  Two categorical variables                 → Chi-square / Fisher\'s Exact
  Continuous outcome, 2 independent groups  → Independent t-test
  Continuous outcome, 2 paired measurements → Paired t-test
  Continuous outcome, 3+ independent groups → One-way ANOVA
  Ordinal/assumptions fail, 2 indep groups  → Mann–Whitney U
  Ordinal/assumptions fail, 3+ groups       → Kruskal–Wallis
  Ordinal/assumptions fail, paired          → Wilcoxon signed-rank
  Two numerical variables                   → Pearson correlation
  Rank/ordinal/monotonic association        → Spearman correlation
  One numerical predictor → numerical DV    → Simple linear regression
  Multiple predictors → numerical DV        → Multiple linear regression
  Binary outcome                            → Logistic regression
  Ordered categorical outcome               → Ordinal logistic regression
  Unordered 3+ category outcome             → Multinomial logistic regression
  Two factors + continuous outcome          → Factorial / Two-way ANOVA
  Group + repeated time points              → Mixed / Repeated-measures ANOVA
  Continuous outcome + covariate            → ANCOVA / Regression
  Hierarchical / clustered data             → Mixed / Multilevel models
  Count outcome                             → Poisson / Negative-binomial
  Time-to-event outcome                     → Survival analysis
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional
import logging

logger = logging.getLogger(__name__)

OutcomeType  = Literal["continuous", "categorical", "ordinal", "binary", "count", "time_to_event"]
PredictorType = Literal["categorical", "continuous", "none"]


@dataclass
class GroupingVariable:
    """A single factor / grouping variable in the study design."""
    name: str
    n_levels: int                        # number of categories/groups
    is_repeated: bool = False            # True if same subjects measured multiple times
    scale: str = "nominal"              # nominal | ordinal
    categories: list = field(default_factory=list)


@dataclass
class DecisionResult:
    """Full output of the decision engine for one research question."""
    research_question: str
    recommended_test:  str
    design_label:      str               # e.g. "2 × 3 Factorial Design"
    tests_to_run:      list              # internal test registry names
    report_fields:     list              # fields the report MUST include
    effect_size_metric: str              # Cohen\'s d / η² / r / Cramér\'s V
    posthoc:           Optional[str]
    nonparametric_fallback: Optional[str]
    reasoning:         list              # step-by-step reasoning chain
    interaction_to_check:    bool = False
    interaction_plot_required: bool = False
    warning:           Optional[str] = None


# ─── Predetermined report field schemas per test ──────────────────────────────
_REPORT_FIELDS = {
    "independent_ttest":       ["group_means", "group_sds", "mean_difference", "95_ci", "t_statistic", "df", "p_value", "cohens_d"],
    "paired_ttest":            ["mean_difference", "sd_of_differences", "95_ci", "t_statistic", "df", "p_value", "cohens_d"],
    "one_way_anova":           ["group_means", "F_statistic", "df_between", "df_within", "p_value", "eta_squared", "posthoc_table"],
    "two_way_anova":           ["F_main_A", "p_main_A", "F_main_B", "p_main_B", "F_interaction", "p_interaction",
                                "eta_sq_partial_A", "eta_sq_partial_B", "eta_sq_partial_interaction", "interaction_plot"],
    "mixed_anova":             ["F_between", "p_between", "F_within", "p_within", "F_interaction", "p_interaction", "eta_sq_partial"],
    "repeated_measures_anova": ["Mauchly_W", "F_statistic", "df", "p_value", "eta_squared", "posthoc_pairwise"],
    "chi_square":              ["observed_table", "expected_table", "chi2_statistic", "df", "p_value", "cramers_v"],
    "fishers_exact":           ["observed_table", "odds_ratio", "p_value"],
    "pearson_correlation":     ["r", "p_value", "95_ci", "effect_size_label"],
    "spearman_correlation":    ["rho", "p_value", "effect_size_label"],
    "linear_regression":       ["R_squared", "adj_R_squared", "F_statistic", "p_model",
                                "beta_coefficients", "standard_errors", "t_values",
                                "p_values_per_predictor", "95_ci_per_predictor"],
    "logistic_regression":     ["odds_ratios", "95_ci", "Wald_chi2", "p_values", "Nagelkerke_R2"],
    "mann_whitney_u":          ["U_statistic", "z_score", "p_value", "rank_biserial_r"],
    "wilcoxon_signed_rank":    ["W_statistic", "z_score", "p_value", "rank_biserial_r"],
    "kruskal_wallis":          ["H_statistic", "df", "p_value", "epsilon_squared"],
    "descriptive_categorical": ["frequencies", "percentages", "mode"],
    "descriptive_continuous":  ["mean", "sd", "median", "iqr", "min", "max", "skewness", "kurtosis"],
    "ancova":                  ["F_covariate", "F_group", "p_covariate", "p_group", "eta_sq_partial", "adjusted_means"],
}

_EFFECT_SIZE = {
    "independent_ttest":       "Cohen\'s d",
    "paired_ttest":            "Cohen\'s d",
    "one_way_anova":           "η² (eta-squared)",
    "two_way_anova":           "η² partial per effect",
    "mixed_anova":             "η² partial per effect",
    "repeated_measures_anova": "η² (eta-squared)",
    "chi_square":              "Cramér\'s V",
    "fishers_exact":           "Odds Ratio",
    "pearson_correlation":     "r (correlation coefficient)",
    "spearman_correlation":    "ρ (rho)",
    "linear_regression":       "R² (variance explained)",
    "logistic_regression":     "Nagelkerke R² / Odds Ratio",
    "mann_whitney_u":          "Rank-biserial r",
    "wilcoxon_signed_rank":    "Rank-biserial r",
    "kruskal_wallis":          "ε² (epsilon-squared)",
    "ancova":                  "η² partial",
}


def decide_test(
    research_question: str,
    outcome_type: OutcomeType,
    predictor_type: PredictorType,
    grouping_variables=None,
    has_covariate: bool = False,
    assume_normality: bool = True,
    n_predictors: int = 1,
) -> DecisionResult:
    """
    Main entry point. Walks through the Golden Rule chain and returns the
    recommended test with full reasoning, report fields, and effect size metric.
    """
    gvars = grouping_variables or []
    reasoning = [f"Research Question: {research_question}",
                 f"Outcome variable type: {outcome_type}",
                 f"Predictor type: {predictor_type}"]

    # ── Descriptive only (no predictor, no grouping) ──────────────────────
    if predictor_type == "none" and not gvars:
        if outcome_type == "categorical":
            reasoning.append("No predictor — descriptive summary only. Outcome is categorical.")
            return DecisionResult(
                research_question=research_question,
                recommended_test="Frequency Table / Percentage Distribution",
                design_label="Descriptive — Categorical",
                tests_to_run=["descriptive_categorical"],
                report_fields=_REPORT_FIELDS["descriptive_categorical"],
                effect_size_metric="N/A",
                posthoc=None, nonparametric_fallback=None, reasoning=reasoning,
            )
        reasoning.append("No predictor — descriptive summary only. Outcome is continuous/ordinal.")
        return DecisionResult(
            research_question=research_question,
            recommended_test="Mean / SD and Median / IQR",
            design_label="Descriptive — Continuous",
            tests_to_run=["descriptive_continuous"],
            report_fields=_REPORT_FIELDS["descriptive_continuous"],
            effect_size_metric="N/A",
            posthoc=None, nonparametric_fallback=None, reasoning=reasoning,
        )

    # ── Two categorical variables ─────────────────────────────────────────
    if outcome_type == "categorical" and predictor_type == "categorical":
        reasoning.append("Both outcome and predictor are categorical → association test.")
        # Fisher's Exact: only for true 2×2 tables (both variables have exactly 2 levels)
        # Chi-square: 3+ categories on either variable (larger tables)
        n_gvar_levels = gvars[0].n_levels if gvars else 2
        is_true_2x2 = (n_gvar_levels == 2)  # outcome binary assumed when outcome_type=categorical + single grouping var
        test = "fishers_exact" if is_true_2x2 else "chi_square"
        if is_true_2x2:
            reasoning.append("True 2x2 table: Fisher's Exact Test (exact probabilities, no large-sample approximation).")
        else:
            reasoning.append(f"Table has {n_gvar_levels} categories: Chi-square Test of Independence.")
        return DecisionResult(
            research_question=research_question,
            recommended_test="Chi-square Test of Independence" if test == "chi_square" else "Fisher's Exact Test",
            design_label="Two Categorical Variables",
            tests_to_run=[test],
            report_fields=_REPORT_FIELDS[test],
            effect_size_metric=_EFFECT_SIZE[test],
            posthoc=None, nonparametric_fallback="Fisher's Exact (if expected cells < 5)", reasoning=reasoning,
        )

    # ── Binary outcome → Logistic Regression ─────────────────────────────
    if outcome_type == "binary":
        reasoning.append("Outcome is binary (Yes/No, Pass/Fail) → Logistic Regression.")
        return DecisionResult(
            research_question=research_question,
            recommended_test="Binary Logistic Regression",
            design_label="Binary Outcome",
            tests_to_run=["logistic_regression"],
            report_fields=_REPORT_FIELDS["logistic_regression"],
            effect_size_metric=_EFFECT_SIZE["logistic_regression"],
            posthoc=None, nonparametric_fallback=None, reasoning=reasoning,
        )

    # ── Count outcome → Poisson ────────────────────────────────────────────
    if outcome_type == "count":
        reasoning.append("Outcome is a count variable → Poisson / Negative-Binomial Regression.")
        return DecisionResult(
            research_question=research_question,
            recommended_test="Poisson Regression (or Negative-Binomial if overdispersed)",
            design_label="Count Outcome",
            tests_to_run=["poisson_regression"],
            report_fields=["IRR", "95_ci", "p_value", "model_fit"],
            effect_size_metric="Incidence Rate Ratio (IRR)",
            posthoc=None, nonparametric_fallback=None, reasoning=reasoning,
        )

    # ── Correlation: two continuous variables, no groups ──────────────────
    if outcome_type in ("continuous", "ordinal") and predictor_type == "continuous" and not gvars:
        if outcome_type == "ordinal" or not assume_normality:
            reasoning.append("Ordinal or non-normal continuous variables → Spearman correlation.")
            return DecisionResult(
                research_question=research_question,
                recommended_test="Spearman Rank Correlation",
                design_label="Rank / Monotonic Association",
                tests_to_run=["spearman_correlation"],
                report_fields=_REPORT_FIELDS["spearman_correlation"],
                effect_size_metric=_EFFECT_SIZE["spearman_correlation"],
                posthoc=None, nonparametric_fallback=None, reasoning=reasoning,
            )
        reasoning.append("Two continuous variables, approximately normal → Pearson correlation.")
        return DecisionResult(
            research_question=research_question,
            recommended_test="Pearson Correlation",
            design_label="Two Numerical Variables",
            tests_to_run=["pearson_correlation"],
            report_fields=_REPORT_FIELDS["pearson_correlation"],
            effect_size_metric=_EFFECT_SIZE["pearson_correlation"],
            posthoc=None, nonparametric_fallback="Spearman Correlation", reasoning=reasoning,
        )

    # ── Multiple continuous predictors → Regression ───────────────────────
    if outcome_type == "continuous" and predictor_type == "continuous" and n_predictors > 1:
        reasoning.append(f"{n_predictors} continuous predictors → Multiple Linear Regression.")
        return DecisionResult(
            research_question=research_question,
            recommended_test="Multiple Linear Regression",
            design_label=f"Multiple Regression ({n_predictors} predictors)",
            tests_to_run=["linear_regression"],
            report_fields=_REPORT_FIELDS["linear_regression"],
            effect_size_metric=_EFFECT_SIZE["linear_regression"],
            posthoc=None, nonparametric_fallback=None, reasoning=reasoning,
        )

    # ── ANCOVA: continuous outcome + categorical grouping + covariate ──────
    if has_covariate and gvars and outcome_type == "continuous":
        reasoning.append("Grouping variable + covariate to control → ANCOVA.")
        return DecisionResult(
            research_question=research_question,
            recommended_test="ANCOVA (Analysis of Covariance)",
            design_label="Group Comparison Controlling for Covariate",
            tests_to_run=["ancova"],
            report_fields=_REPORT_FIELDS["ancova"],
            effect_size_metric=_EFFECT_SIZE["ancova"],
            posthoc="Pairwise comparisons with Bonferroni correction",
            nonparametric_fallback=None, reasoning=reasoning,
        )

    # ── GROUP COMPARISONS ─────────────────────────────────────────────────
    if predictor_type == "categorical" and gvars:
        n_factors = len(gvars)
        reasoning.append(f"Categorical predictor with {n_factors} grouping variable(s).")

        # TWO or more grouping variables → Factorial design
        if n_factors >= 2:
            levels = [gv.n_levels for gv in gvars]
            design_str = " × ".join(str(l) for l in levels)
            factor_names = " × ".join(gv.name for gv in gvars)
            has_repeated = any(gv.is_repeated for gv in gvars)
            reasoning.append(f"{design_str} factorial design detected ({factor_names}).")
            reasoning.append(
                "⚠ Running separate t-tests/ANOVAs would miss the interaction effect "
                "— a factorial model is required to examine main effects AND interaction."
            )
            reasoning.append(
                "Tests: (1) Main effect of each factor, (2) Interaction between factors."
            )
            if has_repeated:
                reasoning.append("One factor is repeated-measures → Mixed ANOVA (split-plot).")
                return DecisionResult(
                    research_question=research_question,
                    recommended_test="Mixed ANOVA (Split-Plot Design)",
                    design_label=f"{design_str} Mixed Design ({factor_names})",
                    tests_to_run=["mixed_anova"],
                    report_fields=_REPORT_FIELDS["mixed_anova"],
                    effect_size_metric=_EFFECT_SIZE["mixed_anova"],
                    posthoc="Pairwise comparisons on significant effects",
                    nonparametric_fallback=None, reasoning=reasoning,
                    interaction_to_check=True, interaction_plot_required=True,
                )
            return DecisionResult(
                research_question=research_question,
                recommended_test=f"Factorial ANOVA ({design_str} design)",
                design_label=f"{design_str} Factorial Design ({factor_names})",
                tests_to_run=["two_way_anova"],
                report_fields=_REPORT_FIELDS["two_way_anova"],
                effect_size_metric=_EFFECT_SIZE["two_way_anova"],
                posthoc="Tukey HSD on significant main effects",
                nonparametric_fallback="Scheirer–Ray–Hare test",
                reasoning=reasoning,
                interaction_to_check=True, interaction_plot_required=True,
            )

        # ONE grouping variable
        gv = gvars[0]
        n_groups = gv.n_levels
        is_repeated = gv.is_repeated
        reasoning.append(
            f"One grouping variable: \'{gv.name}\' with {n_groups} level(s). "
            f"Repeated measures: {is_repeated}."
        )

        # Ordinal outcome or normality failed → non-parametric
        if outcome_type == "ordinal" or not assume_normality:
            reasoning.append("Outcome is ordinal or normality assumption not met → non-parametric test.")
            if is_repeated:
                reasoning.append("Paired/repeated data → Wilcoxon signed-rank.")
                return DecisionResult(
                    research_question=research_question,
                    recommended_test="Wilcoxon Signed-Rank Test",
                    design_label="Ordinal / Non-Normal Paired Data",
                    tests_to_run=["wilcoxon_signed_rank"],
                    report_fields=_REPORT_FIELDS["wilcoxon_signed_rank"],
                    effect_size_metric=_EFFECT_SIZE["wilcoxon_signed_rank"],
                    posthoc=None, nonparametric_fallback=None, reasoning=reasoning,
                )
            if n_groups == 2:
                reasoning.append("2 independent groups → Mann–Whitney U test.")
                return DecisionResult(
                    research_question=research_question,
                    recommended_test="Mann–Whitney U Test",
                    design_label="Non-Parametric: 2 Independent Groups",
                    tests_to_run=["mann_whitney_u"],
                    report_fields=_REPORT_FIELDS["mann_whitney_u"],
                    effect_size_metric=_EFFECT_SIZE["mann_whitney_u"],
                    posthoc=None, nonparametric_fallback=None, reasoning=reasoning,
                )
            reasoning.append(f"{n_groups} independent groups → Kruskal–Wallis + Dunn post-hoc.")
            return DecisionResult(
                research_question=research_question,
                recommended_test="Kruskal–Wallis Test",
                design_label=f"Non-Parametric: {n_groups} Independent Groups",
                tests_to_run=["kruskal_wallis"],
                report_fields=_REPORT_FIELDS["kruskal_wallis"],
                effect_size_metric=_EFFECT_SIZE["kruskal_wallis"],
                posthoc="Dunn\'s test with Bonferroni correction",
                nonparametric_fallback=None, reasoning=reasoning,
            )

        # Continuous outcome, normal
        if is_repeated:
            if n_groups == 2:
                reasoning.append("Same subjects measured twice (paired) → Paired t-test.")
                reasoning.append("Report: mean difference, SD of differences, 95% CI, t, df, p-value, Cohen\'s d.")
                return DecisionResult(
                    research_question=research_question,
                    recommended_test="Paired-Samples t-test",
                    design_label="Paired Measurements (Pre/Post)",
                    tests_to_run=["paired_ttest"],
                    report_fields=_REPORT_FIELDS["paired_ttest"],
                    effect_size_metric=_EFFECT_SIZE["paired_ttest"],
                    posthoc=None, nonparametric_fallback="Wilcoxon Signed-Rank", reasoning=reasoning,
                )
            reasoning.append(f"Same subjects at {n_groups} timepoints → Repeated-Measures ANOVA.")
            return DecisionResult(
                research_question=research_question,
                recommended_test="One-Way Repeated-Measures ANOVA",
                design_label=f"Repeated Measures ({n_groups} timepoints)",
                tests_to_run=["repeated_measures_anova"],
                report_fields=_REPORT_FIELDS["repeated_measures_anova"],
                effect_size_metric=_EFFECT_SIZE["repeated_measures_anova"],
                posthoc="Bonferroni pairwise comparisons",
                nonparametric_fallback="Friedman Test", reasoning=reasoning,
            )

        # Independent groups
        if n_groups == 2:
            reasoning.append(
                f"Continuous outcome, 2 independent groups (\'{gv.name}\') → Independent-samples t-test."
            )
            reasoning.append(
                "Report: group means, SDs, mean difference, 95% CI, t statistic, df, p-value, Cohen\'s d."
            )
            reasoning.append(
                "Interpretation: State whether evidence supports a difference, the magnitude (Cohen\'s d), "
                "and what it means for the research question."
            )
            return DecisionResult(
                research_question=research_question,
                recommended_test="Independent-Samples t-test",
                design_label="2 Independent Groups",
                tests_to_run=["independent_ttest"],
                report_fields=_REPORT_FIELDS["independent_ttest"],
                effect_size_metric=_EFFECT_SIZE["independent_ttest"],
                posthoc=None, nonparametric_fallback="Mann–Whitney U Test", reasoning=reasoning,
            )

        reasoning.append(f"Continuous outcome, {n_groups} independent groups → One-way ANOVA.")
        reasoning.append("Report: group means, F statistic, df, p-value, η² (eta-squared), post-hoc comparisons.")
        return DecisionResult(
            research_question=research_question,
            recommended_test="One-Way ANOVA",
            design_label=f"{n_groups} Independent Groups",
            tests_to_run=["one_way_anova"],
            report_fields=_REPORT_FIELDS["one_way_anova"],
            effect_size_metric=_EFFECT_SIZE["one_way_anova"],
            posthoc="Tukey HSD (or Bonferroni if unequal group sizes)",
            nonparametric_fallback="Kruskal–Wallis Test", reasoning=reasoning,
        )

    # ── Fallback: simple linear regression ────────────────────────────────
    reasoning.append("Continuous predictor → Simple Linear Regression.")
    return DecisionResult(
        research_question=research_question,
        recommended_test="Simple Linear Regression",
        design_label="One Numerical Predictor → Numerical Outcome",
        tests_to_run=["linear_regression"],
        report_fields=_REPORT_FIELDS["linear_regression"],
        effect_size_metric=_EFFECT_SIZE["linear_regression"],
        posthoc=None, nonparametric_fallback=None, reasoning=reasoning,
    )


def decide_from_brief(brief: dict) -> list:
    """
    Convenience wrapper: extract structure from a validated brief dict
    and run the decision engine for each research question.
    Returns a list of DecisionResult objects (one per RQ).
    """
    results = []
    rqs = brief.get("research_questions") or []
    if not rqs:
        rqs = brief.get("objectives") or ["Research question not specified"]

    # Build grouping variables from brief
    gvars_raw = brief.get("grouping_variables") or []
    gvars = [
        GroupingVariable(
            name=gv.get("name", "Group"),
            n_levels=gv.get("n_levels") or len(gv.get("categories") or []) or 2,
            is_repeated=gv.get("is_repeated", False),
            scale=gv.get("scale", "nominal"),
            categories=gv.get("categories") or [],
        )
        for gv in gvars_raw
        if isinstance(gv, dict)
    ]

    # Infer outcome/predictor types from variable_scales in brief
    scales = brief.get("variable_scales") or {}
    dv = brief.get("dependent_variable", "")
    iv = brief.get("independent_variable", "")
    dv_scale = scales.get(dv, "").lower()
    iv_scale = scales.get(iv, "").lower()

    _CONTINUOUS = {"continuous", "ratio", "interval", "likert_5", "likert_7"}
    _CATEGORICAL = {"nominal"}
    _ORDINAL     = {"ordinal"}

    outcome_type = (
        "continuous"  if dv_scale in _CONTINUOUS
        else "binary" if dv_scale == "binary"
        else "ordinal" if dv_scale in _ORDINAL
        else "categorical" if dv_scale in _CATEGORICAL
        else "continuous"  # sensible default
    )
    predictor_type = (
        "categorical" if (iv_scale in _CATEGORICAL or gvars)
        else "continuous" if iv_scale in _CONTINUOUS
        else "categorical" if gvars
        else "none"
    )

    has_covariate = bool(brief.get("control_variables") or brief.get("control_variable"))

    for rq in rqs:
        if not str(rq).strip():
            continue
        try:
            result = decide_test(
                research_question=rq,
                outcome_type=outcome_type,
                predictor_type=predictor_type,
                grouping_variables=gvars if gvars else None,
                has_covariate=has_covariate,
                assume_normality=True,
            )
            results.append(result)
        except Exception as exc:
            logger.warning("[TestDecisionEngine] Failed for RQ=%r: %s", rq, exc)

    return results
