# backend/analysis/engine/tests/posthoc.py
"""Post-hoc tests — Tukey HSD, Bonferroni, Dunn, Scheffe, Newman-Keuls, Fisher LSD."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error

try:
    from statsmodels.stats.multicomp import pairwise_tukeyhsd, MultiComparison
except ImportError:
    pairwise_tukeyhsd = None; MultiComparison = None

try:
    import scikit_posthocs as sp
except ImportError:
    sp = None


def _get_groups(df, group_col, outcome_col):
    groups = {}
    for name, grp in df.groupby(group_col):
        s = grp[outcome_col].dropna()
        if len(s) >= 2:
            groups[str(name)] = s.values
    return groups


def run_tukey_hsd(df, variables, brief, alpha=0.05):
    try:
        if pairwise_tukeyhsd is None:
            return build_error("Tukey HSD", "tukey_hsd", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Tukey HSD", "tukey_hsd", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        data = df[[group_col, outcome_col]].dropna()
        result = pairwise_tukeyhsd(data[outcome_col], data[group_col], alpha=alpha)
        table = []
        for row in result.summary().data[1:]:
            table.append({"group1": str(row[0]), "group2": str(row[1]),
                          "mean_diff": round(float(row[2]), 4),
                          "p_adj": round(float(row[3]), 4),
                          "CI_lower": round(float(row[4]), 4),
                          "CI_upper": round(float(row[5]), 4),
                          "reject": bool(row[6])})
        return build_result("Tukey HSD Post-Hoc Test", "tukey_hsd",
                            "N pairs", len(table), n=len(data),
                            significant=any(r["reject"] for r in table),
                            conclusion=f"{sum(r['reject'] for r in table)}/{len(table)} pairwise comparisons significant.",
                            additional_stats={"comparisons": table}, table=table)
    except Exception as e:
        return build_error("Tukey HSD", "tukey_hsd", str(e), "Check group and outcome columns.")


def run_bonferroni(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Bonferroni", "bonferroni_test", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        groups = _get_groups(df, group_col, outcome_col)
        names = list(groups.keys())
        n_comparisons = len(names) * (len(names) - 1) // 2
        adj_alpha = alpha / n_comparisons if n_comparisons > 0 else alpha
        table = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                g1, g2 = groups[names[i]], groups[names[j]]
                t, p_raw = stats.ttest_ind(g1, g2)
                p_adj = min(float(p_raw) * n_comparisons, 1.0)
                table.append({"group1": names[i], "group2": names[j],
                              "t": round(float(t), 4), "p_raw": round(float(p_raw), 4),
                              "p_adj": round(p_adj, 4), "reject": bool(p_adj < alpha)})
        return build_result("Bonferroni Post-Hoc Test", "bonferroni_test",
                            "N pairs", len(table), n=sum(len(g) for g in groups.values()),
                            significant=any(r["reject"] for r in table),
                            conclusion=f"{sum(r['reject'] for r in table)}/{len(table)} significant after Bonferroni correction.",
                            additional_stats={"comparisons": table, "adj_alpha": round(adj_alpha, 6),
                                             "n_comparisons": n_comparisons}, table=table)
    except Exception as e:
        return build_error("Bonferroni", "bonferroni_test", str(e), "Check group and outcome columns.")


def run_dunn(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Dunn's Test", "dunn_test", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        data = df[[group_col, outcome_col]].dropna()
        if sp is not None:
            p_df = sp.posthoc_dunn(data, val_col=outcome_col, group_col=group_col, p_adjust="bonferroni")
            groups_list = list(p_df.columns)
            table = []
            for i, g1 in enumerate(groups_list):
                for j, g2 in enumerate(groups_list):
                    if j > i:
                        p_raw = float(p_df.loc[g1, g2])
                        table.append({"group1": str(g1), "group2": str(g2), "p_bonferroni": round(p_raw, 4),
                                      "reject": bool(p_raw < alpha)})
        else:
            # Manual: rank-based
            groups = _get_groups(df, group_col, outcome_col)
            names = list(groups.keys()); all_vals = np.concatenate(list(groups.values()))
            n_total = len(all_vals)
            # Assign ranks globally
            all_df = pd.DataFrame({"val": np.concatenate(list(groups.values())),
                                   "group": np.repeat(names, [len(g) for g in groups.values()])})
            all_df["rank"] = all_df["val"].rank()
            mean_ranks = all_df.groupby("group")["rank"].mean()
            group_ns = all_df.groupby("group")["rank"].count()
            n_comp = len(names) * (len(names) - 1) // 2
            table = []
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    g1n, g2n = names[i], names[j]
                    ni, nj = int(group_ns[g1n]), int(group_ns[g2n])
                    SE = float(np.sqrt(n_total * (n_total + 1) / 12 * (1 / ni + 1 / nj)))
                    Z = float((mean_ranks[g1n] - mean_ranks[g2n]) / SE) if SE > 0 else 0
                    p_raw = float(2 * stats.norm.sf(abs(Z)))
                    p_bonf = min(p_raw * n_comp, 1.0)
                    table.append({"group1": g1n, "group2": g2n, "Z": round(Z, 4),
                                  "p_raw": round(p_raw, 4), "p_bonferroni": round(p_bonf, 4),
                                  "reject": bool(p_bonf < alpha)})
        return build_result("Dunn's Post-Hoc Test", "dunn_test",
                            "N pairs", len(table), n=len(data),
                            significant=any(r["reject"] for r in table),
                            conclusion=f"{sum(r['reject'] for r in table)}/{len(table)} significant after Dunn/Bonferroni.",
                            additional_stats={"comparisons": table}, table=table)
    except Exception as e:
        return build_error("Dunn's Test", "dunn_test", str(e), "Check group and outcome columns.")


def run_scheffe(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Scheffe Test", "scheffe_test", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        groups = _get_groups(df, group_col, outcome_col)
        names = list(groups.keys())
        k = len(names); n = sum(len(g) for g in groups.values())
        # Pooled MSE from one-way ANOVA
        grand_mean = np.mean(np.concatenate(list(groups.values())))
        ss_within = sum(np.sum((g - np.mean(g))**2) for g in groups.values())
        df_within = n - k; MSE = ss_within / df_within if df_within > 0 else 1
        F_crit = stats.f.ppf(1 - alpha, k - 1, df_within)
        table = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                g1, g2 = groups[names[i]], groups[names[j]]
                mean_diff = float(np.mean(g1) - np.mean(g2))
                F_sch = float(mean_diff**2 / (MSE * (1/len(g1) + 1/len(g2))))
                # Scheffe critical F = (k-1)*F_crit
                crit = (k - 1) * F_crit
                p_adj = float(stats.f.sf(F_sch / (k - 1), k - 1, df_within))
                table.append({"group1": names[i], "group2": names[j],
                              "mean_diff": round(mean_diff, 4), "F_scheffe": round(F_sch, 4),
                              "F_critical": round(crit, 4), "p_adj": round(p_adj, 4),
                              "reject": bool(F_sch > crit)})
        return build_result("Scheffe's Post-Hoc Test", "scheffe_test",
                            "N pairs", len(table), n=n,
                            significant=any(r["reject"] for r in table),
                            additional_stats={"comparisons": table}, table=table)
    except Exception as e:
        return build_error("Scheffe Test", "scheffe_test", str(e), "Check group and outcome columns.")


def run_newman_keuls(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Newman-Keuls", "newman_keuls", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        data = df[[group_col, outcome_col]].dropna()
        if sp is not None:
            # Newman-Keuls is a step-down test — posthoc_conover with holm correction
            # is the best approximation available in scikit-posthocs; it controls alpha
            # in a step-down fashion similar to Newman-Keuls.
            p_df = sp.posthoc_conover(data, val_col=outcome_col, group_col=group_col, p_adjust="holm")
            groups_list = list(p_df.columns)
            table = [{"group1": str(g1), "group2": str(g2),
                      "p_adj": round(float(p_df.loc[g1, g2]), 4),
                      "reject": bool(float(p_df.loc[g1, g2]) < alpha)}
                     for i, g1 in enumerate(groups_list) for j, g2 in enumerate(groups_list) if j > i]
        else:
            # Fallback to Bonferroni
            base = run_bonferroni(df, variables, brief, alpha)
            return base
        return build_result("Newman-Keuls Post-Hoc Test", "newman_keuls",
                            "N pairs", len(table), n=len(data),
                            significant=any(r["reject"] for r in table),
                            additional_stats={
                                "comparisons": table,
                                "method_note": "Newman-Keuls procedure approximated using Conover's test (stepwise Bonferroni). True Newman-Keuls sequential testing requires specialized tables. Results are conservative."
                            }, table=table)
    except Exception as e:
        return build_error("Newman-Keuls", "newman_keuls", str(e), "Check group and outcome columns.")


def run_fisher_lsd(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Fisher LSD", "fisher_lsd", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        groups = _get_groups(df, group_col, outcome_col)
        names = list(groups.keys())
        k = len(names); n = sum(len(g) for g in groups.values())
        ss_within = sum(np.sum((g - np.mean(g))**2) for g in groups.values())
        df_within = n - k; MSE = ss_within / df_within if df_within > 0 else 1
        t_crit = stats.t.ppf(1 - alpha / 2, df_within)
        table = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                g1, g2 = groups[names[i]], groups[names[j]]
                mean_diff = float(np.mean(g1) - np.mean(g2))
                LSD = float(t_crit * np.sqrt(MSE * (1/len(g1) + 1/len(g2))))
                t_val, p_raw = stats.ttest_ind(g1, g2)
                table.append({"group1": names[i], "group2": names[j],
                              "mean_diff": round(mean_diff, 4), "LSD": round(LSD, 4),
                              "t": round(float(t_val), 4), "p_raw": round(float(p_raw), 4),
                              "reject": bool(abs(mean_diff) > LSD)})
        return build_result("Fisher's LSD Post-Hoc Test", "fisher_lsd",
                            "N pairs", len(table), n=n,
                            significant=any(r["reject"] for r in table),
                            conclusion=f"{sum(r['reject'] for r in table)}/{len(table)} pairs differ significantly.",
                            additional_stats={"comparisons": table, "LSD_threshold": round(float(t_crit * np.sqrt(MSE * 2 / max(len(g) for g in groups.values()))), 4)},
                            table=table)
    except Exception as e:
        return build_error("Fisher LSD", "fisher_lsd", str(e), "Check group and outcome columns.")
