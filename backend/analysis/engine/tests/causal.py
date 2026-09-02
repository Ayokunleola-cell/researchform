# backend/analysis/engine/tests/causal.py
"""Causal inference methods — DiD, IV, PSM, RDD, Bayesian AB."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error

try:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
except ImportError:
    sm = None; smf = None

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.neighbors import NearestNeighbors
    _sklearn = True
except ImportError:
    _sklearn = False


def _num_cols(df, variables):
    return [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]


def run_difference_in_differences(df, variables, brief, alpha=0.05):
    """Difference-in-Differences (DiD) causal estimator."""
    try:
        if sm is None:
            return build_error("DiD", "difference_in_differences",
                               "statsmodels not installed.", "pip install statsmodels")
        # Required: outcome, treatment (0/1), time (0/1 for pre/post), optional: covariates
        if len(variables) < 3:
            return build_error("DiD", "difference_in_differences",
                               "Need outcome_col, treatment_col, time_col.", "Select 3 variables.")
        outcome_col, treatment_col, time_col = variables[0], variables[1], variables[2]
        covariates = [c for c in variables[3:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        missing = [c for c in [outcome_col, treatment_col, time_col] if c not in df.columns]
        if missing:
            return build_error("DiD", "difference_in_differences",
                               f"Columns not found: {missing}", "Check column names.")
        data = df[[outcome_col, treatment_col, time_col] + covariates].dropna()
        data = data.copy()
        data["_treat_x_time"] = data[treatment_col] * data[time_col]
        rhs = [treatment_col, time_col, "_treat_x_time"] + covariates
        X = sm.add_constant(data[rhs].astype(float))
        model = sm.OLS(data[outcome_col].astype(float), X).fit(
            cov_type="HC3"  # Robust SE
        )
        did_estimate = float(model.params["_treat_x_time"])
        did_p = float(model.pvalues["_treat_x_time"])
        did_se = float(model.bse["_treat_x_time"])
        ci = model.conf_int()
        did_ci_l = float(ci.loc["_treat_x_time", 0])
        did_ci_u = float(ci.loc["_treat_x_time", 1])
        # Pre/post means per group
        pre_treat = data[(data[time_col] == 0) & (data[treatment_col] == 1)][outcome_col].mean()
        post_treat = data[(data[time_col] == 1) & (data[treatment_col] == 1)][outcome_col].mean()
        pre_control = data[(data[time_col] == 0) & (data[treatment_col] == 0)][outcome_col].mean()
        post_control = data[(data[time_col] == 1) & (data[treatment_col] == 0)][outcome_col].mean()
        naive_did = float((post_treat - pre_treat) - (post_control - pre_control))
        return build_result("Difference-in-Differences (DiD)", "difference_in_differences",
                            "DiD estimate", did_estimate, p_value=did_p, n=len(data),
                            significant=bool(did_p < alpha),
                            ci_lower=did_ci_l, ci_upper=did_ci_u,
                            conclusion=f"DiD = {did_estimate:.4f} (SE={did_se:.4f}, p={did_p:.4f}). {'Significant' if did_p<alpha else 'Non-significant'} treatment effect.",
                            additional_stats={
                                "did_estimate": round(did_estimate, 4),
                                "did_se_robust": round(did_se, 4),
                                "did_p": round(did_p, 4),
                                "naive_did": round(naive_did, 4),
                                "group_means": {
                                    "treat_pre": round(float(pre_treat), 4) if not np.isnan(pre_treat) else None,
                                    "treat_post": round(float(post_treat), 4) if not np.isnan(post_treat) else None,
                                    "control_pre": round(float(pre_control), 4) if not np.isnan(pre_control) else None,
                                    "control_post": round(float(post_control), 4) if not np.isnan(post_control) else None,
                                },
                                "r_squared": round(float(model.rsquared), 4),
                            })
    except Exception as e:
        return build_error("DiD", "difference_in_differences", str(e), "Check outcome, treatment (0/1), and time (0/1) columns.")


def run_instrumental_variables(df, variables, brief, alpha=0.05):
    """Two-Stage Least Squares (2SLS) Instrumental Variables."""
    try:
        if sm is None:
            return build_error("IV (2SLS)", "instrumental_variables",
                               "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 3:
            return build_error("IV (2SLS)", "instrumental_variables",
                               "Need outcome_col, endogenous_col, instrument_col.", "Select 3 variables.")
        outcome_col, endog_col, instr_col = variables[0], variables[1], variables[2]
        controls = [c for c in variables[3:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        data = df[[outcome_col, endog_col, instr_col] + controls].dropna().astype(float)
        n = len(data)
        if n < 10:
            return build_error("IV (2SLS)", "instrumental_variables",
                               f"Too few observations (n={n}). Need >= 10.", "Use more data.")
        # Stage 1: regress endog on instrument + controls
        stage1_X = sm.add_constant(data[[instr_col] + controls])
        stage1 = sm.OLS(data[endog_col], stage1_X).fit()
        data["_endog_hat"] = stage1.fittedvalues
        F_first = float(stage1.fvalue)
        # First-stage F < 10 = weak instrument
        # Stage 2: regress outcome on predicted endog + controls
        stage2_X = sm.add_constant(data[["_endog_hat"] + controls])
        stage2 = sm.OLS(data[outcome_col], stage2_X).fit()
        tsls_coef = float(stage2.params["_endog_hat"])
        tsls_p = float(stage2.pvalues["_endog_hat"])
        ci = stage2.conf_int()
        tsls_ci_l = float(ci.loc["_endog_hat", 0])
        tsls_ci_u = float(ci.loc["_endog_hat", 1])
        ols_X = sm.add_constant(data[[endog_col] + controls])
        ols_model = sm.OLS(data[outcome_col], ols_X).fit()
        ols_coef = float(ols_model.params[endog_col])
        
        coef_table = [{"predictor": k, "coef": v} for k, v in stage2.params.items()]
        se_note = ""
        try:
            n_obs = len(data)
            X2 = stage2_X.values  # design matrix from stage 2
            e2 = stage2.resid.values       # residuals from stage 2
            # Use HC0 sandwich: (X'X)^{-1} X' diag(e^2) X (X'X)^{-1}
            XtX_inv = np.linalg.pinv(X2.T @ X2)
            meat = X2.T @ np.diag(e2**2) @ X2
            sandwich = XtX_inv @ meat @ XtX_inv
            corrected_se = np.sqrt(np.diag(sandwich))
            # Replace the SEs in the coef table with corrected ones
            for i, row in enumerate(coef_table):
                if i < len(corrected_se):
                    row['SE_2sls'] = round(float(corrected_se[i]), 4)
                    row['t_2sls'] = round(float(row.get('b', row.get('coef', 0)) / corrected_se[i]), 4) if corrected_se[i] > 0 else None
            se_note = '2SLS standard errors corrected via HC0 sandwich estimator.'
        except Exception as _se_err:
            se_note = f'2SLS SE correction failed: {_se_err}. Reported SEs from stage-2 OLS are not valid.'

        return build_result("Instrumental Variables (2SLS)", "instrumental_variables",
                            "2SLS estimate", tsls_coef, p_value=tsls_p, n=n,
                            significant=bool(tsls_p < alpha),
                            ci_lower=tsls_ci_l, ci_upper=tsls_ci_u,
                            conclusion=f"2SLS estimate = {tsls_coef:.4f} (p = {tsls_p:.4f}). {'Weak instrument warning.' if F_first < 10 else 'First stage F > 10 (strong instrument).'}",
                            additional_stats={
                                "tsls_coef": round(tsls_coef, 4),
                                "ols_coef_for_comparison": round(ols_coef, 4),
                                "first_stage_F": round(F_first, 4),
                                "weak_instrument": F_first < 10,
                                "first_stage_r_squared": round(float(stage1.rsquared), 4),
                                "se_note": se_note,
                                "coefficients": coef_table,
                            })
    except Exception as e:
        return build_error("IV (2SLS)", "instrumental_variables", str(e),
                           "Ensure outcome, endogenous, and instrument columns are numeric.")


def run_propensity_score_matching(df, variables, brief, alpha=0.05):
    """Propensity Score Matching (PSM) for observational causal inference."""
    try:
        if not _sklearn:
            return build_error("PSM", "propensity_score_matching",
                               "scikit-learn not installed.", "pip install scikit-learn")
        if len(variables) < 3:
            return build_error("PSM", "propensity_score_matching",
                               "Need treatment_col, outcome_col, covariate(s).", "Select >= 3 variables.")
        treatment_col, outcome_col = variables[0], variables[1]
        covariates = [c for c in variables[2:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if not covariates:
            return build_error("PSM", "propensity_score_matching",
                               "No numeric covariates found.", "Select covariate columns.")
        data = df[[treatment_col, outcome_col] + covariates].dropna()
        n = len(data)
        T = data[treatment_col].values.astype(int)
        Y = data[outcome_col].values.astype(float)
        X = data[covariates].values
        # Estimate propensity scores
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        lr = LogisticRegression(max_iter=500, random_state=42)
        lr.fit(X_scaled, T)
        pscore = lr.predict_proba(X_scaled)[:, 1]
        # 1:1 nearest-neighbor matching without replacement
        treated_idx = np.where(T == 1)[0]
        control_idx = np.where(T == 0)[0]
        ps_treated = pscore[treated_idx].reshape(-1, 1)
        ps_control = pscore[control_idx].reshape(-1, 1)
        nn = NearestNeighbors(n_neighbors=1, algorithm="ball_tree")
        nn.fit(ps_control)
        distances, indices = nn.kneighbors(ps_treated)
        matched_control_idx = control_idx[indices.flatten()]
        # Deduplicate to enforce without-replacement matching
        seen = set()
        matched_ctrl_unique = []
        treated_unique = []
        for t_idx, c_idx in zip(treated_idx, matched_control_idx):
            if c_idx not in seen:
                seen.add(c_idx)
                matched_ctrl_unique.append(c_idx)
                treated_unique.append(t_idx)
        matched_control_idx = np.array(matched_ctrl_unique)
        treated_idx = np.array(treated_unique)
        # ATT: Average Treatment Effect on Treated
        Y_treat = Y[treated_idx]
        Y_matched_control = Y[matched_control_idx]
        att = float(np.mean(Y_treat - Y_matched_control))
        t_stat, p_val = stats.ttest_rel(Y_treat, Y_matched_control)
        n_matched = len(treated_idx)
        # Covariate balance AFTER matching
        balance = []
        for i, col in enumerate(covariates):
            x_treat = X[treated_idx, i]
            x_control = X[matched_control_idx, i]
            smd_before = float((np.mean(X[treated_idx, i]) - np.mean(X[control_idx, i])) /
                               np.std(X[:, i])) if np.std(X[:, i]) > 0 else 0
            smd_after = float((np.mean(x_treat) - np.mean(x_control)) /
                              np.std(X[:, i])) if np.std(X[:, i]) > 0 else 0
            balance.append({"covariate": col, "smd_before": round(smd_before, 4), "smd_after": round(smd_after, 4)})
        return build_result("Propensity Score Matching (PSM)", "propensity_score_matching",
                            "ATT", att, p_value=p_val, n=n,
                            significant=bool(p_val < alpha),
                            conclusion=f"ATT = {att:.4f}, p = {p_val:.4f} ({n_matched} matched pairs). {'Significant' if p_val<alpha else 'Non-significant'} treatment effect.",
                            additional_stats={
                                "att": round(att, 4),
                                "t_statistic": round(float(t_stat), 4),
                                "n_treated": int(len(treated_idx)),
                                "n_control": int(len(control_idx)),
                                "n_matched_pairs": n_matched,
                                "covariate_balance": balance,
                                "max_smd_after": round(max(abs(b["smd_after"]) for b in balance), 4) if balance else None,
                            }, table=balance)
    except Exception as e:
        return build_error("PSM", "propensity_score_matching", str(e),
                           "Check treatment (binary), outcome, and covariate columns.")


def run_rdd(df, variables, brief, alpha=0.05):
    """Regression Discontinuity Design (RDD) — local linear approach."""
    try:
        if sm is None:
            return build_error("RDD", "regression_discontinuity",
                               "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("RDD", "regression_discontinuity",
                               "Need outcome_col and running_variable_col.", "Select 2 numeric columns.")
        outcome_col, running_col = variables[0], variables[1]
        threshold = float(brief.get("rdd_threshold", 0) or df[running_col].median())
        bandwidth = brief.get("rdd_bandwidth")
        data = df[[outcome_col, running_col]].dropna()
        data = data.copy()
        data["_D"] = (data[running_col] >= threshold).astype(int)
        data["_X_c"] = data[running_col] - threshold
        if bandwidth:
            bw = float(bandwidth)
            data = data[data[running_col].between(threshold - bw, threshold + bw)]
        if len(data) < 10:
            return build_error("RDD", "regression_discontinuity",
                               f"Too few obs in bandwidth (n={len(data)}).", "Widen bandwidth or check threshold.")
        # Local linear regression: Y ~ D + X_c + D*X_c
        data["_DX"] = data["_D"] * data["_X_c"]
        X = sm.add_constant(data[["_D", "_X_c", "_DX"]].astype(float))
        model = sm.OLS(data[outcome_col].astype(float), X).fit(cov_type="HC3")
        rdd_estimate = float(model.params["_D"])
        rdd_p = float(model.pvalues["_D"])
        rdd_se = float(model.bse["_D"])
        ci = model.conf_int()
        ci_l, ci_u = float(ci.loc["_D", 0]), float(ci.loc["_D", 1])
        return build_result("Regression Discontinuity Design (RDD)", "regression_discontinuity",
                            "RD estimate", rdd_estimate, p_value=rdd_p, n=len(data),
                            significant=bool(rdd_p < alpha),
                            ci_lower=ci_l, ci_upper=ci_u,
                            conclusion=f"RD = {rdd_estimate:.4f} (SE={rdd_se:.4f}, p={rdd_p:.4f}) at threshold={threshold}. {'Significant discontinuity' if rdd_p<alpha else 'No significant discontinuity'}.",
                            additional_stats={
                                "rd_estimate": round(rdd_estimate, 4),
                                "threshold": threshold,
                                "bandwidth": bandwidth,
                                "n_below_threshold": int((data["_D"] == 0).sum()),
                                "n_above_threshold": int((data["_D"] == 1).sum()),
                                "r_squared": round(float(model.rsquared), 4),
                            })
    except Exception as e:
        return build_error("RDD", "regression_discontinuity", str(e),
                           "Check outcome and running variable columns. Provide rdd_threshold in brief.")


def run_bayesian_ab(df, variables, brief, alpha=0.05):
    """Bayesian A/B test — Beta-Binomial for conversion rates."""
    try:
        if len(variables) < 2:
            return build_error("Bayesian A/B", "bayesian_ab_test",
                               "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        if group_col not in df.columns or outcome_col not in df.columns:
            return build_error("Bayesian A/B", "bayesian_ab_test",
                               "Columns not found.", "Check column names.")
        data = df[[group_col, outcome_col]].dropna()
        groups = data[group_col].unique()
        if len(groups) != 2:
            return build_error("Bayesian A/B", "bayesian_ab_test",
                               f"Expected 2 groups, found {len(groups)}.", "Ensure 2 variants.")
        g_a, g_b = str(groups[0]), str(groups[1])
        vals_a = data[data[group_col] == groups[0]][outcome_col].astype(float)
        vals_b = data[data[group_col] == groups[1]][outcome_col].astype(float)
        # Beta-Binomial if binary outcome
        is_binary = set(data[outcome_col].unique()).issubset({0, 1, 0.0, 1.0})
        if is_binary:
            alpha_prior, beta_prior = 1, 1  # Uniform Beta prior
            a_a = int(vals_a.sum()) + alpha_prior
            b_a = int(len(vals_a) - vals_a.sum()) + beta_prior
            a_b = int(vals_b.sum()) + alpha_prior
            b_b = int(len(vals_b) - vals_b.sum()) + beta_prior
            # Monte Carlo estimation
            n_samples = 100_000
            rng = np.random.default_rng(42)
            samples_a = rng.beta(a_a, b_a, n_samples)
            samples_b = rng.beta(a_b, b_b, n_samples)
            prob_b_better = float(np.mean(samples_b > samples_a))
            lift = float(np.mean((samples_b - samples_a) / (samples_a + 1e-10)))
            expected_a = float(a_a / (a_a + b_a))
            expected_b = float(a_b / (a_b + b_b))
            credible_diff_l = float(np.percentile(samples_b - samples_a, 2.5))
            credible_diff_u = float(np.percentile(samples_b - samples_a, 97.5))
        else:
            # Normal approximation for continuous outcomes
            n_samples = 100_000
            rng = np.random.default_rng(42)
            mu_a, se_a = float(vals_a.mean()), float(vals_a.sem())
            mu_b, se_b = float(vals_b.mean()), float(vals_b.sem())
            samples_a = rng.normal(mu_a, se_a, n_samples)
            samples_b = rng.normal(mu_b, se_b, n_samples)
            prob_b_better = float(np.mean(samples_b > samples_a))
            lift = float(np.mean((samples_b - samples_a) / (np.abs(samples_a) + 1e-10)))
            expected_a, expected_b = mu_a, mu_b
            credible_diff_l = float(np.percentile(samples_b - samples_a, 2.5))
            credible_diff_u = float(np.percentile(samples_b - samples_a, 97.5))
        # Also run frequentist for reference
        if is_binary:
            _, p_freq = stats.chi2_contingency([[int(vals_a.sum()), int(len(vals_a) - vals_a.sum())],
                                                 [int(vals_b.sum()), int(len(vals_b) - vals_b.sum())]])[:2]
        else:
            _, p_freq = stats.ttest_ind(vals_a, vals_b)
        winner = g_b if prob_b_better > 0.95 else (g_a if prob_b_better < 0.05 else "inconclusive")
        return build_result("Bayesian A/B Test", "bayesian_ab_test",
                            "P(B > A)", prob_b_better, n=len(data),
                            significant=bool(winner != "inconclusive"),
                            conclusion=f"P(B > A) = {prob_b_better:.4f}. Lift = {lift:.2%}. Winner: {winner}.",
                            additional_stats={
                                "group_a": g_a, "group_b": g_b,
                                "expected_rate_a": round(expected_a, 4),
                                "expected_rate_b": round(expected_b, 4),
                                "prob_b_better_than_a": round(prob_b_better, 4),
                                "expected_lift": round(lift, 4),
                                "credible_interval_diff": [round(credible_diff_l, 4), round(credible_diff_u, 4)],
                                "frequentist_p": round(float(p_freq), 4),
                                "winner": winner,
                                "outcome_type": "binary" if is_binary else "continuous",
                            })
    except Exception as e:
        return build_error("Bayesian A/B", "bayesian_ab_test", str(e),
                           "Check group (2 variants) and outcome columns.")


def run_synthetic_control(df, variables, brief, alpha=0.05):
    """Synthetic Control Method — builds a weighted control group from donor pool."""
    try:
        if sm is None:
            return build_error("Synthetic Control", "synthetic_control",
                               "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 3:
            return build_error("Synthetic Control", "synthetic_control",
                               "Need outcome_col, time_col, unit_col (and optionally treatment_unit in brief).",
                               "Select 3 variables: outcome, time, unit.")
        outcome_col, time_col, unit_col = variables[0], variables[1], variables[2]
        # treatment_unit can be 4th variable value OR provided in brief
        treatment_unit = str(
            brief.get("treatment_unit",
                      variables[3] if len(variables) >= 4 else df[unit_col].iloc[0])
        )
        treatment_period = brief.get("treatment_period")
        data = df[[outcome_col, time_col, unit_col]].dropna()
        # Pivot to wide format: rows=time, cols=units
        wide = data.pivot_table(index=time_col, columns=unit_col, values=outcome_col)
        if treatment_unit not in wide.columns:
            return build_error("Synthetic Control", "synthetic_control",
                               f"Treatment unit '{treatment_unit}' not found in {unit_col}.", "Check treatment_unit in brief.")
        donor_cols = [c for c in wide.columns if c != treatment_unit]
        if not donor_cols:
            return build_error("Synthetic Control", "synthetic_control",
                               "No donor units available.", "Need multiple units in unit_col.")
        Y_treated = wide[treatment_unit].values
        Y_donors = wide[donor_cols].values
        # Determine pre/post treatment periods
        if treatment_period is not None:
            pre_mask = wide.index < treatment_period
        else:
            mid = len(wide) // 2
            pre_mask = np.arange(len(wide)) < mid
        Y_pre_treated = Y_treated[pre_mask]
        Y_pre_donors = Y_donors[pre_mask, :]
        # Optimal weights via least squares (constrained to sum to 1, non-negative)
        from scipy.optimize import minimize
        def objective(w):
            synth = Y_pre_donors @ w
            return float(np.sum((Y_pre_treated - synth)**2))
        n_donors = len(donor_cols)
        w0 = np.ones(n_donors) / n_donors
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
        bounds = [(0, 1)] * n_donors
        opt = minimize(objective, w0, constraints=cons, bounds=bounds, method="SLSQP",
                       options={"maxiter": 1000, "ftol": 1e-9})
        weights = opt.x
        converged = bool(opt.success)
        Y_synthetic = Y_donors @ weights
        # RMSPE pre-treatment
        rmspe_pre = float(np.sqrt(np.mean((Y_pre_treated - Y_synthetic[pre_mask])**2)))
        post_mask = ~pre_mask
        att_post = float(np.mean(Y_treated[post_mask] - Y_synthetic[post_mask])) if post_mask.any() else None
        convergence_note = "" if converged else f" [Warning: Optimizer did not converge ({opt.message}). Weights may be suboptimal.]"
        return build_result("Synthetic Control Method", "synthetic_control",
                            "ATT (post)", att_post, n=len(data),
                            conclusion=f"ATT (post-treatment) = {att_post:.4f}. RMSPE pre = {rmspe_pre:.4f}.{convergence_note}",
                            additional_stats={
                                "treatment_unit": treatment_unit,
                                "donor_weights": {str(d): round(float(w), 4) for d, w in zip(donor_cols, weights) if w > 0.001},
                                "att_post_treatment": round(att_post, 4) if att_post is not None else None,
                                "rmspe_pre_treatment": round(rmspe_pre, 4),
                                "n_donors": n_donors,
                                "optimizer_converged": converged,
                                "optimizer_message": opt.message if not converged else "Converged successfully",
                            })
    except Exception as e:
        return build_error("Synthetic Control", "synthetic_control", str(e),
                           "Need outcome, time, unit columns and treatment_unit in brief.")


def run_sensitivity_analysis(df, variables, brief, alpha=0.05):
    """Sensitivity analysis via Rosenbaum bounds for matched studies."""
    try:
        if len(variables) < 2:
            return build_error("Sensitivity Analysis", "sensitivity_analysis",
                               "Need outcome_treated and outcome_control columns.", "Select 2 matched outcome columns.")
        y_treat_col, y_control_col = variables[0], variables[1]
        data = df[[y_treat_col, y_control_col]].dropna()
        if len(data) < 5:
            return build_error("Sensitivity Analysis", "sensitivity_analysis",
                               f"Too few matched pairs (n={len(data)}).", "Need >= 5 pairs.")
        y_treat = data[y_treat_col].values
        y_control = data[y_control_col].values
        diff = y_treat - y_control
        n = len(diff)
        _, p_0 = stats.wilcoxon(y_treat, y_control)
        gamma_values = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
        bounds = []
        for gamma in gamma_values:
            p_max = gamma / (1 + gamma)  # upper bound on assignment prob
            p_min = 1 / (1 + gamma)
            # Rosenbaum: compute upper bound p-value (worst case)
            T_obs = float(np.sum(diff[diff > 0]))  # Wilcoxon signed rank test stat
            E_T = float(n * (n + 1) / 4 * (p_max - p_min + 1))
            # Simplified approximation
            p_upper = float(min(1.0, p_0 * gamma))
            bounds.append({
                "gamma": gamma,
                "p_upper": round(p_upper, 4),
                "still_significant": bool(p_upper < alpha),
            })
        # Gamma at which significance is lost
        critical_gamma = next((b["gamma"] for b in bounds if not b["still_significant"]), None)
        return build_result("Rosenbaum Sensitivity Analysis", "sensitivity_analysis",
                            "Γ*", critical_gamma, n=n,
                            additional_stats={
                                "original_p": round(float(p_0), 4),
                                "critical_gamma": critical_gamma,
                                "sensitivity_table": bounds,
                                "interpretation": f"Results robust to hidden bias up to Γ = {critical_gamma}." if critical_gamma else "Results not robust to hidden bias.",
                            }, table=bounds)
    except Exception as e:
        return build_error("Sensitivity Analysis", "sensitivity_analysis", str(e),
                           "Check matched pair outcome columns.")
