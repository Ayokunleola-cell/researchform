# backend/analysis/engine/dispatcher.py
"""
run_all_tests() — The heart of the Statistical Engine.

This function REPLACES _generate_code() + _execute_code() in pipeline.py.
It receives the test plan from Stage 4, runs every test deterministically
using pre-built Python functions, and returns structured JSON results ready
for Claude's report writer.

Claude AI never generates math code. It only receives the results and writes the report.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import hashlib
import logging
import json
from datetime import datetime

from analysis.engine.registry import get_registry, lookup
from analysis.engine.validator import run_health_check
from analysis.engine.assumptions import (
    check_normality, check_equal_variance,
    check_expected_frequencies, check_sphericity,
    check_multicollinearity, get_fallback,
)
from analysis.engine.schema import build_error
from analysis.engine.cache import get_cached, set_cached
from analysis.engine.fitness import check_test_fitness, MISMATCH, WARNING
from analysis.engine.weighting import _apply_survey_weights, _apply_imputation

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_all_tests(
    tests: list[dict],
    df: pd.DataFrame,
    brief: dict,
    data_dict: dict,
    missing_strategy: str = "auto",
    weight_column: str | None = None,
    imputation_method: str | None = None,
) -> dict:
    """
    Orchestrates the full analysis pipeline deterministically.

    Args:
        tests:            Ordered list of test specs from Stage 4 (LLM test selector).
        df:               The raw pandas DataFrame of the uploaded dataset.
        brief:            Research brief dict (topic, hypotheses, variables, etc.).
        data_dict:        Data profile dict from Stage 3 (variable types, ordinal_vars, etc.).
        missing_strategy: How to handle missing data before running tests.

    Returns:
        Structured results dict — sent directly to Stage 7 (_write_report).
    """
    # ── Initialize results container ─────────────────────────────────────────
    results = _empty_results()
    alpha = float(brief.get("significance_level", 0.05) or 0.05)

    # -- STEP 0: Survey Case Weighting ------------------------------------------
    weight_meta = None
    if weight_column and weight_column in df.columns:
        df, weight_meta = _apply_survey_weights(df.copy(), weight_column)
        results["warnings"].append(
            "Survey weighting applied using column '" + weight_column + "'. "
            "Effective N = " + str(weight_meta["effective_n"]) +
            " (unweighted N = " + str(weight_meta["unweighted_n"]) + ")."
        )
    elif weight_column:
        results["warnings"].append(
            "Weight column '" + weight_column + "' not found in dataset -- weighting skipped."
        )

    # -- STEP 1b: MICE / KNN Imputation (if requested) --------------------------
    if imputation_method in ("mice", "knn"):
        df, imp_meta = _apply_imputation(df.copy(), imputation_method)
        results["warnings"].append(
            "Missing data imputed using " + imp_meta["method"] + " (" +
            str(imp_meta["cols_imputed"]) + " columns, " +
            str(imp_meta["cells_imputed"]) + " cells filled)."
        )


    # ── STEP 1: Apply missing data strategy ──────────────────────────────────
    df = _apply_missing_strategy(df.copy(), missing_strategy)
    results["meta"] = _build_meta(df, tests, brief, missing_strategy)

    # ── STEP 2: Pre-Validation Health Check ──────────────────────────────────
    health = run_health_check(df, tests, brief)
    results["health_report"] = {
        "passed": health.passed,
        "warnings": health.warnings,
        "errors": health.errors,
        "auto_fixes": health.auto_fixes,
        "suggestions": health.suggestions,
    }
    results["warnings"].extend(health.warnings)

    if not health.passed:
        results["not_applicable"].append(
            build_error(
                "All Tests", "all",
                "Data quality errors prevent analysis: " + " | ".join(health.errors),
                "Fix the data quality issues listed in the health report and re-submit.",
            )
        )
        logger.error(f"[Dispatcher] Health check FAILED. Aborting analysis.")
        return results

    # ── STEP 3: Build dataset fingerprint for caching ─────────────────────────
    dataset_hash = results["meta"]["dataset_hash"]

    # ── STEP 4: Execute each test ─────────────────────────────────────────────
    registry = get_registry()

    for test_spec in tests:
        test_function = (test_spec.get("test_function") or "").strip()
        test_name = test_spec.get("test_name") or test_function
        variables = [v for v in (test_spec.get("variables") or []) if isinstance(v, str)]

        if not test_function:
            continue

        # ── Check if registered ───────────────────────────────────────────────
        if test_function not in registry:
            results["not_applicable"].append(
                build_error(
                    test_name, test_function,
                    f"'{test_function}' is not yet registered in the Statistical Engine.",
                    "This test will be available in a future release. Contact support if urgent.",
                )
            )
            logger.warning(f"[Dispatcher] Unknown test: {test_function}")
            continue

        entry = registry[test_function]

        # ── Minimum sample size guard ─────────────────────────────────────────
        n = len(df)
        min_n = entry.get("min_n", 1)
        if n < min_n:
            results["not_applicable"].append(
                build_error(
                    test_name, test_function,
                    f"Requires minimum n = {min_n}. Your dataset has n = {n}.",
                    "Collect more data or select a test appropriate for small samples.",
                )
            )
            continue

        # ── Check cache ───────────────────────────────────────────────────────
        cache_params = {"alpha": alpha, "missing_strategy": missing_strategy}
        cached = get_cached(dataset_hash, test_function, variables, cache_params)
        if cached is not None:
            _store_result(results, entry["family"], test_function, cached)
            if cached.get("p_value") is not None:
                _append_summary(results, test_spec, test_function, cached)
            results["meta"]["cache_hits"] = results["meta"].get("cache_hits", 0) + 1
            logger.debug(f"[Dispatcher] CACHE HIT: {test_function}")
            continue

        # ── Assumption checks + auto-fallback ─────────────────────────────────
        actual_fn_name = test_function
        assumption_results: dict = {}
        assumptions = entry.get("assumptions", [])

        valid_cols = [c for c in variables if c in df.columns]

        # ── PRE-FLIGHT: Fitness check (no AI — pure rule-based) ───────────────
        is_manual = bool(test_spec.get("manually_selected", False))
        try:
            fitness_report = check_test_fitness(
                test_function=test_function,
                test_name=test_name,
                df=df,
                variables=variables,
                brief=brief,
                registry_entry=entry,
            )
            if fitness_report["fitness"] == MISMATCH:
                # Always warn — but still run the test so the user sees the result
                warn_msg = (
                    f"[Fitness Mismatch] {test_name}: {fitness_report['message']}"
                    + (f" Suggestion: {fitness_report['suggestion']}" if fitness_report.get('suggestion') else "")
                )
                results["warnings"].append(warn_msg)
                logger.warning(f"[Dispatcher] Fitness MISMATCH for {test_function}: {fitness_report['message']}")
            elif fitness_report["fitness"] == WARNING:
                warn_msg = (
                    f"[Fitness Warning] {test_name}: {fitness_report['message']}"
                    + (f" Suggestion: {fitness_report['suggestion']}" if fitness_report.get('suggestion') else "")
                )
                results["warnings"].append(warn_msg)
                logger.info(f"[Dispatcher] Fitness WARNING for {test_function}: {fitness_report['message']}")
        except Exception as fe:
            fitness_report = {"fitness": "good"}
            logger.debug(f"[Dispatcher] Fitness check error for {test_function}: {fe}")

        for assumption in assumptions:
            try:
                if assumption == "normality" and valid_cols:
                    # Find first numeric column for normality check
                    numeric_col = next(
                        (c for c in valid_cols if pd.api.types.is_numeric_dtype(df[c])), None
                    )
                    if numeric_col:
                        norm = check_normality(df[numeric_col].dropna(), alpha)
                        assumption_results["normality"] = norm
                        if not norm["passed"]:
                            fb = get_fallback(test_function, "non_normal")
                            if fb and fb in registry:
                                results["fallbacks_applied"].append({
                                    "original": test_function, "fallback": fb,
                                    "reason": f"Normality violated ({norm['test_used']} p = {norm['p_value']}). Switched to {fb}.",
                                })
                                actual_fn_name = fb
                                logger.info(f"[Dispatcher] Fallback: {test_function} → {fb}")

                elif assumption == "equal_variance" and len(valid_cols) >= 2:
                    group_col = valid_cols[0]
                    outcome_col = valid_cols[1] if len(valid_cols) > 1 else None
                    if outcome_col and pd.api.types.is_numeric_dtype(df.get(outcome_col, pd.Series())):
                        groups = [
                            df[df[group_col] == g][outcome_col].dropna()
                            for g in df[group_col].dropna().unique()
                            if len(df[df[group_col] == g]) >= 2
                        ]
                        if len(groups) >= 2:
                            var_res = check_equal_variance(*groups, alpha=alpha)
                            assumption_results["equal_variance"] = var_res
                            if not var_res["passed"] and test_function == "independent_t_test":
                                actual_fn_name = "welch_t_test"
                                results["fallbacks_applied"].append({
                                    "original": "independent_t_test", "fallback": "welch_t_test",
                                    "reason": f"Unequal variances (Levene p = {var_res['p_value']}). Welch's t-test applied.",
                                })

                elif assumption == "expected_freq" and len(valid_cols) >= 2:
                    col1, col2 = valid_cols[0], valid_cols[1]
                    if col1 in df.columns and col2 in df.columns:
                        ct = pd.crosstab(df[col1].dropna(), df[col2].dropna())
                        if ct.size > 0:
                            freq_res = check_expected_frequencies(ct)
                            assumption_results["expected_frequencies"] = freq_res
                            if not freq_res["valid_for_chi_square"]:
                                actual_fn_name = "fisher_exact"
                                results["fallbacks_applied"].append({
                                    "original": "chi_square", "fallback": "fisher_exact",
                                    "reason": f"{freq_res['cells_below_5_pct']}% of expected cells < 5. Fisher's Exact used.",
                                })

                elif assumption == "sphericity" and len(valid_cols) >= 3:
                    sph = check_sphericity(df, valid_cols, alpha)
                    assumption_results["sphericity"] = sph
                    if not sph["passed"]:
                        fb = get_fallback(test_function, "sphericity_violated")
                        if fb and fb in registry:
                            actual_fn_name = fb
                            results["fallbacks_applied"].append({
                                "original": test_function, "fallback": fb,
                                "reason": f"Sphericity violated (p = {sph.get('p_value')}). Switched to {fb}.",
                            })

                elif assumption == "vif" and len(valid_cols) >= 3:
                    vif = check_multicollinearity(df, valid_cols[1:])
                    assumption_results["vif"] = vif
                    if not vif["passed"]:
                        results["warnings"].append(
                            f"Multicollinearity detected in {test_name}. "
                            f"Problematic predictors: {list(vif.get('severe_multicollinearity', {}).keys())}. "
                            "Consider removing correlated predictors."
                        )
            except Exception as ae:
                logger.warning(f"[Dispatcher] Assumption check failed ({assumption}): {ae}")

        # ── Auto-resolve variables for mediation / moderation tests ──────────
        # These tests require exactly [IV, Med/Mod, DV]. If the LLM or fallback
        # produced an empty/incomplete variable list, fill from the brief directly.
        if actual_fn_name in ("mediation_analysis", "moderation_analysis", "moderated_mediation"):
            variables = _resolve_medmod_variables(brief, df, actual_fn_name, variables)

        # ── Run the (possibly substituted) test function ───────────────────────
        run_entry = registry.get(actual_fn_name, entry)
        fn = run_entry["fn"]
        family = run_entry.get("family", "descriptive")

        try:
            test_result = fn(df=df, variables=variables, brief=brief, alpha=alpha)

            if test_result is None:
                results["not_applicable"].append(
                    build_error(test_name, actual_fn_name,
                                "Test returned no result (None).",
                                "Check variable selection for this test.")
                )
                continue

            # Enrich result with metadata
            test_result["test_key"] = test_function       # original registry key
            test_result["test_function_used"] = actual_fn_name
            test_result["assumption_checks"] = assumption_results
            if actual_fn_name != test_function:
                test_result["original_test_requested"] = test_function

            # ── Attach fitness report so frontend can show the indicator ──────
            test_result["fitness"] = fitness_report.get("fitness", "good")
            if fitness_report.get("fitness") in (WARNING, MISMATCH):
                test_result["fitness_message"]    = fitness_report.get("message", "")
                test_result["fitness_suggestion"] = fitness_report.get("suggestion", "")
                test_result["fitness_mismatch"]   = (fitness_report["fitness"] == MISMATCH)
            else:
                test_result["fitness_mismatch"] = False

            # Store in correct bucket
            _store_result(results, family, test_function, test_result)

            # Add to summary if it has a p-value or it's an error
            if test_result.get("p_value") is not None or test_result.get("error"):
                _append_summary(results, test_spec, actual_fn_name, test_result)

            # Cache the result
            set_cached(test_result, dataset_hash, test_function, variables, cache_params)

            logger.debug(f"[Dispatcher] ✓ {test_function} (→{actual_fn_name}) n={n}")

        except Exception as e:
            logger.error(f"[Dispatcher] ✗ {actual_fn_name}: {e}", exc_info=True)
            results["not_applicable"].append(
                build_error(
                    test_name, actual_fn_name,
                    f"Runtime error: {str(e)}",
                    "Verify that the selected variables are the correct types for this test.",
                )
            )

    # ── STEP 5: Finalize metadata ─────────────────────────────────────────────
    results["meta"]["completed_at"] = datetime.utcnow().isoformat()
    results["meta"]["tests_requested"] = len(tests)
    results["meta"]["tests_run"] = len(results["summary"])
    results["meta"]["tests_skipped"] = len(results["not_applicable"])
    results["meta"]["fallbacks_applied"] = len(results["fallbacks_applied"])

    logger.info(
        f"[Dispatcher] Done. ran={results['meta']['tests_run']}, "
        f"skipped={results['meta']['tests_skipped']}, "
        f"fallbacks={results['meta']['fallbacks_applied']}"
    )
    return results


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _empty_results() -> dict:
    return {
        "meta": {},
        "health_report": {},
        "summary": [],
        "descriptive": {},
        "frequencies": {},
        "normality": {},
        "reliability": {},
        "outliers": {},
        "assumptions": {},
        "comparison": {},
        "correlation": {},
        "regression": {},
        "posthoc": {},
        "multivariate": {},
        "survival": {},
        "causal": {},
        "timeseries": {},
        "multilevel": {},
        "power": {},
        "missing": {},
        "not_applicable": [],
        "warnings": [],
        "fallbacks_applied": [],
    }


def _apply_missing_strategy(df: pd.DataFrame, strategy: str) -> pd.DataFrame:
    """
    Apply a missing-data strategy to the DataFrame before running tests.

    Strategies
    ----------
    auto          Smart type-aware imputation (DEFAULT):
                    • numeric columns  → median (robust to outliers/Likert scales)
                    • categorical/object → mode (most frequent category)
    mean_impute   Replace numeric NAs with column mean; leave categorical as-is.
    median_impute Replace numeric NAs with column median; leave categorical as-is.
    mode_impute   Replace all NAs with the column mode (works for any type).
    knn_impute    K-Nearest Neighbours imputation for numeric columns (k=5).
                  Falls back to median if scikit-learn is not installed.
    drop_rows     Drop every row that contains at least one NA.
    flag_only     Pass the DataFrame through unchanged (legacy listwise deletion
                  happens inside each test via .dropna()). Use only when you
                  want full control over per-test sample sizes.
    """
    if df.empty:
        return df

    try:
        if strategy == "flag_only":
            # Legacy behaviour — no imputation; each test calls .dropna() itself.
            return df

        if strategy == "drop_rows":
            before = len(df)
            result = df.dropna()
            dropped = before - len(result)
            if dropped:
                logger.info(f"[Dispatcher] drop_rows: removed {dropped} rows with any NA.")
            return result

        if strategy in ("auto", "mean_impute", "median_impute"):
            df = df.copy()
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            cat_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()

            for col in numeric_cols:
                if df[col].isna().any():
                    if strategy == "mean_impute":
                        fill_val = df[col].mean()
                    else:
                        # "auto" and "median_impute" both use median:
                        # median is robust to outliers and correct for ordinal
                        # Likert scales (where the mean can be non-integer).
                        fill_val = df[col].median()
                    n_filled = df[col].isna().sum()
                    df[col] = df[col].fillna(fill_val)
                    logger.debug(f"[Dispatcher] {strategy}: filled {n_filled} NAs in '{col}' with {strategy.replace('_impute','').replace('auto','median')}={fill_val:.4f}")

            if strategy == "auto":
                # For categorical columns, impute with mode
                for col in cat_cols:
                    if df[col].isna().any():
                        mode_vals = df[col].mode()
                        if len(mode_vals) > 0:
                            n_filled = df[col].isna().sum()
                            df[col] = df[col].fillna(mode_vals.iloc[0])
                            logger.debug(f"[Dispatcher] auto: filled {n_filled} NAs in '{col}' (categorical) with mode='{mode_vals.iloc[0]}'")

            return df

        if strategy == "mode_impute":
            df = df.copy()
            for col in df.columns:
                if df[col].isna().any():
                    mode_vals = df[col].mode()
                    if len(mode_vals) > 0:
                        df[col] = df[col].fillna(mode_vals.iloc[0])
            return df

        if strategy == "knn_impute":
            df = df.copy()
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if not numeric_cols:
                return df
            try:
                from sklearn.impute import KNNImputer
                imputer = KNNImputer(n_neighbors=5, weights="distance")
                df[numeric_cols] = imputer.fit_transform(df[numeric_cols])
                logger.info(f"[Dispatcher] knn_impute: applied KNN (k=5) to {len(numeric_cols)} numeric columns.")
            except ImportError:
                logger.warning("[Dispatcher] knn_impute: scikit-learn not installed. Falling back to median imputation.")
                for col in numeric_cols:
                    if df[col].isna().any():
                        df[col] = df[col].fillna(df[col].median())
            return df

        # Unknown strategy — log a warning and return unchanged
        logger.warning(f"[Dispatcher] Unknown missing strategy '{strategy}'. Skipping imputation (flag_only behaviour).")
        return df

    except Exception as e:
        logger.warning(f"[Dispatcher] Missing strategy '{strategy}' failed: {e}. Skipping imputation.")
        return df



def _build_meta(df: pd.DataFrame, tests: list, brief: dict, strategy: str) -> dict:
    try:
        df_hash = hashlib.md5(
            pd.util.hash_pandas_object(df, index=True).values.tobytes()
        ).hexdigest()
    except Exception:
        df_hash = "unknown"
    return {
        "dataset_hash": df_hash,
        "n_rows": len(df),
        "n_cols": len(df.columns),
        "n_tests_requested": len(tests),
        "alpha": brief.get("significance_level", 0.05),
        "missing_strategy": strategy,
        "engine_version": "2.0.0",
        "started_at": datetime.utcnow().isoformat(),
    }


_FAMILY_BUCKET_MAP = {
    "descriptive":    "descriptive",
    "frequencies":    "frequencies",
    "normality":      "normality",
    "assumption":     "assumptions",
    "reliability":    "reliability",
    "outlier":        "outliers",
    "comparison":     "comparison",
    "association":    "comparison",
    "anova":          "comparison",       # ANOVA-family tests (one_way_anova, planned_contrasts, etc.)
    "correlation":    "correlation",
    "regression":     "regression",
    "posthoc":        "posthoc",
    "effect_size":    "comparison",
    "multivariate":   "multivariate",
    "sem":            "multivariate",
    "survival":       "survival",
    "causal":         "causal",
    "timeseries":     "timeseries",
    "multilevel":     "multilevel",
    "power":          "power",
    "power_analysis": "power",            # alias used by some power test registrations
    "missing":        "missing",
}


def _store_result(results: dict, family: str, key: str, value: dict) -> None:
    bucket = _FAMILY_BUCKET_MAP.get(family, "descriptive")
    results[bucket][key] = value


def _append_summary(results: dict, test_spec: dict, fn_used: str, test_result: dict) -> None:
    """Append a normalised summary row that the frontend can render directly.

    The frontend expects FLAT fields for statistic/effect_size values so it
    can display them without nested object traversal.  We preserve the nested
    objects too (backward-compat) but add convenience flat aliases.
    """
    stat_obj  = test_result.get("statistic") or {}
    eff_obj   = test_result.get("effect_size") or {}

    # Flatten statistic
    stat_value = stat_obj.get("value") if isinstance(stat_obj, dict) else stat_obj
    stat_name  = stat_obj.get("label") if isinstance(stat_obj, dict) else None

    # Flatten effect size
    eff_value = eff_obj.get("value") if isinstance(eff_obj, dict) else eff_obj
    eff_name  = eff_obj.get("name")  if isinstance(eff_obj, dict) else None
    eff_interp = eff_obj.get("interpretation") if isinstance(eff_obj, dict) else None

    # Confidence interval → list format expected by frontend
    ci_raw = test_result.get("confidence_interval") or {}
    ci_95 = None
    if isinstance(ci_raw, dict) and ci_raw.get("lower") is not None and ci_raw.get("upper") is not None:
        ci_95 = [ci_raw["lower"], ci_raw["upper"]]

    # Post-hoc pairwise comparisons (ANOVA etc.)
    post_hoc = (
        test_result.get("post_hoc")
        or test_result.get("posthoc")
        or (test_result.get("additional_stats") or {}).get("post_hoc")
        or (test_result.get("additional_stats") or {}).get("pairwise")
        or []
    )

    results["summary"].append({
        # ── Core identifiers ──────────────────────────────────────────────
        "test_name":        test_spec.get("test_name", fn_used),
        "test_function":    fn_used,
        "hypothesis_index": test_spec.get("hypothesis_index", -1),
        "hypothesis":       test_spec.get("hypothesis", ""),

        # ── Statistic (nested + flat aliases) ─────────────────────────────
        "statistic":        stat_obj,           # nested object kept for compat
        "statistic_name":   stat_name,          # flat alias — used by frontend table header
        "statistic_value":  stat_value,         # flat numeric value

        # Degrees of freedom
        "df":               test_result.get("df"),

        # ── p-value & significance ────────────────────────────────────────
        "p_value":          test_result.get("p_value"),
        "significant":      test_result.get("significant"),

        # ── Effect size (nested + flat aliases) ───────────────────────────
        "effect_size":      eff_obj,            # nested object kept for compat
        "effect_size_value": eff_value,         # flat numeric value
        "effect_size_name": eff_name,           # flat name string
        "effect_size_interpretation": eff_interp,

        # ── 95% CI ────────────────────────────────────────────────────────
        "ci_95":            ci_95,

        # ── Narrative & sample size ────────────────────────────────────────
        "conclusion":       test_result.get("conclusion", ""),
        "n":                test_result.get("n"),

        # ── Post-hoc table ────────────────────────────────────────────────
        "post_hoc":         post_hoc if isinstance(post_hoc, list) else [],

        # ── Fitness / error metadata ──────────────────────────────────────
        "fitness":          test_result.get("fitness", "good"),
        "fitness_message":  test_result.get("fitness_message", ""),
        "fitness_mismatch": test_result.get("fitness_mismatch", False),
        "error":            test_result.get("reason") if test_result.get("error") else None,
    })


# ─────────────────────────────────────────────────────────────────────────────
# MEDIATION / MODERATION VARIABLE AUTO-RESOLVER
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_medmod_variables(
    brief: dict,
    df: "pd.DataFrame",
    test_function: str,
    current_vars: list[str],
) -> list[str]:
    """
    For mediation_analysis, moderation_analysis, and moderated_mediation,
    ensure the variable list is complete. Falls back to brief fields when the
    LLM-provided variable list is missing or incomplete.

    Expected variable order:
      mediation_analysis:   [IV, Mediator, DV]
      moderation_analysis:  [IV, Moderator, DV]
      moderated_mediation:  [IV, Mediator, Moderator, DV]
    """
    def _first_valid(raw: str) -> str:
        """Take first comma-token; return empty string if column not in df."""
        token = (raw or "").split(",")[0].strip()
        return token  # caller validates against df.columns

    iv_raw  = brief.get("independent_variable", "") or brief.get("iv_column", "") or ""
    dv_raw  = brief.get("dependent_variable",   "") or brief.get("dv_column", "") or ""
    med_raw = brief.get("mediating_variable",   "") or brief.get("mediating_column", "") or ""
    mod_raw = brief.get("moderating_variable",  "") or brief.get("moderating_column", "") or ""

    iv  = _first_valid(iv_raw)
    dv  = _first_valid(dv_raw)
    med = _first_valid(med_raw)
    mod = _first_valid(mod_raw)

    # Only use brief-resolved vars if the current list is incomplete
    if test_function == "mediation_analysis":
        needed = 3
        if len(current_vars) >= needed:
            return current_vars
        # Build from brief
        resolved = [v for v in [iv, med, dv] if v]
        if len(resolved) == needed:
            logger.info(f"[Dispatcher] mediation_analysis: auto-resolved variables → {resolved}")
            return resolved
        return current_vars  # partial — let the engine report the error

    elif test_function == "moderation_analysis":
        needed = 3
        if len(current_vars) >= needed:
            return current_vars
        resolved = [v for v in [iv, mod, dv] if v]
        if len(resolved) == needed:
            logger.info(f"[Dispatcher] moderation_analysis: auto-resolved variables → {resolved}")
            return resolved
        return current_vars

    elif test_function == "moderated_mediation":
        needed = 4
        if len(current_vars) >= needed:
            return current_vars
        resolved = [v for v in [iv, med, mod, dv] if v]
        if len(resolved) == needed:
            logger.info(f"[Dispatcher] moderated_mediation: auto-resolved variables → {resolved}")
            return resolved
        return current_vars

    return current_vars
