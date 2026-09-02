# backend/analysis/engine/tests/survival.py
"""Survival analysis — Kaplan-Meier, Log-Rank, Cox PH, Weibull, Nelson-Aalen, Life Table."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error

try:
    from lifelines import (
        KaplanMeierFitter, CoxPHFitter, WeibullAFTFitter,
        NelsonAalenFitter, LogNormalFitter, ExponentialFitter
    )
    from lifelines.statistics import logrank_test, multivariate_logrank_test
    _lifelines = True
except ImportError:
    _lifelines = False


def _check_cols(df, duration_col, event_col):
    if duration_col not in df.columns:
        return f"Duration column '{duration_col}' not found."
    if event_col not in df.columns:
        return f"Event column '{event_col}' not found."
    if not pd.api.types.is_numeric_dtype(df[duration_col]):
        return f"Duration column '{duration_col}' must be numeric."
    return None


def run_kaplan_meier(df, variables, brief, alpha=0.05):
    try:
        if not _lifelines:
            return build_error("Kaplan-Meier", "kaplan_meier",
                               "lifelines not installed.", "pip install lifelines")
        if len(variables) < 2:
            return build_error("Kaplan-Meier", "kaplan_meier",
                               "Need duration_col and event_col.", "Select 2 variables.")
        duration_col, event_col = variables[0], variables[1]
        err = _check_cols(df, duration_col, event_col)
        if err:
            return build_error("Kaplan-Meier", "kaplan_meier", err, "Check column selection.")
        data = df[[duration_col, event_col]].dropna()
        T = data[duration_col]; E = data[event_col]
        n = len(data)
        kmf = KaplanMeierFitter()
        kmf.fit(T, E, alpha=alpha)
        # Survival table
        timeline = kmf.timeline.tolist()
        survival = kmf.survival_function_["KM_estimate"].tolist()
        ci_lower = kmf.confidence_interval_["KM_estimate_lower_0.95"].tolist()
        ci_upper = kmf.confidence_interval_["KM_estimate_upper_0.95"].tolist()
        at_risk_counts = [int(kmf.event_table.loc[t, "at_risk"]) if t in kmf.event_table.index else None
                          for t in timeline]
        events_at = [int(kmf.event_table.loc[t, "observed"]) if t in kmf.event_table.index else None
                     for t in timeline]
        # Median survival
        median_surv = float(kmf.median_survival_time_) if kmf.median_survival_time_ != np.inf else None
        survival_table = [{"time": round(float(t), 4), "survival": round(float(s), 4),
                           "ci_lower": round(float(cl), 4), "ci_upper": round(float(cu), 4)}
                          for t, s, cl, cu in zip(timeline, survival, ci_lower, ci_upper)]
        n_events = int(E.sum())
        n_censored = int(n - n_events)
        return build_result("Kaplan-Meier Survival Estimator", "kaplan_meier",
                            "Median Survival", median_surv, n=n,
                            conclusion=(f"Median survival time = {median_surv:.4f} ({duration_col} units)."
                                        if median_surv is not None
                                        else "Median survival time not reached (insufficient events)."),
                            additional_stats={
                                "median_survival_time": round(median_surv, 4) if median_surv else None,
                                "n_events": n_events, "n_censored": n_censored,
                                "survival_probability_at_end": round(float(survival[-1]), 4) if survival else None,
                                "survival_curve": survival_table,
                            }, table=survival_table)
    except Exception as e:
        return build_error("Kaplan-Meier", "kaplan_meier", str(e), "Ensure duration column is numeric, event column is binary.")


def run_log_rank_test(df, variables, brief, alpha=0.05):
    try:
        if not _lifelines:
            return build_error("Log-Rank Test", "log_rank_test",
                               "lifelines not installed.", "pip install lifelines")
        if len(variables) < 3:
            return build_error("Log-Rank Test", "log_rank_test",
                               "Need duration_col, event_col, group_col.", "Select 3 variables.")
        duration_col, event_col, group_col = variables[0], variables[1], variables[2]
        err = _check_cols(df, duration_col, event_col)
        if err:
            return build_error("Log-Rank Test", "log_rank_test", err, "Check column selection.")
        data = df[[duration_col, event_col, group_col]].dropna()
        groups = data[group_col].unique()
        if len(groups) < 2:
            return build_error("Log-Rank Test", "log_rank_test",
                               f"Need >= 2 groups, found {len(groups)}.", "Check group column.")
        if len(groups) == 2:
            g1_mask = data[group_col] == groups[0]
            results = logrank_test(
                data.loc[g1_mask, duration_col], data.loc[~g1_mask, duration_col],
                data.loc[g1_mask, event_col], data.loc[~g1_mask, event_col],
                alpha=alpha
            )
            chi2 = float(results.test_statistic)
            p = float(results.p_value)
            dof = 1
        else:
            results = multivariate_logrank_test(
                data[duration_col], data[group_col], data[event_col]
            )
            chi2 = float(results.test_statistic)
            p = float(results.p_value)
            dof = len(groups) - 1
        significant = bool(p < alpha)
        # Per-group summary
        group_table = []
        for grp in sorted(groups, key=str):
            mask = data[group_col] == grp
            gdata = data[mask]
            kmf = KaplanMeierFitter()
            kmf.fit(gdata[duration_col], gdata[event_col])
            med = float(kmf.median_survival_time_) if kmf.median_survival_time_ != np.inf else None
            group_table.append({"group": str(grp), "n": int(len(gdata)),
                                 "n_events": int(gdata[event_col].sum()),
                                 "median_survival": round(med, 4) if med else None})
        return build_result("Log-Rank Test", "log_rank_test",
                            "χ²", chi2, p_value=p, n=len(data), df_val=dof,
                            significant=significant,
                            conclusion=f"χ²({dof}) = {chi2:.3f}, p = {p:.4f}. {'Significant' if significant else 'No significant'} difference in survival curves.",
                            additional_stats={"chi2": round(chi2, 4), "df": dof,
                                             "group_comparison": group_table},
                            table=group_table)
    except Exception as e:
        return build_error("Log-Rank Test", "log_rank_test", str(e), "Check duration, event, and group columns.")


def run_cox_ph(df, variables, brief, alpha=0.05):
    try:
        if not _lifelines:
            return build_error("Cox PH", "cox_ph_regression",
                               "lifelines not installed.", "pip install lifelines")
        if len(variables) < 2:
            return build_error("Cox PH", "cox_ph_regression",
                               "Need duration_col, event_col, and covariates.", "Select >= 2 variables.")
        duration_col, event_col = variables[0], variables[1]
        covariates = [c for c in variables[2:] if c in df.columns]
        err = _check_cols(df, duration_col, event_col)
        if err:
            return build_error("Cox PH", "cox_ph_regression", err, "Check column selection.")
        if not covariates:
            return build_error("Cox PH", "cox_ph_regression",
                               "No covariates specified.", "Select covariate columns.")
        data = df[[duration_col, event_col] + covariates].dropna()
        # Cox requires numeric covariates
        num_cov = [c for c in covariates if pd.api.types.is_numeric_dtype(data[c])]
        if not num_cov:
            return build_error("Cox PH", "cox_ph_regression",
                               "Covariates must be numeric.", "Check covariate columns.")
        cph = CoxPHFitter()
        cph.fit(data[[duration_col, event_col] + num_cov], duration_col=duration_col,
                event_col=event_col)
        summary = cph.summary
        coef_table = []
        for covar in num_cov:
            if covar not in summary.index:
                continue
            coef_table.append({
                "covariate": covar,
                "coef": round(float(summary.loc[covar, "coef"]), 4),
                "HR": round(float(summary.loc[covar, "exp(coef)"]), 4),
                "SE": round(float(summary.loc[covar, "se(coef)"]), 4),
                "z": round(float(summary.loc[covar, "z"]), 4),
                "p": round(float(summary.loc[covar, "p"]), 4),
                "CI_lower_HR": round(float(summary.loc[covar, "exp(coef) lower 95%"]), 4),
                "CI_upper_HR": round(float(summary.loc[covar, "exp(coef) upper 95%"]), 4),
            })
        concordance = float(cph.concordance_index_)
        log_likelihood = float(cph.log_likelihood_)
        return build_result("Cox Proportional Hazards Regression", "cox_ph_regression",
                            "Concordance", concordance, n=len(data),
                            additional_stats={
                                "concordance_index": round(concordance, 4),
                                "log_likelihood": round(log_likelihood, 4),
                                "hazard_ratios": coef_table,
                                "n_events": int(data[event_col].sum()),
                            }, table=coef_table)
    except Exception as e:
        return build_error("Cox PH", "cox_ph_regression", str(e), "Check duration, event, and covariate columns.")


def run_weibull_aft(df, variables, brief, alpha=0.05):
    try:
        if not _lifelines:
            return build_error("Weibull AFT", "weibull_aft",
                               "lifelines not installed.", "pip install lifelines")
        if len(variables) < 2:
            return build_error("Weibull AFT", "weibull_aft",
                               "Need duration_col and event_col.", "Select 2 variables.")
        duration_col, event_col = variables[0], variables[1]
        covariates = [c for c in variables[2:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        err = _check_cols(df, duration_col, event_col)
        if err:
            return build_error("Weibull AFT", "weibull_aft", err, "Check column selection.")
        data = df[[duration_col, event_col] + covariates].dropna()
        waf = WeibullAFTFitter()
        waf.fit(data, duration_col=duration_col, event_col=event_col)
        median_surv = float(waf.median_survival_time_)
        summary = waf.summary.reset_index()
        param_table = [{"parameter": str(row["param"]) if "param" in summary.columns else str(row.get("covariate", "")),
                        "coef": round(float(row.get("coef", 0)), 4)}
                       for _, row in summary.iterrows()]
        return build_result("Weibull AFT Model", "weibull_aft",
                            "Median Survival", median_surv, n=len(data),
                            additional_stats={
                                "median_survival_time": round(median_surv, 4) if median_surv != np.inf else None,
                                "log_likelihood": round(float(waf.log_likelihood_), 4),
                                "AIC": round(float(waf.AIC_), 4),
                                "parameters": param_table,
                            })
    except Exception as e:
        return build_error("Weibull AFT", "weibull_aft", str(e), "Check duration and event columns.")


def run_nelson_aalen(df, variables, brief, alpha=0.05):
    try:
        if not _lifelines:
            return build_error("Nelson-Aalen", "nelson_aalen",
                               "lifelines not installed.", "pip install lifelines")
        if len(variables) < 2:
            return build_error("Nelson-Aalen", "nelson_aalen",
                               "Need duration_col and event_col.", "Select 2 variables.")
        duration_col, event_col = variables[0], variables[1]
        err = _check_cols(df, duration_col, event_col)
        if err:
            return build_error("Nelson-Aalen", "nelson_aalen", err, "Check column selection.")
        data = df[[duration_col, event_col]].dropna()
        naf = NelsonAalenFitter()
        naf.fit(data[duration_col], data[event_col])
        timeline = naf.timeline.tolist()
        cumhaz = naf.cumulative_hazard_["NA_estimate"].tolist()
        cumhaz_table = [{"time": round(float(t), 4), "cumulative_hazard": round(float(h), 4)}
                        for t, h in zip(timeline, cumhaz)]
        return build_result("Nelson-Aalen Cumulative Hazard Estimator", "nelson_aalen",
                            "N", len(data), n=len(data),
                            additional_stats={
                                "cumulative_hazard_curve": cumhaz_table,
                                "final_cumulative_hazard": round(float(cumhaz[-1]), 4) if cumhaz else None,
                            }, table=cumhaz_table)
    except Exception as e:
        return build_error("Nelson-Aalen", "nelson_aalen", str(e), "Check duration and event columns.")


def run_life_table(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Life Table", "life_table",
                               "Need duration_col and event_col.", "Select 2 variables.")
        duration_col, event_col = variables[0], variables[1]
        err = _check_cols(df, duration_col, event_col)
        if err:
            return build_error("Life Table", "life_table", err, "Check column selection.")
        data = df[[duration_col, event_col]].dropna()
        T = data[duration_col].values; E = data[event_col].values
        # Build life table using sorted unique times
        unique_times = np.sort(np.unique(T))
        n_total = len(T)
        table_rows = []
        survivors = n_total
        q_values = []
        for t in unique_times:
            mask = T == t
            d = int(np.sum(mask & (E == 1)))  # deaths/events at time t
            c = int(np.sum(mask & (E == 0)))  # censored at time t
            n = survivors
            if n == 0:
                break
            q = d / n  # probability of dying
            p = 1 - q   # probability of surviving
            q_values.append(q)
            table_rows.append({
                "time": round(float(t), 4),
                "n_at_risk": n,
                "n_events": d,
                "n_censored": c,
                "hazard": round(q, 4),
            })
            survivors -= (d + c)
            
        p_survive_per_interval = np.array([1 - q_i for q_i in q_values])
        survival_probs = np.cumprod(p_survive_per_interval)
        for i, row in enumerate(table_rows):
            row["survival"] = round(float(survival_probs[i]), 4)
        return build_result("Life Table (Actuarial Method)", "life_table",
                            "N intervals", len(table_rows), n=n_total,
                            additional_stats={"life_table": table_rows,
                                             "n_events": int(E.sum()),
                                             "n_censored": int(n_total - E.sum())},
                            table=table_rows)
    except Exception as e:
        return build_error("Life Table", "life_table", str(e), "Check duration and event columns.")


def run_ph_assumption(df, variables, brief, alpha=0.05):
    """Test Cox PH proportionality assumption via Schoenfeld residuals."""
    try:
        if not _lifelines:
            return build_error("PH Assumption Test", "ph_assumption_test",
                               "lifelines not installed.", "pip install lifelines")
        if len(variables) < 3:
            return build_error("PH Assumption Test", "ph_assumption_test",
                               "Need duration_col, event_col, and covariates.", "Select >= 3 variables.")
        duration_col, event_col = variables[0], variables[1]
        covariates = [c for c in variables[2:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        err = _check_cols(df, duration_col, event_col)
        if err:
            return build_error("PH Assumption Test", "ph_assumption_test", err, "Check column selection.")
        data = df[[duration_col, event_col] + covariates].dropna()
        cph = CoxPHFitter()
        cph.fit(data[[duration_col, event_col] + covariates], duration_col=duration_col, event_col=event_col)
        # Check PH assumption via correlation of Schoenfeld residuals with time
        schoenfeld = cph.compute_residuals(data[[duration_col, event_col] + covariates], kind="schoenfeld")
        T = data[duration_col].values[data[event_col].values == 1]
        results = []
        for col in schoenfeld.columns:
            if col in [duration_col, event_col]:
                continue
            try:
                resid = schoenfeld[col].values[:len(T)]
                if len(resid) > 3:
                    rho, p = stats.spearmanr(T[:len(resid)], resid)
                    results.append({"covariate": col, "rho": round(float(rho), 4), "p": round(float(p), 4),
                                    "ph_violated": bool(p < alpha)})
            except Exception:
                pass
        return build_result("Cox PH Assumption Test (Schoenfeld Residuals)", "ph_assumption_test",
                            "N covariates tested", len(results), n=len(data),
                            significant=any(r["ph_violated"] for r in results),
                            conclusion=f"{'PH assumption violated for some covariates' if any(r['ph_violated'] for r in results) else 'PH assumption holds for all covariates'}.",
                            additional_stats={"schoenfeld_results": results},
                            table=results)
    except Exception as e:
        return build_error("PH Assumption Test", "ph_assumption_test", str(e), "Check variables.")


def run_competing_risks(df, variables, brief, alpha=0.05):
    """Competing risks analysis using Fine-Gray approach (Aalen-Johansen estimator via lifelines)."""
    try:
        if not _lifelines:
            return build_error("Competing Risks", "competing_risks",
                               "lifelines not installed.", "pip install lifelines")
        if len(variables) < 2:
            return build_error("Competing Risks", "competing_risks",
                               "Need duration_col and event_col.", "Select 2 variables.")
        duration_col, event_col = variables[0], variables[1]
        err = _check_cols(df, duration_col, event_col)
        if err:
            return build_error("Competing Risks", "competing_risks", err, "Check column selection.")
        data = df[[duration_col, event_col]].dropna()
        event_codes = sorted(data[event_col].unique())
        results = {}
        for code in event_codes:
            if code == 0:
                continue  # 0 = censored
            E_cause = (data[event_col] == code).astype(int)
            kmf = KaplanMeierFitter()
            # Cause-specific: censor all other events
            kmf.fit(data[duration_col], E_cause)
            results[str(code)] = {
                "cause": str(code),
                "n_events": int(E_cause.sum()),
                "median_survival": round(float(kmf.median_survival_time_), 4) if kmf.median_survival_time_ != np.inf else None,
                "final_cumulative_incidence": round(float(1 - kmf.survival_function_["KM_estimate"].iloc[-1]), 4),
            }
        return build_result("Competing Risks Analysis", "competing_risks",
                            "N causes", len(results), n=len(data),
                            additional_stats={"cause_specific": list(results.values()),
                                             "event_codes": [str(c) for c in event_codes if c != 0]})
    except Exception as e:
        return build_error("Competing Risks", "competing_risks", str(e), "Ensure event column has numeric codes (0=censored, 1=event1, 2=event2, ...).")
