# backend/analysis/engine/tests/outliers.py
"""Outlier detection and variance homogeneity tests — pre-built."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error

try:
    import statsmodels.api as sm
except ImportError:
    sm = None
try:
    import pingouin as pg
except ImportError:
    pg = None


def _num_cols(df, variables):
    return [c for c in (variables or df.columns) if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]


def run_iqr_outliers(df, variables, brief, alpha=0.05):
    try:
        cols = _num_cols(df, variables)
        if not cols:
            return build_error("IQR Outliers", "outliers_iqr", "No numeric columns found.", "Select numeric variables.")
        summary = {}
        for col in cols:
            s = df[col].dropna()
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outliers = s[(s < lower) | (s > upper)]
            summary[col] = {
                "q1": round(float(q1), 4), "q3": round(float(q3), 4),
                "iqr": round(float(iqr), 4), "lower_fence": round(float(lower), 4),
                "upper_fence": round(float(upper), 4), "n_outliers": int(len(outliers)),
                "pct_outliers": round(float(len(outliers) / len(s) * 100), 2),
                "outlier_values": [round(float(v), 4) for v in outliers.tolist()[:20]],
            }
        return build_result("IQR Outlier Detection", "outliers_iqr", "N", len(df), n=len(df),
                            additional_stats={"columns": summary})
    except Exception as e:
        return build_error("IQR Outliers", "outliers_iqr", str(e), "Check numeric column selection.")


def run_zscore_outliers(df, variables, brief, alpha=0.05):
    try:
        cols = _num_cols(df, variables)
        if not cols:
            return build_error("Z-Score Outliers", "outliers_zscore", "No numeric columns.", "Select numeric variables.")
        summary = {}
        for col in cols:
            s = df[col].dropna()
            if s.std() == 0:
                continue
            z = (s - s.mean()) / s.std()
            outlier_mask = z.abs() > 3
            summary[col] = {
                "n_outliers": int(outlier_mask.sum()),
                "pct_outliers": round(float(outlier_mask.mean() * 100), 2),
                "max_z": round(float(z.max()), 4), "min_z": round(float(z.min()), 4),
                "outlier_indices": z[outlier_mask].index.tolist()[:20],
            }
        return build_result("Z-Score Outlier Detection", "outliers_zscore", "N", len(df), n=len(df),
                            additional_stats={"columns": summary})
    except Exception as e:
        return build_error("Z-Score Outliers", "outliers_zscore", str(e), "Check column types.")


def run_grubbs_test(df, variables, brief, alpha=0.05):
    try:
        col = next((c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])), None)
        if col is None:
            return build_error("Grubbs' Test", "outliers_grubbs", "No numeric column found.", "Select a numeric variable.")
        s = df[col].dropna()
        n = len(s)
        if n < 6:
            return build_error("Grubbs' Test", "outliers_grubbs", f"n={n} too small. Need >= 6.", "Collect more data.")
        G = float((s - s.mean()).abs().max() / s.std())
        t_crit = stats.t.ppf(1 - alpha / (2 * n), n - 2)
        G_crit = float((n - 1) / np.sqrt(n) * np.sqrt(t_crit**2 / (n - 2 + t_crit**2)))
        outlier_val = float(s.iloc[(s - s.mean()).abs().argmax()])
        has_outlier = G > G_crit
        return build_result("Grubbs' Test for Single Outlier", "outliers_grubbs",
                            "G", G, p_value=None, n=n,
                            significant=has_outlier,
                            conclusion=f"{'Significant outlier detected' if has_outlier else 'No significant outlier'}: {outlier_val:.4f}",
                            additional_stats={"G_statistic": round(G, 4), "G_critical": round(G_crit, 4),
                                             "has_outlier": has_outlier, "outlier_value": round(outlier_val, 4)})
    except Exception as e:
        return build_error("Grubbs' Test", "outliers_grubbs", str(e), "Ensure normal distribution for Grubbs' test.")


def run_mahalanobis(df, variables, brief, alpha=0.05):
    try:
        cols = _num_cols(df, variables)
        if len(cols) < 2:
            return build_error("Mahalanobis Distance", "mahalanobis_distance",
                               "Need >= 2 numeric variables for multivariate outlier detection.", "Select 2+ numeric columns.")
        data = df[cols].dropna()
        n, p = len(data), len(cols)
        if n < p + 2:
            return build_error("Mahalanobis Distance", "mahalanobis_distance", f"n={n} too small for {p} variables.", "Need more rows.")
        X = data.values
        cov = np.cov(X.T)
        try:
            cov_inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            cov_inv = np.linalg.pinv(cov)
        mean = X.mean(axis=0)
        diffs = X - mean
        D2 = np.array([float(d @ cov_inv @ d) for d in diffs])
        threshold = float(stats.chi2.ppf(1 - alpha, df=p))
        outlier_mask = D2 > threshold
        outlier_rows = [{"row": int(data.index[i]), "D2": round(float(D2[i]), 4)}
                        for i in np.where(outlier_mask)[0][:10]]
        return build_result("Mahalanobis Distance (Multivariate Outliers)", "mahalanobis_distance",
                            "D²", float(D2.max()), n=n,
                            additional_stats={
                                "n_outliers": int(outlier_mask.sum()),
                                "pct_outliers": round(float(outlier_mask.mean() * 100), 2),
                                "threshold": round(threshold, 4),
                                "chi2_df": p, "alpha": alpha,
                                "outlier_rows": outlier_rows,
                            })
    except Exception as e:
        return build_error("Mahalanobis Distance", "mahalanobis_distance", str(e), "Check variables are numeric with no constant columns.")


def run_cooks_distance(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Cook's Distance", "cooks_distance", "statsmodels not installed.", "pip install statsmodels")
        cols = _num_cols(df, variables)
        if len(cols) < 2:
            return build_error("Cook's Distance", "cooks_distance", "Need DV + at least 1 IV.", "Select outcome and predictors.")
        dv, ivs = cols[0], cols[1:]
        data = df[cols].dropna()
        X = sm.add_constant(data[ivs].astype(float))
        y = data[dv].astype(float)
        model = sm.OLS(y, X).fit()
        influence = model.get_influence()
        cooks_d = influence.cooks_distance[0]
        threshold = 4 / len(data)
        influential = np.where(cooks_d > threshold)[0]
        return build_result("Cook's Distance (Influential Points)", "cooks_distance",
                            "D", float(cooks_d.max()), n=len(data),
                            additional_stats={
                                "n_influential": int(len(influential)),
                                "threshold": round(threshold, 4),
                                "max_cook_d": round(float(cooks_d.max()), 4),
                                "influential_rows": [{"row": int(data.index[i]), "cook_d": round(float(cooks_d[i]), 4)}
                                                     for i in influential[:20]],
                            })
    except Exception as e:
        return build_error("Cook's Distance", "cooks_distance", str(e), "Ensure valid DV and at least 1 numeric IV.")


def run_levene_test(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Levene's Test", "levene_test", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        if group_col not in df.columns or outcome_col not in df.columns:
            return build_error("Levene's Test", "levene_test", "Column(s) not found.", "Check variable names.")
        groups = [grp[outcome_col].dropna().values for _, grp in df.groupby(group_col) if len(grp) >= 2]
        if len(groups) < 2:
            return build_error("Levene's Test", "levene_test", "Need >= 2 groups with data.", "Check grouping variable.")
        stat, p = stats.levene(*groups)
        significant = p < alpha
        conclusion = ("Equal variances cannot be assumed (heteroscedastic)" if significant
                      else "Equal variances can be assumed (homoscedastic)")
        return build_result("Levene's Test for Equality of Variances", "levene_test",
                            "F", stat, p_value=p, n=sum(len(g) for g in groups),
                            significant=significant, conclusion=conclusion,
                            additional_stats={"statistic": round(float(stat), 4), "p_value": round(float(p), 4),
                                             "n_groups": len(groups), "conclusion": conclusion})
    except Exception as e:
        return build_error("Levene's Test", "levene_test", str(e), "Check group and outcome columns.")


def run_bartlett_test(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Bartlett's Test", "bartlett_test", "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        groups = [grp[outcome_col].dropna().values for _, grp in df.groupby(group_col) if len(grp) >= 2]
        if len(groups) < 2:
            return build_error("Bartlett's Test", "bartlett_test", "Need >= 2 groups.", "Check grouping variable.")
        stat, p = stats.bartlett(*groups)
        significant = p < alpha
        return build_result("Bartlett's Test for Equal Variances", "bartlett_test",
                            "K²", stat, p_value=p, n=sum(len(g) for g in groups),
                            significant=significant,
                            conclusion="Variances are significantly different." if significant else "Variances are homogeneous.",
                            additional_stats={"statistic": round(float(stat), 4), "p_value": round(float(p), 4)})
    except Exception as e:
        return build_error("Bartlett's Test", "bartlett_test", str(e), "Requires normally distributed groups.")


def run_mauchly_test(df, variables, brief, alpha=0.05):
    try:
        cols = _num_cols(df, variables)
        if len(cols) < 3:
            return build_error("Mauchly's Test", "mauchly_test",
                               "Need >= 3 within-subject time-point columns.", "Select repeated measures columns.")
        data = df[cols].dropna()
        if pg is not None:
            try:
                import io, contextlib
                # Use pingouin sphericity
                sph = pg.sphericity(data=data)
                return build_result("Mauchly's Test of Sphericity", "mauchly_test",
                                    "W", float(sph[1]), p_value=float(sph[2]), n=len(data),
                                    significant=bool(float(sph[2]) < alpha),
                                    conclusion="Sphericity violated — use Greenhouse-Geisser correction." if float(sph[2]) < alpha else "Sphericity assumed.",
                                    additional_stats={"W": round(float(sph[1]), 4), "p_value": round(float(sph[2]), 4),
                                                     "epsilon_gg": round(float(sph[3]), 4), "epsilon_hf": round(float(sph[4]), 4),
                                                     "correction_needed": bool(float(sph[2]) < alpha)})
            except Exception:
                pass
        # Fallback: compute epsilon via covariance matrix
        S = np.cov(data.values.T)
        k = len(cols)
        n = len(data)
        trace_s = np.trace(S)
        trace_s2 = np.trace(S @ S)
        epsilon_gg = float((trace_s**2) / ((k - 1) * trace_s2)) if trace_s2 > 0 else 1.0
        return build_result("Sphericity (Epsilon Estimate)", "mauchly_test",
                            "ε_GG", epsilon_gg, n=n,
                            additional_stats={"epsilon_gg": round(epsilon_gg, 4),
                                             "correction_needed": epsilon_gg < 0.75,
                                             "note": "Approximate epsilon — install pingouin for Mauchly W statistic."})
    except Exception as e:
        return build_error("Mauchly's Test", "mauchly_test", str(e), "Need >= 3 within-subject columns.")
