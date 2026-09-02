# backend/analysis/engine/tests/correlation.py
"""Correlation analysis — Pearson, Spearman, Kendall, partial, canonical, matrix."""
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
    from analysis.engine.bootstrap import bootstrap_r, n_resamples_for
    _BOOTSTRAP_AVAILABLE = True
except Exception:
    _BOOTSTRAP_AVAILABLE = False


def _safe_boot_r(x, y, n, alpha):
    """Bootstrap CI for correlation coefficient. Returns (ci_l, ci_u) or None."""
    if not _BOOTSTRAP_AVAILABLE or n < 4:
        return None
    try:
        ci_l, ci_u, _ = bootstrap_r(x, y, n_resamples=n_resamples_for(n), ci_level=1 - alpha)
        return ci_l, ci_u
    except Exception:
        return None


def _fisher_z_ci(r, n, alpha=0.05):
    """Fisher's z-transformation CI for correlation coefficient."""
    if n <= 3 or abs(r) >= 1:
        return None, None
    z = np.arctanh(r)
    se = 1 / np.sqrt(n - 3)
    z_crit = stats.norm.ppf(1 - alpha / 2)
    return float(np.tanh(z - z_crit * se)), float(np.tanh(z + z_crit * se))


def _interp_r(r):
    r = abs(r)
    if r < 0.10: return "negligible"
    if r < 0.30: return "small"
    if r < 0.50: return "medium"
    return "large"


def run_pearson(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Pearson Correlation", "pearson_correlation", "Need 2 numeric columns.", "Select x and y columns.")
        x_col, y_col = variables[0], variables[1]
        data = df[[x_col, y_col]].dropna()
        r, p = stats.pearsonr(data[x_col], data[y_col])
        n = len(data)
        ci_l, ci_u = _fisher_z_ci(r, n, alpha)
        df_val = n - 2
        t = float(r * np.sqrt(df_val) / np.sqrt(1 - r**2)) if abs(r) < 1 else float("inf")
        # BCa bootstrap CI for r (more robust than Fisher z for non-normal data)
        boot = _safe_boot_r(data[x_col].values, data[y_col].values, n, alpha)
        boot_block = {"lower": round(boot[0], 4), "upper": round(boot[1], 4),
                      "method": "BCa bootstrap", "n_resamples": n_resamples_for(n)} if boot else None
        return build_result("Pearson Correlation", "pearson_correlation",
                            "r", r, p_value=p, n=n, df_val=df_val,
                            significant=bool(p < alpha), ci_lower=ci_l, ci_upper=ci_u,
                            effect_size_name="r", effect_size_value=r,
                            effect_size_interpretation=_interp_r(r),
                            conclusion=f"r({df_val}) = {r:.3f}, p = {p:.4f}. {'Significant' if p<alpha else 'Non-significant'} {('positive' if r>0 else 'negative')} correlation.",
                            additional_stats={"r": round(float(r), 4), "r_squared": round(float(r**2), 4),
                                             "t": round(t, 4),
                                             "fisher_z_ci": [round(ci_l, 4), round(ci_u, 4)] if ci_l else None,
                                             "bootstrap_ci": boot_block})
    except Exception as e:
        return build_error("Pearson Correlation", "pearson_correlation", str(e), "Check that both columns are numeric.")


def run_spearman(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Spearman Correlation", "spearman_correlation", "Need 2 columns.", "Select x and y columns.")
        x_col, y_col = variables[0], variables[1]
        data = df[[x_col, y_col]].dropna()
        rho, p = stats.spearmanr(data[x_col], data[y_col])
        n = len(data)
        ci_l, ci_u = _fisher_z_ci(rho, n, alpha)
        # BCa bootstrap CI for rho
        boot = _safe_boot_r(data[x_col].values, data[y_col].values, n, alpha)
        boot_block = {"lower": round(boot[0], 4), "upper": round(boot[1], 4),
                      "method": "BCa bootstrap", "n_resamples": n_resamples_for(n)} if boot else None
        return build_result("Spearman Rank Correlation", "spearman_correlation",
                            "rho", rho, p_value=p, n=n,
                            significant=bool(p < alpha), ci_lower=ci_l, ci_upper=ci_u,
                            effect_size_name="rho", effect_size_value=rho,
                            effect_size_interpretation=_interp_r(rho),
                            conclusion=f"rho = {rho:.3f}, p = {p:.4f}. {'Significant' if p<alpha else 'Non-significant'} rank correlation.",
                            additional_stats={"rho": round(float(rho), 4),
                                             "fisher_z_ci": [round(ci_l, 4), round(ci_u, 4)] if ci_l else None,
                                             "bootstrap_ci": boot_block})
    except Exception as e:
        return build_error("Spearman Correlation", "spearman_correlation", str(e), "Check column types.")


def run_kendall_tau(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Kendall's Tau", "kendall_tau", "Need 2 columns.", "Select x and y columns.")
        x_col, y_col = variables[0], variables[1]
        data = df[[x_col, y_col]].dropna()
        tau, p = stats.kendalltau(data[x_col], data[y_col])
        n = len(data)
        return build_result("Kendall's Tau Correlation", "kendall_tau",
                            "τ", tau, p_value=p, n=n,
                            significant=bool(p < alpha),
                            effect_size_name="τ", effect_size_value=tau,
                            effect_size_interpretation=_interp_r(tau),
                            conclusion=f"τ = {tau:.3f}, p = {p:.4f}.",
                            additional_stats={"tau": round(float(tau), 4)})
    except Exception as e:
        return build_error("Kendall's Tau", "kendall_tau", str(e), "Check column types.")


def run_point_biserial(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Point-Biserial", "point_biserial", "Need binary col and continuous col.", "Select 2 variables.")
        bin_col, cont_col = variables[0], variables[1]
        data = df[[bin_col, cont_col]].dropna().copy()
        # Encode binary column to 0/1 regardless of dtype (int, bool, or string category)
        col = data[bin_col]
        unique_vals = col.unique()
        if len(unique_vals) != 2:
            return build_error("Point-Biserial", "point_biserial",
                               f"'{bin_col}' has {len(unique_vals)} unique values; point-biserial requires exactly 2.",
                               "Use a dichotomous (binary) variable as the first column.")
        # Map to 0/1 numerically
        if not pd.api.types.is_numeric_dtype(col):
            mapping = {unique_vals[0]: 0, unique_vals[1]: 1}
            col_encoded = col.map(mapping).astype(float)
        else:
            col_encoded = col.astype(float)
        r, p = stats.pointbiserialr(col_encoded.values, data[cont_col].astype(float).values)
        n = len(data)
        return build_result("Point-Biserial Correlation", "point_biserial",
                            "r_pb", r, p_value=p, n=n,
                            significant=bool(p < alpha),
                            effect_size_name="r_pb", effect_size_value=r,
                            effect_size_interpretation=_interp_r(r),
                            conclusion=f"r_pb = {r:.3f}, p = {p:.4f}.",
                            additional_stats={"r_pb": round(float(r), 4),
                                             "groups": list(str(v) for v in unique_vals)})
    except Exception as e:
        return build_error("Point-Biserial", "point_biserial", str(e), "Ensure first column is binary (0/1 or two-category string).")


def run_phi(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Phi Coefficient", "phi_coefficient", "Need 2 binary columns.", "Select 2 binary variables.")
        col1, col2 = variables[0], variables[1]
        data = df[[col1, col2]].dropna()
        ct = pd.crosstab(data[col1], data[col2])
        if ct.shape != (2, 2):
            return build_error("Phi Coefficient", "phi_coefficient", "Requires 2×2 table.", "Use only binary columns.")
        a, b_v, c_v, d = ct.values[0, 0], ct.values[0, 1], ct.values[1, 0], ct.values[1, 1]
        denom_phi = np.sqrt(float((a + b_v) * (c_v + d) * (a + c_v) * (b_v + d)))
        if denom_phi == 0:
            return build_error('Phi Coefficient', 'phi_coefficient', 
                               'One or more marginal totals is zero (empty row or column).', 
                               'Ensure both variables have values in all categories.')
        phi = float((a * d - b_v * c_v) / denom_phi)
        chi2, p, _, _ = stats.chi2_contingency(ct)
        return build_result("Phi Coefficient", "phi_coefficient",
                            "φ", phi, p_value=p, n=int(ct.values.sum()),
                            significant=bool(p < alpha),
                            effect_size_name="φ", effect_size_value=phi,
                            effect_size_interpretation=_interp_r(phi),
                            additional_stats={"phi": round(phi, 4), "chi2": round(float(chi2), 4)})
    except Exception as e:
        return build_error("Phi Coefficient", "phi_coefficient", str(e), "Ensure both columns are binary.")


def run_cramers_v(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 2:
            return build_error("Cramer's V", "cramers_v", "Need 2 categorical columns.", "Select 2 categorical variables.")
        col1, col2 = variables[0], variables[1]
        data = df[[col1, col2]].dropna()
        ct = pd.crosstab(data[col1], data[col2])
        chi2, p, dof, _ = stats.chi2_contingency(ct)
        n = int(ct.values.sum())
        min_dim = min(ct.shape) - 1
        V = float(np.sqrt(chi2 / (n * min_dim))) if min_dim > 0 and n > 0 else 0.0
        return build_result("Cramer's V", "cramers_v",
                            "V", V, p_value=p, n=n,
                            significant=bool(p < alpha),
                            effect_size_name="V", effect_size_value=V,
                            effect_size_interpretation=_interp_r(V),
                            conclusion=f"V = {V:.3f}, χ²({dof}) = {chi2:.3f}, p = {p:.4f}.",
                            additional_stats={"cramers_v": round(V, 4), "chi2": round(float(chi2), 4), "df": dof})
    except Exception as e:
        return build_error("Cramer's V", "cramers_v", str(e), "Check categorical column types.")


def run_partial_correlation(df, variables, brief, alpha=0.05):
    try:
        if len(variables) < 3:
            return build_error("Partial Correlation", "partial_correlation", "Need x, y, and covariate.", "Select 3 columns.")
        x_col, y_col, cov_col = variables[0], variables[1], variables[2]
        # Ensure all three columns are numeric
        num_vars = [c for c in [x_col, y_col, cov_col] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(num_vars) < 3:
            return build_error("Partial Correlation", "partial_correlation",
                               "All 3 variables must be numeric.", "Select 3 numeric columns.")
        data = df[num_vars].dropna()
        n = len(data)
        if n < 5:
            return build_error("Partial Correlation", "partial_correlation",
                               f"Too few observations (n={n}). Need >= 5.", "Collect more data.")

        r, p, ci = None, None, [None, None]
        if pg is not None:
            try:
                res = pg.partial_corr(data=data, x=x_col, y=y_col, covar=cov_col)
                r = float(res["r"].iloc[0])
                # Handle both pingouin <=0.5 ('p-val') and >=0.5.4 ('p-unc')
                p_col = next((c for c in ["p-unc", "p-val", "pval"] if c in res.columns), None)
                p = float(res[p_col].iloc[0]) if p_col else None
                if "CI95%" in res.columns:
                    ci = list(res["CI95%"].iloc[0])
            except Exception:
                r = p = None  # fall through to manual

        if r is None:
            # Manual residual-based partial correlation
            def residuals(var_arr, cov_arr):
                slope, intercept, _, _, _ = stats.linregress(cov_arr, var_arr)
                return var_arr - (slope * cov_arr + intercept)
            rx = residuals(data[x_col].values, data[cov_col].values)
            ry = residuals(data[y_col].values, data[cov_col].values)
            r, p = stats.pearsonr(rx, ry)
            ci_l, ci_u = _fisher_z_ci(float(r), n, alpha)
            ci = [ci_l, ci_u]

        if p is None:
            p = float(stats.pearsonr(data[x_col], data[y_col])[1])  # fallback p

        return build_result("Partial Correlation", "partial_correlation",
                            "r", r, p_value=p, n=n,
                            significant=bool(p < alpha),
                            ci_lower=ci[0] if ci[0] is not None else None,
                            ci_upper=ci[1] if ci[1] is not None else None,
                            effect_size_name="r", effect_size_value=r,
                            effect_size_interpretation=_interp_r(r),
                            conclusion=f"Partial r = {r:.3f}, p = {p:.4f} (controlling for {cov_col}).",
                            additional_stats={
                                "r": round(float(r), 4),
                                "covariate": cov_col,
                                "ci": [round(float(c), 4) for c in ci if c is not None],
                            })
    except Exception as e:
        return build_error("Partial Correlation", "partial_correlation", str(e), "Check that all 3 columns are numeric.")


def run_canonical_correlation(df, variables, brief, alpha=0.05):
    try:
        num_cols = [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(num_cols) < 4:
            return build_error("Canonical Correlation", "canonical_correlation", "Need >= 4 numeric columns.", "Select 2+ X and 2+ Y variables.")
        mid = len(num_cols) // 2
        set1, set2 = num_cols[:mid], num_cols[mid:]
        data = df[num_cols].dropna()
        X = data[set1].values; Y = data[set2].values
        X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-10)
        Y = (Y - Y.mean(axis=0)) / (Y.std(axis=0) + 1e-10)
        Cxx = np.cov(X.T); Cyy = np.cov(Y.T); Cxy = np.cov(X.T, Y.T)[:X.shape[1], X.shape[1]:]
        try:
            Cxx_inv_sqrt = np.linalg.inv(np.linalg.cholesky(Cxx + np.eye(Cxx.shape[0]) * 1e-8))
            Cyy_inv_sqrt = np.linalg.inv(np.linalg.cholesky(Cyy + np.eye(Cyy.shape[0]) * 1e-8))
        except Exception:
            Cxx_inv_sqrt = np.linalg.pinv(Cxx)
            Cyy_inv_sqrt = np.linalg.pinv(Cyy)
        T = Cxx_inv_sqrt.T @ Cxy @ Cyy_inv_sqrt
        U, s, Vt = np.linalg.svd(T, full_matrices=False)
        canonical_correlations = [round(float(v), 4) for v in s]
        n, p, q = len(data), len(set1), len(set2)
        # Wilks' lambda approximation
        wilks = float(np.prod(1 - np.array(s)**2))
        return build_result("Canonical Correlation Analysis", "canonical_correlation",
                            "Rc", canonical_correlations[0] if canonical_correlations else None, n=n,
                            additional_stats={"canonical_correlations": canonical_correlations,
                                             "wilks_lambda": round(wilks, 4), "set1": set1, "set2": set2,
                                             "n_functions": len(canonical_correlations)})
    except Exception as e:
        return build_error("Canonical Correlation", "canonical_correlation", str(e), "Need >= 4 numeric columns split into 2 sets.")


def run_correlation_matrix(df, variables, brief, alpha=0.05):
    try:
        num_cols = [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(num_cols) < 2:
            return build_error("Correlation Matrix", "correlation_matrix", "Need >= 2 numeric columns.", "Select numeric variables.")
        data = df[num_cols].dropna()
        r_matrix = data.corr(method="pearson")
        n = len(data)
        # P-value matrix
        p_matrix = pd.DataFrame(np.ones((len(num_cols), len(num_cols))), index=num_cols, columns=num_cols)
        for i, c1 in enumerate(num_cols):
            for j, c2 in enumerate(num_cols):
                if i != j:
                    _, p = stats.pearsonr(data[c1], data[c2])
                    p_matrix.loc[c1, c2] = round(float(p), 4)
        # Table of all pairs
        table = []
        for i, c1 in enumerate(num_cols):
            for j, c2 in enumerate(num_cols):
                if j > i:
                    r = float(r_matrix.loc[c1, c2])
                    p = float(p_matrix.loc[c1, c2])
                    table.append({"var1": c1, "var2": c2, "r": round(r, 4), "p": round(p, 4), "significant": bool(p < alpha)})
        return build_result("Correlation Matrix", "correlation_matrix",
                            "r", None, n=n,
                            additional_stats={"matrix": r_matrix.round(4).to_dict(),
                                             "p_matrix": p_matrix.round(4).to_dict(),
                                             "variables": num_cols},
                            table=table)
    except Exception as e:
        return build_error("Correlation Matrix", "correlation_matrix", str(e), "Check numeric column selection.")


def run_correlation_significance(df, variables, brief, alpha=0.05):
    try:
        base = run_correlation_matrix(df, variables, brief, alpha)
        if base.get("error"):
            return base
        sig_pairs = [row for row in (base.get("table") or []) if row.get("significant")]
        base["additional_stats"]["significant_pairs"] = sig_pairs
        base["additional_stats"]["n_significant"] = len(sig_pairs)
        base["additional_stats"]["n_total_pairs"] = len(base.get("table") or [])
        return base
    except Exception as e:
        return build_error("Correlation Significance", "correlation_significance", str(e), "Check column types.")
