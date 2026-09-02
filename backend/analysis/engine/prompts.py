# backend/analysis/engine/prompts.py
"""
Specialist Claude report prompts — one per statistical test family.
Claude receives the pre-computed JSON results + a specialist prompt 
and writes a professional APA-formatted narrative.
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# REPORT PROMPT TEMPLATES
# Variables available in every prompt: {context}, {results}, {fallbacks},
# {alpha}, {report_type}, {topic}, {hypotheses}
# ─────────────────────────────────────────────────────────────────────────────

PROMPTS: dict[str, str] = {

    # ── DESCRIPTIVE STATISTICS ───────────────────────────────────────────────
    "descriptive": """
You are a senior academic statistician writing Chapter 4 of a university research report.

STUDY CONTEXT:
{context}

DESCRIPTIVE STATISTICS RESULTS (JSON — pre-computed, use these numbers only):
{results}

Write a complete, APA 7th edition Descriptive Statistics section that:
1. Opens with a brief paragraph introducing the variables and sample (n = {n}).
2. For each continuous variable: report M (mean), SD (standard deviation), Mdn (median), and the range [min, max] in APA format: M = X.XX, SD = X.XX.
3. For each categorical variable: report frequencies and percentages (e.g., "Male respondents comprised 54.3% (n = 65) of the sample").
4. Discuss skewness and kurtosis where notable (|skewness| > 1 warrants a comment).
5. Conclude with a brief data quality note (missing data, outliers flagged).

STRICT RULES:
- Use ONLY the numbers from the JSON above. Do NOT invent or recalculate any values.
- Write in third person, past tense, academic English.
- Format all statistics in APA style (italicise statistic symbols in your mind: M, SD, p, F, t).
- Do not include headings — this section flows into the broader Chapter 4.
""",

    # ── NORMALITY & ASSUMPTIONS ──────────────────────────────────────────────
    "assumption": """
You are a biostatistician writing the Preliminary Analysis / Assumption Checks section.

STUDY CONTEXT:
{context}

ASSUMPTION CHECK RESULTS:
{results}

FALLBACKS APPLIED:
{fallbacks}

Write an APA-style preliminary analysis section that:
1. Reports normality test results for each variable tested (test name, statistic, df, p-value).
2. States clearly whether parametric or non-parametric tests were selected as a result.
3. If any fallbacks were applied (e.g., "Mann-Whitney was used instead of independent t-test due to normality violation"), state them explicitly with the p-value that triggered the switch.
4. Reports homogeneity of variance results (Levene's test) where applicable.
5. Notes any sphericity corrections (Greenhouse-Geisser epsilon) for repeated-measures tests.

FORMAT: "The Shapiro-Wilk test indicated that [variable] was not normally distributed, W(N) = X.XX, p = .XXX. Consequently, the non-parametric [test] was employed."
""",

    # ── RELIABILITY ──────────────────────────────────────────────────────────
    "reliability": """
You are a psychometrician writing the Scale Reliability section.

STUDY CONTEXT:
{context}

RELIABILITY RESULTS:
{results}

Write a complete reliability section that:
1. Reports Cronbach's α for each scale with interpretation:
   - α < .60: "Unacceptable internal consistency"
   - α = .60–.69: "Poor internal consistency"  
   - α = .70–.79: "Acceptable internal consistency"
   - α = .80–.89: "Good internal consistency"
   - α ≥ .90: "Excellent internal consistency"
2. Reports the number of items and mean inter-item correlation.
3. If item_analysis data is present: identify items with item-total correlation < .30 and recommend their review.
4. If McDonald's omega is present: report ω alongside α for a more robust estimate.
5. Conclude with whether the scales are suitable for further inferential analysis.

APA FORMAT: "The [Scale Name] demonstrated [good] internal consistency (α = .XX, k = X items, M_r_ii = .XX)."
""",

    # ── COMPARISON TESTS (T-Tests, ANOVA, Non-Parametric) ───────────────────
    "comparison": """
You are an expert statistician writing the Inferential Statistics section.

STUDY CONTEXT:
{context}

STATISTICAL TEST RESULTS:
{results}

HYPOTHESES BEING TESTED:
{hypotheses}

FALLBACKS APPLIED (state these explicitly in the narrative):
{fallbacks}

Write a complete APA-style results section that for each test:
1. States the test used and why (especially if a fallback test was applied due to assumption violation).
2. Provides full APA statistics: e.g., t(38) = 2.45, p = .019, d = 0.78 (large).
3. Reports group means and SDs in context: "The treatment group (M = 4.23, SD = 0.87) scored significantly higher than the control group (M = 3.10, SD = 0.94)."
4. States the hypothesis decision: "The null hypothesis was rejected" or "The null hypothesis was not rejected."
5. Interprets effect size magnitude (small/medium/large using Cohen's benchmarks).
6. For ANOVA: includes post-hoc results (which groups differed, adjusted p-values).

STRICT APA FORMAT for statistics:
- t-test: t(df) = X.XX, p = .XXX, d = X.XX
- ANOVA: F(df_between, df_within) = X.XX, p = .XXX, η² = X.XX
- Mann-Whitney: U = XXX, z = X.XX, p = .XXX, r = X.XX
- Kruskal-Wallis: H(df) = X.XX, p = .XXX, η² = X.XX
""",

    # ── CORRELATION ──────────────────────────────────────────────────────────
    "correlation": """
You are a statistician writing the Correlation Analysis section.

STUDY CONTEXT:
{context}

CORRELATION RESULTS:
{results}

Write a complete APA correlation results section that:
1. Introduces the correlation analysis and which variables were examined.
2. For each correlation pair: reports r/rho, p-value, and 95% CI: r(df) = X.XX, p = .XXX, 95% CI [X.XX, X.XX].
3. Interprets the direction and strength: "A strong positive correlation... A weak negative correlation..."
4. For correlation matrices: narrates the key significant relationships without listing every cell.
5. If partial correlations: explains what variable was controlled for and how it changed the relationship.
6. Uses Cohen's (1988) benchmarks for interpretation: |r| < .10 negligible, .10–.29 small, .30–.49 medium, ≥ .50 large.

NOTE: Report non-significant correlations too (e.g., "No significant correlation was found between X and Y, r = .08, p = .423").
""",

    # ── REGRESSION ───────────────────────────────────────────────────────────
    "regression": """
You are a statistician writing the Regression Analysis section.

STUDY CONTEXT:
{context}

REGRESSION RESULTS:
{results}

Write a complete APA regression section that:
1. Reports model fit: "The model was statistically significant, F(df1, df2) = X.XX, p = .XXX, R² = .XX, indicating that the predictors explained X% of the variance in [outcome]."
2. Presents a coefficients table narrative: for each predictor report B, SE, β (standardized), t, p, and 95% CI [B_lower, B_upper].
3. Identifies the strongest predictor by standardized β.
4. Reports the regression equation: Ŷ = B0 + B1X1 + B2X2 + ...
5. If VIF values present: notes any multicollinearity concerns (VIF > 5 = moderate, > 10 = severe).
6. If Durbin-Watson present: comments on autocorrelation (DW near 2.0 = no autocorrelation).
7. For logistic regression: reports Odds Ratios (OR) with 95% CI and model fit (χ²(df) = X.XX, p = .XXX, Nagelkerke R² = .XX).
8. For hierarchical regression: reports each block's R² change and its significance (ΔR², ΔF, Δp).
9. For mediation: states indirect effect with bootstrap CI: "The indirect effect of X on Z through M was significant, B = X.XX, 95% CI [X.XX, X.XX], indicating [full/partial] mediation."
""",

    # ── RELIABILITY + FACTOR ANALYSIS ────────────────────────────────────────
    "multivariate": """
You are a psychometrician and multivariate statistician writing the Factor/PCA/SEM section.

STUDY CONTEXT:
{context}

MULTIVARIATE RESULTS:
{results}

Write a complete section covering:

FOR PCA/EFA:
1. Reports the number of factors retained and criteria (eigenvalue > 1, scree plot inflection).
2. Reports total variance explained: "X factors were retained, collectively explaining XX.X% of the total variance."
3. For each factor: lists its highest-loading variables (loading > .40) and proposes a construct name.
4. Reports communalities: "The variable [X] demonstrated a communality of .XX, indicating that XX% of its variance was explained by the common factors."

FOR SEM/CFA:
1. Reports model fit: χ²(df) = X.XX, p = .XXX; CFI = X.XX; RMSEA = X.XX [X.XX, X.XX]; SRMR = X.XX; TLI = X.XX.
2. Interprets fit: CFI > .95, RMSEA < .06, SRMR < .08 = good fit.
3. Reports all significant path coefficients with β, SE, z, p.
4. States whether the hypothesized model is supported.

FOR LDA:
1. Reports the number of discriminant functions and their eigenvalues.
2. Reports Wilks' lambda and its chi-square significance.
3. Reports classification accuracy: "The discriminant model correctly classified XX.X% of cases."
""",

    # ── SURVIVAL ANALYSIS ────────────────────────────────────────────────────
    "survival": """
You are a clinical biostatistician writing the Survival Analysis section.

STUDY CONTEXT:
{context}

SURVIVAL RESULTS:
{results}

Write a complete survival analysis section that:
1. Reports median survival time with 95% CI for each group.
2. For Kaplan-Meier: reports the log-rank test: χ²(df) = X.XX, p = .XXX, indicating [significant/non-significant] difference in survival curves.
3. For Cox PH: reports the Hazard Ratio table: "Covariate X was associated with [higher/lower] hazard (HR = X.XX, 95% CI [X.XX, X.XX], p = .XXX)."
4. Interprets HR: "An HR > 1 indicates increased hazard (shorter survival); HR < 1 indicates reduced hazard (longer survival)."
5. Reports the concordance index (C-statistic) as a model discrimination measure.
6. Notes whether the proportional hazards assumption was met.
""",

    # ── CAUSAL INFERENCE ─────────────────────────────────────────────────────
    "causal": """
You are an econometrician writing the Causal Inference section.

STUDY CONTEXT:
{context}

CAUSAL ANALYSIS RESULTS:
{results}

Write a complete section that:
1. For Propensity Score Matching: reports balance (SMD before/after), matched sample size, ATE and ATT estimates with CI and p.
2. For DiD: states "The difference-in-differences estimate of B = X.XX (SE = X.XX, p = .XXX) indicates that [treatment] resulted in a [X.XX unit increase/decrease] in [outcome] relative to the control group."
3. For ITS: reports the level change and slope change at the intervention point with significance.
4. Includes appropriate causal disclaimers about confounding if randomization was not used.
""",

    # ── TIME SERIES ──────────────────────────────────────────────────────────
    "timeseries": """
You are a time series analyst writing the Time Series Analysis section.

STUDY CONTEXT:
{context}

TIME SERIES RESULTS:
{results}

Write a complete section that:
1. Reports stationarity test results (ADF: t = X.XX, p = .XXX) and whether differencing was needed.
2. Reports the selected ARIMA order (p,d,q) and its justification (AIC criterion).
3. Reports model fit: AIC = X.XX, MAE = X.XX, RMSE = X.XX.
4. Reports forecast values for the next X periods with confidence intervals.
5. For Granger causality: "Variable X Granger-caused Variable Y at lag L, F(df1, df2) = X.XX, p = .XXX."
6. For seasonal decomposition: reports trend direction and strength of seasonality.
""",

}


def get_prompt(family: str, context: str, results: str, fallbacks: str = "",
               alpha: float = 0.05, hypotheses: str = "", topic: str = "",
               report_type: str = "chapter4", n: int = 0) -> str:
    """
    Retrieve the formatted specialist prompt for a test family.
    Falls back to a generic prompt if the family is not registered.
    """
    template = PROMPTS.get(family, PROMPTS["comparison"])
    return template.format(
        context=context,
        results=results,
        fallbacks=fallbacks or "None — all tests ran as planned.",
        alpha=alpha,
        hypotheses=hypotheses or "See research brief.",
        topic=topic,
        report_type=report_type,
        n=n,
    )


# ─── Master prompt registry: maps test_function → family ─────────────────────
TEST_FAMILY_MAP: dict[str, str] = {
    # descriptive
    "descriptive_stats": "descriptive", "frequency_analysis": "descriptive",
    "mean_median_mode": "descriptive", "dispersion_extended": "descriptive",
    "percentiles_extended": "descriptive", "z_scores": "descriptive",
    "skewness_analysis": "descriptive", "kurtosis_analysis": "descriptive",
    "variable_transformation": "descriptive",
    # assumptions
    "normality_check": "assumption", "shapiro_wilk_all": "assumption",
    "kolmogorov_smirnov": "assumption", "anderson_darling": "assumption",
    "jarque_bera": "assumption", "dagostino_pearson": "assumption",
    "omnibus_normality": "assumption", "levene_test": "assumption",
    "bartlett_test": "assumption", "mauchly_test": "assumption",
    "durbin_watson": "assumption", "vif_check": "assumption",
    # reliability
    "cronbach_alpha": "reliability", "mcdonald_omega": "reliability",
    "split_half_reliability": "reliability", "item_analysis": "reliability",
    "icc": "reliability", "kr20": "reliability",
    # outliers
    "outliers_iqr": "descriptive", "outliers_zscore": "descriptive",
    "outliers_grubbs": "descriptive", "mahalanobis_distance": "multivariate",
    "cooks_distance": "regression",
    # comparison
    "one_sample_t_test": "comparison", "independent_t_test": "comparison",
    "welch_t_test": "comparison", "paired_t_test": "comparison",
    "one_way_anova": "comparison", "two_way_anova": "comparison",
    "welch_anova": "comparison", "repeated_anova": "comparison",
    "ancova": "comparison", "manova": "comparison",
    "mann_whitney": "comparison", "wilcoxon": "comparison",
    "kruskal_wallis": "comparison", "friedman_test": "comparison",
    "mcnemar": "comparison", "chi_square": "comparison",
    "fisher_exact": "comparison", "sign_test": "comparison",
    # effect sizes
    "independent_t_cohend": "comparison", "paired_t_cohend": "comparison",
    "anova_eta_squared": "comparison", "mann_whitney_r": "comparison",
    "wilcoxon_r": "comparison", "kruskal_wallis_eta2": "comparison",
    # post-hoc
    "tukey_hsd": "comparison", "bonferroni_test": "comparison",
    "dunn_test": "comparison", "scheffe_test": "comparison",
    "newman_keuls": "comparison", "fisher_lsd": "comparison",
    # correlation
    "pearson_correlation": "correlation", "spearman_correlation": "correlation",
    "kendall_tau": "correlation", "point_biserial": "correlation",
    "phi_coefficient": "correlation", "cramers_v": "correlation",
    "partial_correlation": "correlation", "canonical_correlation": "correlation",
    "correlation_matrix": "correlation", "correlation_significance": "correlation",
    # regression
    "simple_linear_regression": "regression", "multiple_regression": "regression",
    "logistic_regression": "regression", "ordinal_regression": "regression",
    "multinomial_logistic": "regression", "hierarchical_regression": "regression",
    "stepwise_regression": "regression", "mediation_analysis": "regression",
    "moderation_analysis": "regression", "quantile_regression": "regression",
    "poisson_regression": "regression", "negative_binomial": "regression",
    "cox_regression": "survival",
    # multivariate
    "pca": "multivariate", "factor_analysis": "multivariate",
    "confirmatory_fa": "multivariate", "discriminant_analysis": "multivariate",
    "cluster_analysis": "multivariate", "sem": "multivariate",
    "path_analysis": "multivariate",
    # survival
    "survival_analysis": "survival",
    # causal
    "propensity_score_matching": "causal", "difference_in_differences": "causal",
    "interrupted_time_series": "causal",
    # time series
    "time_series": "timeseries",
    # multilevel
    "linear_mixed_effects": "multivariate", "gee": "multivariate",
}


def get_family(test_function: str) -> str:
    """Returns the report family for a given test_function name."""
    return TEST_FAMILY_MAP.get(test_function, "comparison")
