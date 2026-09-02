# backend/analysis/engine/tests/nonparametric.py
"""Non-parametric tests — Mann-Whitney, Wilcoxon, Kruskal-Wallis, Chi-Square, etc."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error, interpret_effect_size


def _split_groups(df, group_col, outcome_col):
    groups = {}
    for name, grp in df.groupby(group_col):
        s = grp[outcome_col].dropna()
        if len(s) >= 2:
            groups[str(name)] = s
    return groups


def run_mann_whitney(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Mann-Whitney U", "mann_whitney", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        groups = _split_groups(df, group_col, outcome_col)
        if len(groups) != 2:
            return build_error("Mann-Whitney U", "mann_whitney", f"Expected 2 groups, found {len(groups)}.", "Check grouping variable.")
        g1, g2 = list(groups.values())
        g1_name, g2_name = list(groups.keys())
        U, p = stats.mannwhitneyu(g1, g2, alternative="two-sided")
        n1, n2 = len(g1), len(g2)
        N = n1 + n2
        # Effect size r = Z / sqrt(N)
        Z = float(stats.norm.ppf(p / 2)) if p < 1 else 0.0
        r = abs(Z) / np.sqrt(N)
        interp = "small" if r < 0.3 else ("medium" if r < 0.5 else "large")
        return build_result("Mann-Whitney U Test", "mann_whitney",
                            "U", U, p_value=p, n=N,
                            significant=bool(p < alpha),
                            effect_size_name="r", effect_size_value=r,
                            effect_size_interpretation=interp,
                            conclusion=f"{g1_name} (Mdn={g1.median():.3f}) vs {g2_name} (Mdn={g2.median():.3f}): {'significant' if p<alpha else 'not significant'}.",
                            additional_stats={"U": round(float(U), 4), "Z": round(Z, 4), "r": round(float(r), 4),
                                             g1_name: {"median": round(float(g1.median()), 4), "n": n1},
                                             g2_name: {"median": round(float(g2.median()), 4), "n": n2}})
    except Exception as e:
        return build_error("Mann-Whitney U", "mann_whitney", str(e), "Check group and outcome columns.")


def run_mann_whitney_r(df, variables, brief, alpha=0.05):
    """Standalone effect size r for Mann-Whitney."""
    result = run_mann_whitney(df, variables, brief, alpha)
    if result.get("error"):
        return result
    r = result.get("effect_size", {}).get("value")
    return build_result("Mann-Whitney Effect Size (r)", "mann_whitney_r",
                        "r", r, n=result.get("n"),
                        effect_size_name="r", effect_size_value=r,
                        effect_size_interpretation=result.get("effect_size", {}).get("interpretation"),
                        additional_stats={"r": round(float(r), 4) if r else None})


def run_wilcoxon(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Wilcoxon Signed-Rank", "wilcoxon", "Need pre and post columns.", "Select 2 paired columns.")
        pre_col, post_col = variables[0], variables[1]
        data = df[[pre_col, post_col]].dropna()
        pre, post = data[pre_col].values, data[post_col].values
        diff = post - pre
        non_zero = diff[diff != 0]
        if len(non_zero) == 0:
            return build_error("Wilcoxon", "wilcoxon", "All differences are zero.", "Check the pre/post columns for variation.")
        W, p = stats.wilcoxon(pre, post)
        n = len(non_zero)
        N = len(data)
        Z = stats.norm.ppf(p / 2) if p < 1 else 0.0
        r = abs(Z) / np.sqrt(N)
        n_zeros = int(np.sum(diff == 0))
        return build_result("Wilcoxon Signed-Rank Test", "wilcoxon",
                            "W", W, p_value=p, n=N,
                            significant=bool(p < alpha),
                            effect_size_name="r", effect_size_value=r,
                            effect_size_interpretation="small" if r < 0.3 else ("medium" if r < 0.5 else "large"),
                            conclusion=f"{'Significant' if p<alpha else 'Non-significant'} difference between {pre_col} and {post_col}.",
                            additional_stats={"W": round(float(W), 4), "Z": round(float(Z), 4),
                                             "r": round(float(r), 4), "n_pairs": N, "n_zeros": n_zeros})
    except Exception as e:
        return build_error("Wilcoxon", "wilcoxon", str(e), "Check paired columns are numeric.")


def run_wilcoxon_r(df, variables, brief, alpha=0.05):
    result = run_wilcoxon(df, variables, brief, alpha)
    if result.get("error"):
        return result
    r = result.get("effect_size", {}).get("value")
    return build_result("Wilcoxon Effect Size (r)", "wilcoxon_r", "r", r, n=result.get("n"),
                        effect_size_name="r", effect_size_value=r,
                        additional_stats={"r": round(float(r), 4) if r else None})


def run_kruskal_wallis(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Kruskal-Wallis", "kruskal_wallis", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        groups = _split_groups(df, group_col, outcome_col)
        if len(groups) < 3:
            return build_error("Kruskal-Wallis", "kruskal_wallis", f"Need >= 3 groups, found {len(groups)}.", "Check grouping variable.")
        H, p = stats.kruskal(*list(groups.values()))
        k = len(groups); n = sum(len(g) for g in groups.values())
        # Effect size: eta² = (H - k + 1) / (n - k)
        eta2 = float((H - k + 1) / (n - k)) if n > k else 0.0
        eta2 = max(0, eta2)

        # Compute mean ranks properly
        all_vals = pd.concat([g.rename(name) for name, g in groups.items()]).reset_index(drop=True)
        all_df = pd.DataFrame({"value": pd.concat(list(groups.values())).values,
                               "group": np.repeat(list(groups.keys()), [len(g) for g in groups.values()])})
        all_df["rank"] = all_df["value"].rank()
        group_table = [{"group": name, "n": int(len(g)), "median": round(float(g.median()), 4),
                        "mean_rank": round(float(all_df[all_df["group"] == name]["rank"].mean()), 4)}
                       for name, g in groups.items()]
        return build_result("Kruskal-Wallis H Test", "kruskal_wallis",
                            "H", H, p_value=p, n=n, df_val=k - 1,
                            significant=bool(p < alpha),
                            effect_size_name="η²", effect_size_value=eta2,
                            effect_size_interpretation=interpret_effect_size("eta_squared", eta2),
                            conclusion=f"H({k-1}) = {H:.3f}, p = {p:.4f}. {'Significant' if p<alpha else 'No significant'} group differences.",
                            additional_stats={"H": round(float(H), 4), "eta_squared": round(eta2, 4),
                                             "df": k - 1, "group_table": group_table},
                            table=group_table)
    except Exception as e:
        return build_error("Kruskal-Wallis", "kruskal_wallis", str(e), "Check group and outcome columns.")


def run_kruskal_eta2(df, variables, brief, alpha=0.05):
    result = run_kruskal_wallis(df, variables, brief, alpha)
    if result.get("error"):
        return result
    eta2 = result.get("additional_stats", {}).get("eta_squared")
    return build_result("Kruskal-Wallis Effect Size (η²)", "kruskal_wallis_eta2",
                        "η²", eta2, n=result.get("n"),
                        effect_size_name="η²", effect_size_value=eta2,
                        additional_stats={"eta_squared": eta2})


def run_friedman(df, variables, brief, alpha=0.05):
    try:
        cols = [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(cols) < 3:
            return build_error("Friedman Test", "friedman_test", "Need >= 3 within-subject columns.", "Select 3+ time-point columns.")
        data = df[cols].dropna()
        chi2, p = stats.friedmanchisquare(*[data[c].values for c in cols])
        n, k = len(data), len(cols)
        # Kendall's W
        W = float(chi2 / (n * (k - 1)))
        interp = "weak" if W < 0.3 else ("moderate" if W < 0.7 else "strong")
        return build_result("Friedman Test", "friedman_test",
                            "χ²", chi2, p_value=p, n=n, df_val=k - 1,
                            significant=bool(p < alpha),
                            effect_size_name="Kendall's W", effect_size_value=W,
                            effect_size_interpretation=interp,
                            conclusion=f"χ²({k-1}) = {chi2:.3f}, p = {p:.4f}. {'Significant' if p<alpha else 'No significant'} within-subject differences.",
                            additional_stats={"chi2": round(float(chi2), 4), "kendall_w": round(W, 4),
                                             "df": k - 1, "time_points": cols})
    except Exception as e:
        return build_error("Friedman Test", "friedman_test", str(e), "Check within-subject columns.")


def run_mcnemar(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("McNemar's Test", "mcnemar", "Need before and after columns.", "Select 2 binary columns.")
        before_col, after_col = variables[0], variables[1]
        data = df[[before_col, after_col]].dropna()
        ct = pd.crosstab(data[before_col], data[after_col])
        if ct.shape != (2, 2):
            return build_error("McNemar's Test", "mcnemar", "Both columns must be binary (2 categories).", "Check column values.")
        b = int(ct.iloc[0, 1])  # Yes→No
        c = int(ct.iloc[1, 0])  # No→Yes
        # McNemar statistic
        chi2 = float((abs(b - c) - 1) ** 2 / (b + c)) if (b + c) > 0 else 0.0
        p = float(stats.chi2.sf(chi2, 1))
        OR = b / c if c > 0 else float("inf")
        return build_result("McNemar's Test", "mcnemar",
                            "χ²", chi2, p_value=p, n=len(data),
                            significant=bool(p < alpha),
                            conclusion=f"{'Significant' if p<alpha else 'No significant'} change in proportions.",
                            additional_stats={"chi2": round(chi2, 4), "p": round(float(p), 4),
                                             "b": b, "c": c, "odds_ratio": round(float(OR), 4) if not np.isinf(OR) else None,
                                             "contingency_table": ct.to_dict()})
    except Exception as e:
        return build_error("McNemar's Test", "mcnemar", str(e), "Ensure columns are binary (0/1 or two categories).")


def run_chi_square(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Chi-Square Test", "chi_square", "Need 2 categorical columns.", "Select 2 variables.")
        col1, col2 = variables[0], variables[1]
        data = df[[col1, col2]].dropna()
        ct = pd.crosstab(data[col1], data[col2])
        chi2, p, dof, expected = stats.chi2_contingency(ct)
        n = int(ct.values.sum())
        # Cramer's V
        min_dim = min(ct.shape) - 1
        V = float(np.sqrt(chi2 / (n * min_dim))) if min_dim > 0 and n > 0 else 0.0
        interp = "negligible" if V < 0.1 else ("small" if V < 0.3 else ("medium" if V < 0.5 else "large"))
        return build_result("Chi-Square Test of Independence", "chi_square",
                            "χ²", chi2, p_value=p, n=n, df_val=dof,
                            significant=bool(p < alpha),
                            effect_size_name="Cramer's V", effect_size_value=V,
                            effect_size_interpretation=interp,
                            conclusion=f"χ²({dof}) = {chi2:.3f}, p = {p:.4f}. {'Significant' if p<alpha else 'No significant'} association.",
                            additional_stats={"chi2": round(float(chi2), 4), "cramers_v": round(V, 4),
                                             "contingency_table": ct.to_dict(),
                                             "expected_table": pd.DataFrame(expected, index=ct.index, columns=ct.columns).round(2).to_dict()},
                            table=[{"variable": f"{col1} × {col2}", "chi2": round(float(chi2), 4),
                                    "df": dof, "p": round(float(p), 4), "cramers_v": round(V, 4)}])
    except Exception as e:
        return build_error("Chi-Square Test", "chi_square", str(e), "Check categorical column types.")


def run_chi_square_goodness_of_fit(df, variables, brief, alpha=0.05):
    """
    Chi-Square Goodness-of-Fit test.
    Tests whether the observed frequency distribution of a single categorical
    variable matches an expected distribution (default: uniform).

    Variables: [categorical_col]
    brief.get('expected_proportions') may be a dict of {category: proportion}.
    """
    try:
        if not variables:
            return build_error("Chi-Square GoF", "chi_square_goodness_of_fit",
                               "Need 1 categorical column.", "Select the categorical variable.")
        col = variables[0]
        if col not in df.columns:
            return build_error("Chi-Square GoF", "chi_square_goodness_of_fit",
                               f"Column '{col}' not found.", "Check variable name.")
        data = df[col].dropna()
        observed = data.value_counts().sort_index()
        categories = list(observed.index)
        n = int(observed.sum())
        if n == 0:
            return build_error("Chi-Square GoF", "chi_square_goodness_of_fit",
                               "No observations.", "Check the column.")

        # Expected proportions from brief, or uniform
        raw_exp = (brief or {}).get("expected_proportions") or {}
        if raw_exp and set(str(k) for k in raw_exp.keys()).issuperset(set(str(c) for c in categories)):
            total_p = sum(raw_exp.values())
            exp_props = [raw_exp.get(str(c), raw_exp.get(c, 1/len(categories))) / total_p for c in categories]
        else:
            exp_props = [1.0 / len(categories)] * len(categories)

        expected_counts = [p * n for p in exp_props]
        chi2, p = stats.chisquare(f_obs=observed.values, f_exp=expected_counts)
        dof = len(categories) - 1

        # Effect size: w = sqrt(chi2 / n)
        w = float(np.sqrt(chi2 / n)) if n > 0 else 0.0
        w_interp = "negligible" if w < 0.1 else ("small" if w < 0.3 else ("medium" if w < 0.5 else "large"))

        freq_table = [
            {"category": str(c), "observed": int(o), "expected": round(float(e), 2),
             "pct_observed": round(float(o / n * 100), 2)}
            for c, o, e in zip(categories, observed.values, expected_counts)
        ]
        distribution_type = "user-defined" if raw_exp else "uniform"
        return build_result(
            "Chi-Square Goodness of Fit", "chi_square_goodness_of_fit",
            "χ²", chi2, p_value=p, n=n, df_val=dof,
            significant=bool(p < alpha),
            effect_size_name="w", effect_size_value=w,
            effect_size_interpretation=w_interp,
            conclusion=(f"χ²({dof}) = {chi2:.3f}, p = {p:.4f}. "
                        f"{'Significant' if p < alpha else 'No significant'} deviation from {distribution_type} distribution."),
            additional_stats={
                "chi2": round(float(chi2), 4),
                "effect_w": round(w, 4),
                "distribution_tested": distribution_type,
                "frequency_table": freq_table,
            },
            table=freq_table,
        )
    except Exception as e:
        return build_error("Chi-Square GoF", "chi_square_goodness_of_fit", str(e), "Check the categorical column.")


def run_fisher_exact(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Fisher's Exact Test", "fisher_exact", "Need 2 binary columns.", "Select 2 binary variables.")
        col1, col2 = variables[0], variables[1]
        data = df[[col1, col2]].dropna()
        ct = pd.crosstab(data[col1], data[col2])
        if ct.shape != (2, 2):
            return build_error("Fisher's Exact", "fisher_exact", "Requires 2×2 table (both binary).", "Select binary columns.")
        OR, p = stats.fisher_exact(ct.values)
        # CI on OR via logit approach
        a, b_val, c_val, d = ct.values[0, 0], ct.values[0, 1], ct.values[1, 0], ct.values[1, 1]
        try:
            log_OR = np.log(OR)
            # Haldane-Anscombe correction for zero cells
            if a == 0 or b_val == 0 or c_val == 0 or d == 0:
                a_c, b_c, c_c, d_c = a + 0.5, b_val + 0.5, c_val + 0.5, d + 0.5
            else:
                a_c, b_c, c_c, d_c = a, b_val, c_val, d
            se_log = float(np.sqrt(1/a_c + 1/b_c + 1/c_c + 1/d_c))
            ci_l = float(np.exp(log_OR - 1.96 * se_log))
            ci_u = float(np.exp(log_OR + 1.96 * se_log))
        except Exception:
            ci_l = ci_u = None
        return build_result("Fisher's Exact Test", "fisher_exact",
                            "OR", OR, p_value=p, n=int(ct.values.sum()),
                            significant=bool(p < alpha), ci_lower=ci_l, ci_upper=ci_u,
                            conclusion=f"OR = {OR:.3f}, p = {p:.4f}. {'Significant' if p<alpha else 'No significant'} association.",
                            additional_stats={"odds_ratio": round(float(OR), 4), "p": round(float(p), 4),
                                             "contingency_table": ct.to_dict()})
    except Exception as e:
        return build_error("Fisher's Exact Test", "fisher_exact", str(e), "Requires 2×2 contingency table.")


def run_chi_square_extended(df, variables, brief, alpha=0.05):
    try:
        base = run_chi_square(df, variables, brief, alpha)
        if base.get("error"):
            return base
        col1, col2 = variables[0], variables[1]
        data = df[[col1, col2]].dropna()
        ct = pd.crosstab(data[col1], data[col2])
        n = ct.values.sum()
        chi2 = base["statistic"]["value"]
        # Phi (2x2 only)
        phi = float(np.sqrt(chi2 / n)) if ct.shape == (2, 2) and n > 0 else None
        # Contingency coefficient
        cc = float(np.sqrt(chi2 / (chi2 + n))) if n > 0 else None
        # Column percentages
        col_pct = (ct / ct.sum(axis=0) * 100).round(2).to_dict()
        base["additional_stats"]["phi"] = round(phi, 4) if phi else None
        base["additional_stats"]["contingency_coefficient"] = round(cc, 4) if cc else None
        base["additional_stats"]["column_percentages"] = col_pct
        return base
    except Exception as e:
        return build_error("Chi-Square (Extended)", "chi_square_extended", str(e), "Check categorical column types.")


def run_sign_test(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Sign Test", "sign_test", "Need 2 paired columns.", "Select pre and post columns.")
        col1, col2 = variables[0], variables[1]
        data = df[[col1, col2]].dropna()
        diff = data[col2] - data[col1]
        n_pos = int((diff > 0).sum()); n_neg = int((diff < 0).sum())
        n = n_pos + n_neg
        # Two-sided binomial test
        result = stats.binomtest(n_pos, n=n, p=0.5, alternative="two-sided")
        p = float(result.pvalue)
        return build_result("Sign Test", "sign_test",
                            "n+", n_pos, p_value=p, n=n,
                            significant=bool(p < alpha),
                            conclusion=f"n+ = {n_pos}, n- = {n_neg}: {'Significant' if p<alpha else 'No significant'} direction.",
                            additional_stats={"n_positive": n_pos, "n_negative": n_neg, "n_zeros": int((diff == 0).sum()), "p": round(float(p), 4)})
    except Exception as e:
        return build_error("Sign Test", "sign_test", str(e), "Check paired columns.")


def run_runs_test(df, variables, brief, alpha=0.05):
    try:
        col = next((c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])), None)
        if col is None:
            return build_error("Runs Test", "runs_test", "No numeric column found.", "Select a numeric variable.")
        s = df[col].dropna()
        median = float(s.median())
        binary = (s > median).astype(int).values
        # Count runs
        runs = 1 + int(np.sum(np.diff(binary) != 0))
        n1 = int(binary.sum()); n2 = int(len(binary) - n1)
        n = n1 + n2
        # Expected runs and variance
        exp_runs = float(2 * n1 * n2 / n + 1) if n > 0 else 0
        var_runs = float(2 * n1 * n2 * (2 * n1 * n2 - n) / (n * n * (n - 1))) if n > 1 else 0
        z = float((runs - exp_runs) / np.sqrt(var_runs)) if var_runs > 0 else 0.0
        p = float(2 * stats.norm.sf(abs(z)))
        return build_result("Wald-Wolfowitz Runs Test", "runs_test",
                            "Z", z, p_value=p, n=n,
                            significant=bool(p < alpha),
                            conclusion=f"{'Non-random' if p<alpha else 'Random'} sequence detected (Z = {z:.3f}).",
                            additional_stats={"n_runs": runs, "expected_runs": round(exp_runs, 2), "Z": round(z, 4)})
    except Exception as e:
        return build_error("Runs Test", "runs_test", str(e), "Check numeric column.")


def run_kendall_w(df, variables, brief, alpha=0.05):
    try:
        cols = [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(cols) < 2:
            return build_error("Kendall's W", "kendall_w", "Need >= 2 rater columns.", "Select rater columns.")
        data = df[cols].dropna()
        m, n = len(cols), len(data)  # m = raters, n = subjects
        if n <= 1:
            return build_error('Kendall\'s W', 'kendall_w', 'Need at least 2 subjects.', 'Check your data has multiple rows/subjects.')
        # Rank each rater
        ranks = data.rank(axis=0)
        Ri = ranks.sum(axis=1)  # sum of ranks for each subject
        R_bar = Ri.mean()
        S = float(((Ri - R_bar) ** 2).sum())
        denom = m**2 * (n**3 - n)
        if denom == 0:
            return build_error('Kendall\'s W', 'kendall_w', 'Denominator is zero (identical rankings).', 'Check for variance in rankings.')
        W = float(12 * S / denom)
        chi2 = float(m * (n - 1) * W)
        p = float(stats.chi2.sf(chi2, n - 1))
        interp = "weak" if W < 0.3 else ("moderate" if W < 0.7 else "strong")
        return build_result("Kendall's Coefficient of Concordance (W)", "kendall_w",
                            "W", W, p_value=p, n=n,
                            significant=bool(p < alpha),
                            effect_size_name="W", effect_size_value=W,
                            effect_size_interpretation=interp,
                            conclusion=f"W = {W:.4f}: {interp} agreement. χ²({n-1}) = {chi2:.3f}, p = {p:.4f}.",
                            additional_stats={"W": round(W, 4), "chi2": round(chi2, 4), "df": n - 1, "m_raters": m, "n_subjects": n})
    except Exception as e:
        return build_error("Kendall's W", "kendall_w", str(e), "Check rater columns.")
