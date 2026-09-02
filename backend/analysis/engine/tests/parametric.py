# backend/analysis/engine/tests/parametric.py
"""Parametric comparison tests — T-tests, ANOVA, ANCOVA, MANOVA, effect sizes."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error, interpret_effect_size

try:
    import pingouin as pg
except ImportError:
    pg = None
try:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    from statsmodels.multivariate.manova import MANOVA
except ImportError:
    sm = None; smf = None; MANOVA = None

try:
    from analysis.engine.bootstrap import (
        bootstrap_mean, bootstrap_mean_diff, bootstrap_cohens_d,
        bootstrap_paired_diff, n_resamples_for
    )
    _BOOTSTRAP_AVAILABLE = True
except Exception:
    _BOOTSTRAP_AVAILABLE = False


def _safe_boot(fn, *args, **kwargs):
    """Run a bootstrap function and return (ci_l, ci_u) or None on failure."""
    if not _BOOTSTRAP_AVAILABLE:
        return None
    try:
        ci_l, ci_u, _ = fn(*args, **kwargs)
        return ci_l, ci_u
    except Exception:
        return None


def _split_groups(df, group_col, outcome_col):
    groups = {}
    for name, grp in df.groupby(group_col):
        s = grp[outcome_col].dropna()
        if len(s) >= 2:
            groups[str(name)] = s
    return groups


def _pooled_std(s1, s2):
    n1, n2 = len(s1), len(s2)
    return float(np.sqrt(((n1 - 1) * s1.var(ddof=1) + (n2 - 1) * s2.var(ddof=1)) / (n1 + n2 - 2)))


def _cohens_d_interp(d):
    d = abs(d)
    if d < 0.2: return "negligible"
    if d < 0.5: return "small"
    if d < 0.8: return "medium"
    return "large"


def run_one_sample_t(df, variables, brief, alpha=0.05):
    try:
        col = next((c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])), None)
        if col is None:
            return build_error("One-Sample T-Test", "one_sample_t_test", "No numeric column found.", "Select a numeric variable.")
        test_value = float(brief.get("test_value", 0) or 0)
        s = df[col].dropna()
        t, p = stats.ttest_1samp(s, test_value)
        n = len(s)
        d = float((s.mean() - test_value) / s.std(ddof=1))
        se = float(s.sem())
        t_crit = stats.t.ppf(1 - alpha / 2, n - 1)
        ci_l = float(s.mean() - t_crit * se)
        ci_u = float(s.mean() + t_crit * se)
        # BCa Bootstrap CI for the mean
        boot = _safe_boot(bootstrap_mean, s.values, n_resamples=n_resamples_for(n), ci_level=1 - alpha)
        boot_block = {"lower": round(boot[0], 4), "upper": round(boot[1], 4),
                      "method": "BCa bootstrap", "n_resamples": n_resamples_for(n)} if boot else None
        return build_result("One-Sample T-Test", "one_sample_t_test",
                            "t", t, p_value=p, n=n, df_val=n - 1,
                            significant=bool(p < alpha), ci_lower=ci_l, ci_upper=ci_u,
                            effect_size_name="Cohen's d", effect_size_value=d,
                            effect_size_interpretation=_cohens_d_interp(d),
                            conclusion=f"Mean ({s.mean():.3f}) {'significantly differs from' if p<alpha else 'does not significantly differ from'} test value {test_value}.",
                            additional_stats={"mean": round(float(s.mean()), 4), "std": round(float(s.std(ddof=1)), 4),
                                             "se": round(se, 4), "test_value": test_value, "cohens_d": round(d, 4),
                                             "bootstrap_ci": boot_block})
    except Exception as e:
        return build_error("One-Sample T-Test", "one_sample_t_test", str(e), "Check column is numeric.")


def run_independent_t(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Independent T-Test", "independent_t_test", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        groups = _split_groups(df, group_col, outcome_col)
        if len(groups) != 2:
            return build_error("Independent T-Test", "independent_t_test",
                               f"Expected 2 groups, found {len(groups)}.", "Ensure the group variable has exactly 2 levels.")
        g1, g2 = list(groups.values())
        g1_name, g2_name = list(groups.keys())
        t, p = stats.ttest_ind(g1, g2, equal_var=True)
        pooled = _pooled_std(g1, g2)
        d = float((g1.mean() - g2.mean()) / pooled) if pooled > 0 else 0.0
        n = len(g1) + len(g2)
        df_val = n - 2
        # BCa Bootstrap CIs for mean difference and Cohen's d
        nr = n_resamples_for(n)
        boot_diff = _safe_boot(bootstrap_mean_diff,   g1.values, g2.values, n_resamples=nr, ci_level=1 - alpha)
        boot_d    = _safe_boot(bootstrap_cohens_d,    g1.values, g2.values, n_resamples=nr, ci_level=1 - alpha)
        boot_block = {
            "mean_diff_ci": {"lower": round(boot_diff[0], 4), "upper": round(boot_diff[1], 4)} if boot_diff else None,
            "cohens_d_ci":  {"lower": round(boot_d[0],    4), "upper": round(boot_d[1],    4)} if boot_d    else None,
            "method": "BCa bootstrap", "n_resamples": nr,
        }
        return build_result("Independent Samples T-Test", "independent_t_test",
                            "t", t, p_value=p, n=n, df_val=df_val,
                            significant=bool(p < alpha),
                            effect_size_name="Cohen's d", effect_size_value=d,
                            effect_size_interpretation=_cohens_d_interp(d),
                            conclusion=f"{g1_name} (M={g1.mean():.3f}) {'significantly differs from' if p<alpha else 'does not differ from'} {g2_name} (M={g2.mean():.3f}).",
                            additional_stats={g1_name: {"mean": round(float(g1.mean()), 4), "sd": round(float(g1.std(ddof=1)), 4), "n": len(g1)},
                                             g2_name: {"mean": round(float(g2.mean()), 4), "sd": round(float(g2.std(ddof=1)), 4), "n": len(g2)},
                                             "cohens_d": round(d, 4), "pooled_std": round(pooled, 4),
                                             "bootstrap_ci": boot_block})
    except Exception as e:
        return build_error("Independent T-Test", "independent_t_test", str(e), "Check group and outcome columns.")


def run_welch_t(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Welch's T-Test", "welch_t_test", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        groups = _split_groups(df, group_col, outcome_col)
        if len(groups) != 2:
            return build_error("Welch's T-Test", "welch_t_test", f"Expected 2 groups, found {len(groups)}.", "Check grouping variable.")
        g1, g2 = list(groups.values())
        g1_name, g2_name = list(groups.keys())
        t, p = stats.ttest_ind(g1, g2, equal_var=False)
        s1v, s2v = g1.var(ddof=1), g2.var(ddof=1)
        n1, n2 = len(g1), len(g2)
        df_w = float((s1v / n1 + s2v / n2) ** 2 / ((s1v / n1) ** 2 / (n1 - 1) + (s2v / n2) ** 2 / (n2 - 1)))
        pooled = float(np.sqrt((s1v + s2v) / 2))
        d = float((g1.mean() - g2.mean()) / pooled) if pooled > 0 else 0.0
        nr = n_resamples_for(n1 + n2)
        boot_diff = _safe_boot(bootstrap_mean_diff, g1.values, g2.values, n_resamples=nr, ci_level=1 - alpha)
        boot_d    = _safe_boot(bootstrap_cohens_d,  g1.values, g2.values, n_resamples=nr, ci_level=1 - alpha)
        boot_block = {
            "mean_diff_ci": {"lower": round(boot_diff[0], 4), "upper": round(boot_diff[1], 4)} if boot_diff else None,
            "cohens_d_ci":  {"lower": round(boot_d[0],    4), "upper": round(boot_d[1],    4)} if boot_d    else None,
            "method": "BCa bootstrap", "n_resamples": nr,
        }
        return build_result("Welch's T-Test (Unequal Variances)", "welch_t_test",
                            "t", t, p_value=p, n=n1 + n2, df_val=df_w,
                            significant=bool(p < alpha),
                            effect_size_name="Cohen's d", effect_size_value=d,
                            effect_size_interpretation=_cohens_d_interp(d),
                            conclusion=f"Welch's correction applied. {g1_name} vs {g2_name}: {'significant' if p<alpha else 'not significant'}.",
                            additional_stats={g1_name: {"mean": round(float(g1.mean()), 4), "sd": round(float(g1.std(ddof=1)), 4), "n": n1},
                                             g2_name: {"mean": round(float(g2.mean()), 4), "sd": round(float(g2.std(ddof=1)), 4), "n": n2},
                                             "cohens_d": round(d, 4), "welch_df": round(df_w, 2),
                                             "bootstrap_ci": boot_block})
    except Exception as e:
        return build_error("Welch's T-Test", "welch_t_test", str(e), "Check group and outcome columns.")


def run_paired_t(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Paired T-Test", "paired_t_test", "Need pre and post columns.", "Select 2 paired columns.")
        pre_col, post_col = variables[0], variables[1]
        data = df[[pre_col, post_col]].dropna()
        pre, post = data[pre_col], data[post_col]
        diff = post - pre
        t, p = stats.ttest_rel(pre, post)
        n = len(data)
        diff_std = diff.std(ddof=1)
        if diff_std == 0 or np.isnan(diff_std):
            d = 0.0
            d_note = 'All paired differences are identical; Cohen\'s d is 0.'
        else:
            d = float(diff.mean() / diff_std)
            d_note = None
        se = float(diff.sem())
        t_crit = stats.t.ppf(1 - alpha / 2, n - 1)
        ci_l, ci_u = float(diff.mean() - t_crit * se), float(diff.mean() + t_crit * se)
        # BCa Bootstrap CI for paired mean difference
        nr = n_resamples_for(n)
        boot = _safe_boot(bootstrap_paired_diff, pre.values, post.values, n_resamples=nr, ci_level=1 - alpha)
        boot_block = {"lower": round(boot[0], 4), "upper": round(boot[1], 4),
                      "method": "BCa bootstrap", "n_resamples": nr} if boot else None
        
        add_stats = {"mean_diff": round(float(diff.mean()), 4),
                     "std_diff": round(float(diff.std(ddof=1)), 4),
                     "cohens_d": round(d, 4),
                     pre_col: round(float(pre.mean()), 4),
                     post_col: round(float(post.mean()), 4),
                     "bootstrap_ci": boot_block}
        if d_note: add_stats["d_note"] = d_note
        
        return build_result("Paired Samples T-Test", "paired_t_test",
                            "t", t, p_value=p, n=n, df_val=n - 1,
                            significant=bool(p < alpha), ci_lower=ci_l, ci_upper=ci_u,
                            effect_size_name="Cohen's d", effect_size_value=d,
                            effect_size_interpretation=_cohens_d_interp(d),
                            conclusion=f"Mean difference = {diff.mean():.4f}; {'Significant' if p<alpha else 'Not significant'} change from {pre_col} to {post_col}.",
                            additional_stats=add_stats)
    except Exception as e:
        return build_error("Paired T-Test", "paired_t_test", str(e), "Check pre and post columns are numeric.")



def run_one_way_anova(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("One-Way ANOVA", "one_way_anova", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        groups = _split_groups(df, group_col, outcome_col)
        if len(groups) < 3:
            return build_error("One-Way ANOVA", "one_way_anova", f"Need >= 3 groups, found {len(groups)}.", "Ensure >= 3 group levels.")
        group_vals = list(groups.values())
        F, p = stats.f_oneway(*group_vals)
        all_vals = pd.concat(group_vals)
        grand_mean = float(all_vals.mean())
        ss_total = float(((all_vals - grand_mean) ** 2).sum())
        ss_between = float(sum(len(g) * (g.mean() - grand_mean) ** 2 for g in group_vals))
        eta2 = ss_between / ss_total if ss_total > 0 else 0.0
        df_between = len(groups) - 1
        df_within = sum(len(g) - 1 for g in group_vals)
        group_table = [{"group": name, "n": len(g), "mean": round(float(g.mean()), 4), "sd": round(float(g.std(ddof=1)), 4)}
                       for name, g in groups.items()]
        return build_result("One-Way ANOVA", "one_way_anova",
                            "F", F, p_value=p, n=int(all_vals.count()), df_val=df_between,
                            significant=bool(p < alpha),
                            effect_size_name="η²", effect_size_value=eta2,
                            effect_size_interpretation=interpret_effect_size("eta_squared", eta2),
                            conclusion=f"F({df_between},{df_within}) = {F:.3f}, p = {p:.4f}. {'Significant' if p<alpha else 'Not significant'} group differences.",
                            additional_stats={"eta_squared": round(eta2, 4), "df_between": df_between,
                                             "df_within": df_within, "group_table": group_table},
                            table=group_table)
    except Exception as e:
        return build_error("One-Way ANOVA", "one_way_anova", str(e), "Check group and outcome columns.")


def run_planned_contrasts(df, variables, brief, alpha=0.05):
    """
    Planned (a priori) orthogonal contrasts for one-way ANOVA.

    Variables: [group_col, outcome_col]
    Contrasts are read from brief.get('contrasts') as a list of dicts:
        [{"name": "Treatment vs Control", "weights": {"A": 1, "B": -1, "C": 0}}, ...]
    If no contrasts provided in brief, auto-generates Helmert contrasts.

    Computes: contrast estimate (L), SE, t, df_within, p, Cohen's d per contrast.
    """
    try:
        if len(variables) < 2:
            return build_error("Planned Contrasts", "planned_contrasts",
                               "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        if group_col not in df.columns or outcome_col not in df.columns:
            return build_error("Planned Contrasts", "planned_contrasts",
                               "Column not found.", "Check variable names.")
        data = df[[group_col, outcome_col]].dropna()
        groups_ordered = sorted(data[group_col].astype(str).unique())
        k = len(groups_ordered)
        if k < 2:
            return build_error("Planned Contrasts", "planned_contrasts",
                               "Need >= 2 groups.", "Check group column.")

        group_data = {g: data[data[group_col].astype(str) == g][outcome_col].astype(float).values
                      for g in groups_ordered}
        n_total = sum(len(v) for v in group_data.values())

        # Pooled within-group MSE
        ss_within = sum(float(((v - v.mean()) ** 2).sum()) for v in group_data.values())
        df_within = n_total - k
        mse = ss_within / df_within if df_within > 0 else 1.0
        pooled_sd = float(np.sqrt(mse))

        # Load contrasts from brief or auto-generate Helmert contrasts
        raw_contrasts = (brief or {}).get("contrasts") or []
        if not raw_contrasts:
            for i in range(1, k):
                w = {g: 0.0 for g in groups_ordered}
                for j in range(i):
                    w[groups_ordered[j]] = -1.0 / i
                w[groups_ordered[i]] = 1.0
                prev = ", ".join(groups_ordered[:i])
                raw_contrasts.append({
                    "name": f"{groups_ordered[i]} vs mean({prev})",
                    "weights": w
                })

        results_list = []
        for contrast in raw_contrasts:
            c_name   = contrast.get("name", "Contrast")
            c_wts_raw = contrast.get("weights", {})
            c_wts    = {g: float(c_wts_raw.get(g, 0.0)) for g in groups_ordered}

            means = {g: float(v.mean()) for g, v in group_data.items()}
            ns    = {g: len(v) for g, v in group_data.items()}

            # Contrast estimate: L = sum(c_j * mean_j)
            L = sum(c_wts[g] * means[g] for g in groups_ordered)

            # SE of contrast
            se_sq = mse * sum((c_wts[g] ** 2) / ns[g] for g in groups_ordered if ns[g] > 0)
            se_L  = float(np.sqrt(max(se_sq, 1e-12)))
            t_val = float(L / se_L) if se_L > 0 else 0.0
            p_val = float(2 * stats.t.sf(abs(t_val), df=df_within))
            d     = float(L / pooled_sd) if pooled_sd > 0 else 0.0

            results_list.append({
                "contrast":    c_name,
                "weights":     c_wts,
                "L":           round(L, 4),
                "SE":          round(se_L, 4),
                "t":           round(t_val, 4),
                "df":          df_within,
                "p":           round(p_val, 4),
                "significant": bool(p_val < alpha),
                "cohens_d":    round(d, 4),
            })

        n_sig = sum(1 for r in results_list if r["significant"])
        method = "auto_helmert" if not (brief or {}).get("contrasts") else "user_defined"

        return build_result(
            "Planned Contrasts (ANOVA)", "planned_contrasts",
            "t", results_list[0]["t"] if results_list else 0,
            n=n_total,
            conclusion=(
                f"{len(results_list)} contrast(s) tested; {n_sig} significant at "
                f"alpha={alpha}. MSE = {round(mse, 4)}, df_within = {df_within}. "
                f"Method: {method.replace('_', ' ')}."
            ),
            additional_stats={
                "contrasts":   results_list,
                "group_means": {g: round(float(v.mean()), 4) for g, v in group_data.items()},
                "group_ns":    {g: len(v) for g, v in group_data.items()},
                "mse":         round(mse, 4),
                "df_within":   df_within,
                "method":      method,
            },
            table=results_list,
        )
    except Exception as e:
        return build_error("Planned Contrasts", "planned_contrasts",
                           str(e), "Check group and outcome columns.")


def run_welch_anova(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Welch ANOVA", "welch_anova", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        if group_col not in df.columns or outcome_col not in df.columns:
            return build_error("Welch ANOVA", "welch_anova", "Column not found.", "Check variable names.")
        if not pd.api.types.is_numeric_dtype(df[outcome_col]):
            return build_error("Welch ANOVA", "welch_anova",
                               f"Outcome '{outcome_col}' must be numeric.", "Select a numeric DV.")
        clean = df[[group_col, outcome_col]].dropna()
        n_groups = clean[group_col].nunique()
        if n_groups < 2:
            return build_error("Welch ANOVA", "welch_anova",
                               f"Need >= 2 groups, found {n_groups}.", "Ensure the group column has 2+ levels.")

        if pg is not None:
            try:
                res = pg.welch_anova(data=clean, dv=outcome_col, between=group_col)
                F = float(res["F"].iloc[0])
                df_num = float(res["ddof1"].iloc[0])
                df_den = float(res["ddof2"].iloc[0])
                # Handle both pingouin versions: 'p-unc' vs 'pval'
                p_col = next((c for c in ["p-unc", "pval", "p"] if c in res.columns), None)
                if p_col is None:
                    raise KeyError("No p-value column found in pingouin welch_anova result")
                p = float(res[p_col].iloc[0])
                eta2 = float(res["np2"].iloc[0]) if "np2" in res.columns else None
            except Exception:
                pg_fail = True
            else:
                pg_fail = False
        else:
            pg_fail = True

        if pg is None or pg_fail:
            # Fallback: Welch's ANOVA via Brown-Forsythe style using scipy
            groups = _split_groups(df, group_col, outcome_col)
            group_vals = list(groups.values())
            if len(group_vals) < 2:
                return build_error("Welch ANOVA", "welch_anova", "Need >= 2 groups.", "Check group column.")
            
            # Manual Welch's ANOVA (when pingouin unavailable)
            k = len(group_vals)
            ns = np.array([len(g) for g in group_vals])
            ms = np.array([np.mean(g) for g in group_vals])
            vs = np.array([np.var(g, ddof=1) for g in group_vals])
            ws = ns / vs  # weights
            grand_mean_w = float(np.sum(ws * ms) / np.sum(ws))
            
            # Between-group SS (weighted)
            ss_between = float(np.sum(ws * (ms - grand_mean_w)**2))
            
            # Welch correction term
            lambda_val = (3 / (k**2 - 1)) * float(np.sum(((1 - ws / np.sum(ws))**2) / (ns - 1)))
            
            df1 = k - 1
            df2 = float((k**2 - 1) / (3 * float(np.sum(((1 - ws / np.sum(ws))**2) / (ns - 1)))))
            
            F = float((ss_between / df1) / (1 + 2 * (k - 2) * lambda_val / 3))
            p = float(stats.f.sf(F, df1, df2))
            df_num = float(df1)
            df_den = float(df2)
            
            all_vals = pd.concat(group_vals)
            grand_mean = float(all_vals.mean())
            ss_total = float(((all_vals - grand_mean) ** 2).sum())
            ss_between_unweighted = float(sum(len(g) * (g.mean() - grand_mean) ** 2 for g in group_vals))
            eta2 = float(ss_between_unweighted / ss_total) if ss_total > 0 else None

        n = int(clean.shape[0])
        return build_result("Welch's ANOVA (Unequal Variances)", "welch_anova",
                            "F", F, p_value=p, n=n, df_val=df_num,
                            significant=bool(p < alpha),
                            effect_size_name="eta_squared", effect_size_value=eta2,
                            conclusion=f"F({df_num:.1f},{df_den:.1f}) = {F:.3f}, p = {p:.4f}.",
                            additional_stats={"F": round(float(F), 4), "df_num": round(float(df_num), 2),
                                             "df_den": round(float(df_den), 2),
                                             "eta_squared": round(float(eta2), 4) if eta2 is not None else None})
    except Exception as e:
        return build_error("Welch ANOVA", "welch_anova", str(e), "Check group and outcome columns.")


def run_two_way_anova(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Two-Way ANOVA", "two_way_anova", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 3:
            return build_error("Two-Way ANOVA", "two_way_anova", "Need factor1, factor2, outcome.", "Select 3 variables.")
        f1, f2, dv = variables[0], variables[1], variables[2]
        data = df[[f1, f2, dv]].dropna().copy()
        # Use safe column names to avoid patsy formula issues
        data.columns = ["factor1", "factor2", "outcome"]
        formula = "outcome ~ C(factor1) + C(factor2) + C(factor1):C(factor2)"
        model = smf.ols(formula, data=data).fit()
        from statsmodels.stats.anova import anova_lm
        anova_table = anova_lm(model, typ=2)
        ss_total = float(anova_table["sum_sq"].sum()) + float(model.ssr)
        results_table = []
        for term in anova_table.index:
            if term == "Residual":
                continue
            ss = float(anova_table.loc[term, "sum_sq"])
            F_val = float(anova_table.loc[term, "F"])
            p_val = float(anova_table.loc[term, "PR(>F)"])
            eta2 = ss / ss_total if ss_total > 0 else 0
            readable = term.replace("C(factor1)", f1).replace("C(factor2)", f2)
            results_table.append({"term": readable, "F": round(F_val, 4), "p": round(p_val, 4), "eta_squared": round(eta2, 4)})

        # Pick the interaction term (last) for the top-level p/F; fall back to smallest p
        interaction_rows = [r for r in results_table if ":" in r["term"]]
        primary = interaction_rows[0] if interaction_rows else min(results_table, key=lambda r: r["p"])
        top_F = primary["F"]
        top_p = primary["p"]
        top_eta2 = primary["eta_squared"]

        significant_overall = any(r["p"] < alpha for r in results_table)
        sig_terms = [r["term"] for r in results_table if r["p"] < alpha]
        conclusion = (
            f"Two-Way ANOVA ({f1} x {f2} on {dv}): "
            + (f"Significant effects: {', '.join(sig_terms)}." if sig_terms
               else "No significant main effects or interaction.")
        )
        return build_result("Two-Way ANOVA", "two_way_anova",
                            "F", top_F, p_value=top_p, n=len(data),
                            df_val=None,
                            significant=significant_overall,
                            effect_size_name="eta_squared", effect_size_value=top_eta2,
                            conclusion=conclusion,
                            additional_stats={"effects": results_table, "r_squared": round(float(model.rsquared), 4)},
                            table=results_table)
    except Exception as e:
        return build_error("Two-Way ANOVA", "two_way_anova", str(e), "Check factor and outcome columns.")



def run_two_way_eta_squared(df, variables, brief, alpha=0.05):
    """Delegate to two-way ANOVA and extract eta-squared."""
    return run_two_way_anova(df, variables, brief, alpha)


def run_repeated_anova(df, variables, brief, alpha=0.05):
    try:
        cols = [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(cols) < 2:
            return build_error("Repeated Measures ANOVA", "repeated_anova",
                               "Need >= 2 time-point columns.", "Select time-point columns.")
        data = df[cols].dropna().reset_index(drop=True)
        if len(data) < 5:
            return build_error("Repeated Measures ANOVA", "repeated_anova",
                               f"Too few complete rows (n={len(data)}). Need >= 5.", "Use more data.")
        data["subject"] = range(len(data))
        melted = data.melt(id_vars="subject", var_name="time", value_name="score")

        F = df_val = df2 = p = eta2 = None
        if pg is not None:
            try:
                rm = pg.rm_anova(data=melted, dv="score", within="time", subject="subject")
                F = float(rm["F"].iloc[0])
                df_val = float(rm["ddof1"].iloc[0])
                df2 = float(rm["ddof2"].iloc[0])
                # Handle both pingouin versions: 'p-unc' vs 'pval'
                p_col = next((c for c in ["p-unc", "pval", "p"] if c in rm.columns), None)
                if p_col is None:
                    raise KeyError("No p-value column in pingouin rm_anova result")
                p = float(rm[p_col].iloc[0])
                eta2 = float(rm["ng2"].iloc[0]) if "ng2" in rm.columns else (
                       float(rm["np2"].iloc[0]) if "np2" in rm.columns else None)
            except Exception:
                F = p = df_val = df2 = eta2 = None

        if F is None:
            # Friedman as fallback
            chi2, p = stats.friedmanchisquare(*[data[c] for c in cols])
            F = chi2; df_val = float(len(cols) - 1); df2 = None; eta2 = None

        return build_result("Repeated Measures ANOVA", "repeated_anova",
                            "F", F, p_value=p, n=len(data), df_val=df_val,
                            significant=bool(p < alpha),
                            effect_size_name="eta_squared", effect_size_value=eta2,
                            conclusion=f"Repeated measures: {'significant' if p<alpha else 'not significant'} time effect.",
                            additional_stats={"F": round(float(F), 4),
                                             "df1": round(float(df_val), 2) if df_val is not None else None,
                                             "df2": round(float(df2), 2) if df2 is not None else None,
                                             "eta_squared": round(float(eta2), 4) if eta2 is not None else None,
                                             "time_points": cols})
    except Exception as e:
        return build_error("Repeated Measures ANOVA", "repeated_anova", str(e), "Check time-point columns are numeric.")


def run_ancova(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("ANCOVA", "ancova", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 3:
            return build_error("ANCOVA", "ancova", "Need group_col, outcome_col, covariate_col.", "Select 3 variables.")
        group_col, dv, cov = variables[0], variables[1], variables[2]
        if group_col not in df.columns or dv not in df.columns or cov not in df.columns:
            return build_error("ANCOVA", "ancova", "One or more columns not found.", "Check variable names.")
        if not pd.api.types.is_numeric_dtype(df[dv]):
            return build_error("ANCOVA", "ancova", f"Outcome '{dv}' must be numeric.", "Select a numeric DV.")
        if not pd.api.types.is_numeric_dtype(df[cov]):
            return build_error("ANCOVA", "ancova", f"Covariate '{cov}' must be numeric.", "Select a numeric covariate.")
        data = df[[group_col, dv, cov]].dropna().copy()
        # Rename columns to safe names to avoid patsy backtick issues
        data.columns = ["group_factor", "outcome_var", "covariate_var"]
        formula = "outcome_var ~ C(group_factor) + covariate_var"
        model = smf.ols(formula, data=data).fit()
        from statsmodels.stats.anova import anova_lm
        anova_table = anova_lm(model, typ=2)
        results_table = []
        for term in anova_table.index:
            if term == "Residual":
                continue
            F_val = float(anova_table.loc[term, "F"])
            p_val = float(anova_table.loc[term, "PR(>F)"])
            readable = term.replace("C(group_factor)", group_col).replace("covariate_var", cov)
            results_table.append({"term": readable, "F": round(F_val, 4), "p": round(p_val, 4)})
        group_F = results_table[0]["F"] if results_table else None
        group_p = results_table[0]["p"] if results_table else None
        cov_F = results_table[1]["F"] if len(results_table) > 1 else None
        cov_p = results_table[1]["p"] if len(results_table) > 1 else None
        return build_result("ANCOVA", "ancova",
                            "F", group_F, p_value=group_p, n=len(data),
                            significant=bool(group_p < alpha) if group_p else None,
                            conclusion=f"Group effect: F = {group_F:.3f}, p = {group_p:.4f}. Covariate effect: F = {cov_F:.3f}" if group_F and cov_F else "",
                            additional_stats={
                                "group_effect": {"F": group_F, "p": group_p},
                                "covariate_effect": {"F": cov_F, "p": cov_p},
                                "r_squared": round(float(model.rsquared), 4),
                                "effects_table": results_table,
                            }, table=results_table)
    except Exception as e:
        return build_error("ANCOVA", "ancova", str(e), "Check group, outcome, and covariate columns.")


def run_manova(df, variables, brief, alpha=0.05):
    try:
        if MANOVA is None:
            return build_error("MANOVA", "manova", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 3:
            return build_error("MANOVA", "manova", "Need group_col + >= 2 DVs.", "Select group column and multiple DVs.")
        group_col = variables[0]; dvs = variables[1:]
        dv_cols = [c for c in dvs if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(dv_cols) < 2:
            return build_error("MANOVA", "manova", "Need >= 2 numeric DV columns.", "Select numeric DV columns.")
        data = df[[group_col] + dv_cols].dropna().copy()
        # Rename to safe column names to avoid formula parsing issues
        dv_safe = [f"dv{i}" for i in range(len(dv_cols))]
        col_map = {group_col: "group_factor"}
        col_map.update({orig: safe for orig, safe in zip(dv_cols, dv_safe)})
        safe_data = data.rename(columns=col_map)
        dv_formula = " + ".join(dv_safe)
        formula = f"{dv_formula} ~ C(group_factor)"
        mv = MANOVA.from_formula(formula, data=safe_data)
        mv_test = mv.mv_test()
        # Extract Pillai's trace
        try:
            stat_table = mv_test.results["C(group_factor)"]["stat"]
            pillai = float(stat_table.loc["Pillai's trace", "Value"])
            F_val = float(stat_table.loc["Pillai's trace", "F Value"])
            df_hyp = float(stat_table.loc["Pillai's trace", "Num DF"])
            df_err = float(stat_table.loc["Pillai's trace", "Den DF"])
            p_val = float(stat_table.loc["Pillai's trace", "Pr > F"])
        except Exception:
            pillai = F_val = df_hyp = df_err = p_val = None
        return build_result("MANOVA", "manova",
                            "Pillai's trace", pillai, p_value=p_val, n=len(data),
                            significant=bool(p_val < alpha) if p_val else None,
                            conclusion=f"MANOVA: {'significant' if (p_val and p_val<alpha) else 'not significant'} multivariate group effect.",
                            additional_stats={"pillai_trace": pillai, "F": F_val, "df_hyp": df_hyp,
                                             "df_err": df_err, "p_value": p_val, "dvs": dv_cols})
    except Exception as e:
        return build_error("MANOVA", "manova", str(e), "Check group and DV column types.")


def run_cohens_d_independent(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Cohen's d (Independent)", "independent_t_cohend", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        groups = _split_groups(df, group_col, outcome_col)
        if len(groups) < 2:
            return build_error("Cohen's d", "independent_t_cohend", "Need 2 groups.", "Check grouping variable.")
        g1, g2 = list(groups.values())[:2]
        pooled = _pooled_std(g1, g2)
        d = float((g1.mean() - g2.mean()) / pooled) if pooled > 0 else 0.0
        return build_result("Cohen's d (Independent Groups)", "independent_t_cohend",
                            "d", d, n=len(g1) + len(g2),
                            effect_size_name="Cohen's d", effect_size_value=d,
                            effect_size_interpretation=_cohens_d_interp(d),
                            additional_stats={"cohens_d": round(d, 4), "interpretation": _cohens_d_interp(d)})
    except Exception as e:
        return build_error("Cohen's d", "independent_t_cohend", str(e), "Check group and outcome columns.")


def run_cohens_d_paired(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Cohen's d (Paired)", "paired_t_cohend", "Need pre and post columns.", "Select 2 paired columns.")
        pre_col, post_col = variables[0], variables[1]
        data = df[[pre_col, post_col]].dropna()
        diff = data[post_col] - data[pre_col]
        d = float(diff.mean() / diff.std(ddof=1))
        return build_result("Cohen's d (Paired)", "paired_t_cohend",
                            "d", d, n=len(data),
                            effect_size_name="Cohen's d", effect_size_value=d,
                            effect_size_interpretation=_cohens_d_interp(d),
                            additional_stats={"cohens_d": round(d, 4), "interpretation": _cohens_d_interp(d)})
    except Exception as e:
        return build_error("Cohen's d (Paired)", "paired_t_cohend", str(e), "Check paired columns.")


def run_eta_squared(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Eta-Squared", "anova_eta_squared", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        groups = _split_groups(df, group_col, outcome_col)
        group_vals = list(groups.values())
        F, p = stats.f_oneway(*group_vals)
        all_vals = pd.concat(group_vals)
        grand_mean = float(all_vals.mean())
        ss_total = float(((all_vals - grand_mean) ** 2).sum())
        ss_between = float(sum(len(g) * (g.mean() - grand_mean) ** 2 for g in group_vals))
        ss_within = ss_total - ss_between
        k = len(groups); n = int(all_vals.count())
        eta2 = ss_between / ss_total if ss_total > 0 else 0.0
        partial_eta2 = ss_between / (ss_between + ss_within) if (ss_between + ss_within) > 0 else 0.0
        # Omega squared
        ms_within = ss_within / (n - k) if n > k else 0
        omega2 = float((ss_between - (k - 1) * ms_within) / (ss_total + ms_within)) if ss_total + ms_within > 0 else 0.0
        return build_result("Effect Size (Eta-Squared)", "anova_eta_squared",
                            "η²", eta2, p_value=p, n=n,
                            effect_size_name="η²", effect_size_value=eta2,
                            effect_size_interpretation=interpret_effect_size("eta_squared", eta2),
                            additional_stats={"eta_squared": round(eta2, 4), "partial_eta_squared": round(partial_eta2, 4),
                                             "omega_squared": round(omega2, 4)})
    except Exception as e:
        return build_error("Eta-Squared", "anova_eta_squared", str(e), "Check group and outcome columns.")


def run_one_sample_t_cohend(df, variables, brief, alpha=0.05):
    try:
        col = next((c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])), None)
        if not col:
            return build_error("Cohen's d (One-Sample)", "one_sample_t_cohend", "No numeric column found.", "Select a numeric variable.")
        test_value = float(brief.get("test_value", 0) or 0)
        s = df[col].dropna()
        s_std = s.std(ddof=1)
        if s_std == 0 or np.isnan(s_std):
            d = 0.0
        else:
            d = float((s.mean() - test_value) / s_std)
        return build_result("Cohen's d (One-Sample)", "one_sample_t_cohend",
                            "d", d, n=len(s),
                            effect_size_name="Cohen's d", effect_size_value=d,
                            effect_size_interpretation=_cohens_d_interp(d),
                            additional_stats={"cohens_d": round(d, 4), "interpretation": _cohens_d_interp(d)})
    except Exception as e:
        return build_error("Cohen's d (One-Sample)", "one_sample_t_cohend", str(e), "Check column.")
