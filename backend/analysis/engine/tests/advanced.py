# backend/analysis/engine/tests/advanced.py
"""Advanced multivariate tests — PCA, EFA, CFA, LDA, Cluster, Mediation, Moderation, SEM."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error

try:
    from sklearn.decomposition import PCA, FactorAnalysis
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.metrics import silhouette_score
    _sklearn = True
except ImportError:
    _sklearn = False

try:
    from factor_analyzer import FactorAnalyzer
    _fa_lib = True
except ImportError:
    _fa_lib = False

try:
    import statsmodels.api as sm
except ImportError:
    sm = None


def _num_cols(df, variables):
    return [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]


def run_pca(df, variables, brief, alpha=0.05):
    try:
        if not _sklearn:
            return build_error("PCA", "pca", "scikit-learn not installed.", "pip install scikit-learn")
        cols = _num_cols(df, variables)
        if len(cols) < 2:
            return build_error("PCA", "pca", "Need >= 2 numeric variables.", "Select numeric columns.")
        data = df[cols].dropna()
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(data)
        pca = PCA()
        pca.fit(X_scaled)
        eigenvalues = [round(float(e), 4) for e in pca.explained_variance_]
        var_explained = [round(float(v * 100), 2) for v in pca.explained_variance_ratio_]
        cumulative_var = [round(float(c * 100), 2) for c in np.cumsum(pca.explained_variance_ratio_)]
        n_retain = int(np.sum(np.array(eigenvalues) >= 1.0)) or 1
        # Loadings matrix (components × features, each row is a PC)
        loadings = pca.components_.T  # shape: (n_features, n_components)
        loadings_table = []
        for i, col in enumerate(cols):
            row = {"variable": col}
            for pc in range(min(n_retain, len(cols))):
                row[f"PC{pc+1}"] = round(float(loadings[i, pc]), 4)
            loadings_table.append(row)
        scree_data = [{"pc": i + 1, "eigenvalue": ev, "variance_pct": vr}
                      for i, (ev, vr) in enumerate(zip(eigenvalues, var_explained))]
        return build_result("Principal Component Analysis", "pca",
                            "n_components", n_retain, n=len(data),
                            additional_stats={
                                "n_components_retained": n_retain,
                                "eigenvalues": eigenvalues,
                                "variance_explained_pct": var_explained,
                                "cumulative_variance_pct": cumulative_var,
                                "loadings": loadings_table,
                                "scree_data": scree_data,
                                "total_variance_explained": round(cumulative_var[n_retain - 1] if n_retain <= len(cumulative_var) else 100.0, 2),
                            }, table=loadings_table)
    except Exception as e:
        return build_error("PCA", "pca", str(e), "Check numeric variable selection.")


def run_efa(df, variables, brief, alpha=0.05):
    try:
        cols = _num_cols(df, variables)
        if len(cols) < 3:
            return build_error("EFA", "factor_analysis", "Need >= 3 numeric variables.", "Select scale items.")
        data = df[cols].dropna()
        n_factors = int(brief.get("n_factors", 0) or 0) or max(1, len(cols) // 3)
        if _fa_lib:
            fa = FactorAnalyzer(n_factors=n_factors, rotation="oblimin")
            fa.fit(data)
            loadings = fa.loadings_
            communalities = fa.get_communalities()
            uniqueness = 1 - communalities
            var_exp = fa.get_factor_variance()
            loadings_table = []
            for i, col in enumerate(cols):
                row = {"variable": col, "communality": round(float(communalities[i]), 4),
                       "uniqueness": round(float(uniqueness[i]), 4)}
                for f in range(n_factors):
                    row[f"F{f+1}"] = round(float(loadings[i, f]), 4)
                loadings_table.append(row)
            variance_table = [{"factor": f"F{i+1}", "ss_loadings": round(float(var_exp[0][i]), 4),
                               "pct_variance": round(float(var_exp[1][i] * 100), 2),
                               "cumulative_pct": round(float(var_exp[2][i] * 100), 2)}
                              for i in range(n_factors)]
        elif _sklearn:
            fa_sk = FactorAnalysis(n_components=n_factors, random_state=42)
            fa_sk.fit(data)
            loadings = fa_sk.components_.T
            communalities = np.sum(loadings**2, axis=1)
            uniqueness = fa_sk.noise_variance_
            loadings_table = [{"variable": col,
                               "communality": round(float(communalities[i]), 4),
                               "uniqueness": round(float(uniqueness[i]), 4),
                               **{f"F{f+1}": round(float(loadings[i, f]), 4) for f in range(n_factors)}}
                              for i, col in enumerate(cols)]
            variance_table = []
        else:
            return build_error("EFA", "factor_analysis", "Neither factor_analyzer nor scikit-learn installed.", "pip install factor_analyzer scikit-learn")
        return build_result("Exploratory Factor Analysis", "factor_analysis",
                            "n_factors", n_factors, n=len(data),
                            additional_stats={"n_factors": n_factors, "rotation": "oblimin" if _fa_lib else "varimax",
                                             "loadings": loadings_table, "variance_explained": variance_table},
                            table=loadings_table)
    except Exception as e:
        return build_error("EFA", "factor_analysis", str(e), "Check numeric variable selection.")


def _compute_ave_htmt_cr(loadings_matrix: np.ndarray, cols: list, n_factors: int) -> dict:
    """
    Compute AVE, Composite Reliability (CR), and HTMT for each factor.
    AVE  >= 0.50 → convergent validity
    HTMT < 0.90  → discriminant validity
    CR   >= 0.70 → composite reliability
    """
    results = {}
    for f in range(n_factors):
        factor_loadings = loadings_matrix[:, f]
        lam2 = factor_loadings ** 2
        ave  = float(np.mean(lam2))             # Average Variance Extracted
        cr   = float((np.sum(np.abs(factor_loadings))**2) /
                     (np.sum(np.abs(factor_loadings))**2 + np.sum(1 - lam2)))  # Composite Reliability
        results[f"Factor{f+1}"] = {
            "AVE":  round(ave, 4),
            "CR":   round(cr,  4),
            "AVE_ok": ave >= 0.50,
            "CR_ok":  cr  >= 0.70,
        }

    # HTMT (Heterotrait-Monotrait ratio) — between each factor pair
    htmt_pairs = []
    if n_factors > 1:
        for i in range(n_factors):
            for j in range(i + 1, n_factors):
                li = loadings_matrix[:, i]
                lj = loadings_matrix[:, j]
                # Geometric mean of avg hetero-trait correlations / avg mono-trait correlations
                hetero = float(np.mean(np.abs(li * lj)))
                mono_i = float(np.mean(np.abs(np.outer(li, li)[np.tril_indices(len(li), -1)])))
                mono_j = float(np.mean(np.abs(np.outer(lj, lj)[np.tril_indices(len(lj), -1)])))
                denom  = float(np.sqrt(mono_i * mono_j)) if mono_i * mono_j > 0 else 1.0
                htmt   = round(hetero / denom, 4)
                htmt_pairs.append({
                    "factors": f"Factor{i+1} ↔ Factor{j+1}",
                    "HTMT": htmt,
                    "discriminant_validity": htmt < 0.90,
                })
    results["HTMT"] = htmt_pairs
    return results


def run_cfa(df, variables, brief, alpha=0.05):
    """Confirmatory Factor Analysis — full fit indices.
    Primary: semopy (full CFA with fit indices).
    Fallback: sklearn FactorAnalysis with comprehensive fit indices:
              CFI, TLI, RMSEA + 90% CI + p-close, SRMR, χ², AIC, BIC,
              standardized loadings with p-values, AVE, HTMT, CR.
    """
    try:
        cols = [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(cols) < 3:
            return build_error("CFA", "confirmatory_fa",
                               "Need ≥ 3 numeric indicator variables.",
                               "Select at least 3 numeric items.")
        data = df[cols].dropna()
        n, p = len(data), len(cols)

        # ── Try semopy first ──────────────────────────────────────────────────
        try:
            import semopy
            model_syntax = brief.get("cfa_model_syntax")
            if not model_syntax:
                # Auto-generate single-factor CFA syntax
                model_syntax = "Factor1 =~ " + " + ".join(cols)
            model = semopy.Model(model_syntax)
            model.fit(data)
            # semopy >= 2.x: module-level calc_stats(model) returns a DataFrame
            fit_df = semopy.calc_stats(model)
            row = fit_df.iloc[0]  # single-row DataFrame
            _g = lambda key, fallback=np.nan: float(row[key]) if key in fit_df.columns else fallback
            cfi_val = _g("CFI"); rmsea_val = _g("RMSEA")
            fit_ok = cfi_val >= 0.90 and rmsea_val <= 0.08
            interp = "acceptable fit" if fit_ok else "poor fit — consider model revision"
            return build_result("Confirmatory Factor Analysis", "confirmatory_fa",
                                "CFI", cfi_val, n=n,
                                conclusion=f"CFA: CFI={cfi_val:.3f}, RMSEA={rmsea_val:.3f}. {interp}.",
                                additional_stats={"CFI": round(cfi_val, 4),
                                                 "RMSEA": round(rmsea_val, 4),
                                                 "TLI": round(_g("TLI"), 4),
                                                 "GFI": round(_g("GFI"), 4),
                                                 "chi2": round(_g("chi2"), 4),
                                                 "chi2_pvalue": round(_g("chi2 p-value"), 4),
                                                 "df": int(_g("DoF", 0)),
                                                 "AIC": round(_g("AIC"), 4),
                                                 "BIC": round(_g("BIC"), 4),
                                                 "method": "semopy"})
        except ImportError:
            pass  # Fall through to native implementation

        # ── Native fallback: sklearn FactorAnalysis with full fit indices ──────
        from sklearn.decomposition import FactorAnalysis
        from sklearn.preprocessing import StandardScaler
        from scipy import stats as _stats

        model_syntax = brief.get("cfa_model_syntax", "")
        n_factors = max(1, model_syntax.count("=~")) if model_syntax else 1

        scaler = StandardScaler()
        X = scaler.fit_transform(data.values.astype(float))

        fa = FactorAnalysis(n_components=n_factors, random_state=42, max_iter=1000)
        fa.fit(X)
        loadings = fa.components_.T          # shape (p, n_factors)

        # ── Observed / reproduced correlation matrices ─────────────────────────
        R_obs = np.corrcoef(X, rowvar=False)
        R_rep = loadings @ loadings.T
        np.fill_diagonal(R_rep, 1.0)
        residuals = R_obs - R_rep

        # ── SRMR ─────────────────────────────────────────────────────────────
        off_diag = residuals[np.tril_indices(p, -1)]
        srmr = float(np.sqrt(np.mean(off_diag ** 2)))

        # ── Chi-square (Bartlett) ─────────────────────────────────────────────
        dof = max((p * (p - 1)) // 2 - p * n_factors + n_factors * (n_factors - 1) // 2, 1)
        chi2_val = (n - 1) * float(np.sum(residuals ** 2))
        p_chi2   = float(_stats.chi2.sf(chi2_val, dof))

        # ── RMSEA + 90% CI + p-close ──────────────────────────────────────────
        rmsea = float(np.sqrt(max(0.0, (chi2_val / dof - 1) / max(n - 1, 1))))
        # 90% CI via chi2 non-centrality
        lambda_lo = max(0.0, chi2_val - 1.645 * np.sqrt(2 * dof))  # lower ncp
        lambda_hi = chi2_val + 1.645 * np.sqrt(2 * dof)            # upper ncp
        rmsea_lo  = float(np.sqrt(max(0.0, lambda_lo / (dof * max(n - 1, 1)))))
        rmsea_hi  = float(np.sqrt(lambda_hi / (dof * max(n - 1, 1))))
        # p-close: P(RMSEA <= 0.05)
        ncp_close = max(0.0, (0.05 ** 2) * dof * (n - 1))
        p_close   = float(_stats.chi2.sf(chi2_val, dof, loc=0, scale=1)) if dof > 0 else 1.0

        # ── Null model chi-square ─────────────────────────────────────────────
        R_null    = np.eye(p)
        chi2_null = (n - 1) * float(np.sum((R_obs - R_null) ** 2))
        dof_null  = p * (p - 1) // 2

        # ── CFI ───────────────────────────────────────────────────────────────
        cfi = float(max(0.0, min(1.0,
            1 - (chi2_val - dof) / max(chi2_null - dof_null, 1e-9)
        )))

        # ── TLI (Tucker-Lewis Index / NNFI) ───────────────────────────────────
        tli = float(max(0.0, min(1.0,
            ((chi2_null / dof_null) - (chi2_val / dof)) /
            max((chi2_null / dof_null) - 1, 1e-9)
        )))

        # ── AIC / BIC (log-likelihood approximation) ──────────────────────────
        log_det_obs = float(np.log(np.linalg.det(R_obs) + 1e-12))
        log_det_rep = float(np.log(np.linalg.det(R_rep) + 1e-12))
        n_free = p * n_factors + p  # loadings + uniquenesses
        log_lik = -0.5 * n * (log_det_rep - log_det_obs + float(np.trace(np.linalg.pinv(R_rep) @ R_obs)) - p)
        aic = float(-2 * log_lik + 2 * n_free)
        bic = float(-2 * log_lik + np.log(n) * n_free)

        # ── Standardized loadings with approx. t-statistics ───────────────────
        se_approx = 1.0 / np.sqrt(max(n - n_free, 1))  # approximate SE
        loading_table = []
        for i in range(p):
            row = {"indicator": cols[i]}
            for j in range(n_factors):
                lam = float(loadings[i, j])
                t   = lam / se_approx if se_approx > 0 else 0.0
                pv  = float(2 * _stats.t.sf(abs(t), df=max(n - n_free, 1)))
                row[f"Factor{j+1}"]       = round(lam, 4)
                row[f"Factor{j+1}_t"]     = round(t,   3)
                row[f"Factor{j+1}_p"]     = round(pv,  4)
                row[f"Factor{j+1}_sig"]   = "***" if pv < .001 else "**" if pv < .01 else "*" if pv < .05 else ""
            row["communality"] = round(float(np.sum(loadings[i, :] ** 2)), 4)
            loading_table.append(row)

        # ── AVE, HTMT, CR ─────────────────────────────────────────────────────
        validity = _compute_ave_htmt_cr(loadings, cols, n_factors)

        # ── Modification indices (top 5 largest residuals) ────────────────────
        mod_indices = []
        for i in range(p):
            for j in range(i + 1, p):
                mi = float((n - 1) * residuals[i, j] ** 2)
                mod_indices.append({"pair": f"{cols[i]} ↔ {cols[j]}", "MI": round(mi, 3)})
        mod_indices = sorted(mod_indices, key=lambda x: x["MI"], reverse=True)[:10]

        # ── Fit evaluation ────────────────────────────────────────────────────
        fit_criteria = {
            "CFI ≥ 0.95":    {"value": round(cfi,   4), "pass": cfi   >= 0.95},
            "TLI ≥ 0.95":    {"value": round(tli,   4), "pass": tli   >= 0.95},
            "RMSEA ≤ 0.06":  {"value": round(rmsea, 4), "pass": rmsea <= 0.06},
            "SRMR ≤ 0.08":   {"value": round(srmr,  4), "pass": srmr  <= 0.08},
        }
        n_pass = sum(1 for v in fit_criteria.values() if v["pass"])
        if n_pass == 4:    interpretation = "excellent fit"
        elif n_pass >= 3:  interpretation = "acceptable fit"
        elif n_pass >= 2:  interpretation = "marginal fit — consider model revision"
        else:              interpretation = "poor fit — model revision required"

        return build_result(
            "Confirmatory Factor Analysis", "confirmatory_fa",
            "CFI", cfi, p_value=p_chi2, n=n,
            significant=bool(p_chi2 < alpha),
            conclusion=(
                f"CFA ({n_factors} factor(s), N={n}): "
                f"CFI={cfi:.3f}, TLI={tli:.3f}, RMSEA={rmsea:.3f} "
                f"[{rmsea_lo:.3f}, {rmsea_hi:.3f}], SRMR={srmr:.3f}. {interpretation}."
            ),
            additional_stats={
                # Global fit
                "CFI":         round(cfi,   4),
                "TLI":         round(tli,   4),
                "RMSEA":       round(rmsea, 4),
                "RMSEA_lo90":  round(rmsea_lo, 4),
                "RMSEA_hi90":  round(rmsea_hi, 4),
                "RMSEA_p_close": round(p_close, 4),
                "SRMR":        round(srmr,  4),
                "chi2":        round(chi2_val, 4),
                "df":          dof,
                "p_chi2":      round(p_chi2,  4),
                "chi2_ratio":  round(chi2_val / dof, 4),
                "AIC":         round(aic, 2),
                "BIC":         round(bic, 2),
                # Fit criteria table
                "fit_criteria": fit_criteria,
                # Loadings
                "loadings":    loading_table,
                "n_factors":   n_factors,
                "n_indicators": p,
                # Validity
                "validity":    validity,
                # Diagnostics
                "modification_indices": mod_indices,
                "method":      "native (sklearn FactorAnalysis)",
            },
            table=loading_table
        )
    except Exception as e:
        return build_error("CFA", "confirmatory_fa", str(e), "Check numeric variable selection.")





def run_discriminant_analysis(df, variables, brief, alpha=0.05):
    try:
        if not _sklearn:
            return build_error("LDA", "discriminant_analysis", "scikit-learn not installed.", "pip install scikit-learn")
        if len(variables) < 2:
            return build_error("LDA", "discriminant_analysis", "Need group_col and predictor columns.", "Select variables.")
        group_col = variables[0]; predictors = [c for c in variables[1:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if not predictors:
            return build_error("LDA", "discriminant_analysis", "No numeric predictors found.", "Select numeric predictor columns.")
        data = df[[group_col] + predictors].dropna()
        X = data[predictors].values; y = data[group_col].values
        lda = LinearDiscriminantAnalysis()
        lda.fit(X, y)
        preds = lda.predict(X)
        accuracy = float(np.mean(preds == y) * 100)
        eigenvalues = [round(float(e), 4) for e in lda.explained_variance_ratio_]
        n_funcs = len(eigenvalues)
        # Structure matrix: correlations of predictors with canonical discriminant functions
        structure = [{"predictor": p, **{f"Function{i+1}": round(float(lda.scalings_[j, i]), 4) if j < lda.scalings_.shape[0] and i < lda.scalings_.shape[1] else None
                                         for i in range(n_funcs)}}
                     for j, p in enumerate(predictors)]
        group_centroids = [{"group": str(cls), "centroid": [round(float(lda.transform([lda.means_[i]])[0][f]), 4)
                                                              for f in range(n_funcs)]}
                           for i, cls in enumerate(lda.classes_)]
        return build_result("Linear Discriminant Analysis", "discriminant_analysis",
                            "accuracy", accuracy, n=len(data),
                            additional_stats={
                                "n_functions": n_funcs,
                                "canonical_correlations": eigenvalues,
                                "classification_accuracy_pct": round(accuracy, 2),
                                "structure_matrix": structure,
                                "group_centroids": group_centroids,
                                "classes": list(lda.classes_.astype(str)),
                            })
    except Exception as e:
        return build_error("LDA", "discriminant_analysis", str(e), "Check group and predictor columns.")


def run_cluster_analysis(df, variables, brief, alpha=0.05):
    try:
        if not _sklearn:
            return build_error("Cluster Analysis", "cluster_analysis", "scikit-learn not installed.", "pip install scikit-learn")
        cols = _num_cols(df, variables)
        if not cols:
            return build_error("Cluster Analysis", "cluster_analysis", "No numeric variables found.", "Select numeric columns.")
        k = int(brief.get("n_clusters", 3) or 3)
        data = df[cols].dropna()
        scaler = StandardScaler()
        X = scaler.fit_transform(data)
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        sil = float(silhouette_score(X, labels)) if k > 1 and len(set(labels)) > 1 else None
        wcss = float(km.inertia_)
        sizes = pd.Series(labels).value_counts().sort_index()
        centroids = scaler.inverse_transform(km.cluster_centers_)
        centroid_table = [{"cluster": int(i), "size": int(sizes.get(i, 0)),
                           **{col: round(float(centroids[i, j]), 4) for j, col in enumerate(cols)}}
                          for i in range(k)]
        return build_result("K-Means Cluster Analysis", "cluster_analysis",
                            "k", k, n=len(data),
                            additional_stats={
                                "k": k, "silhouette_score": round(sil, 4) if sil else None,
                                "wcss": round(wcss, 4),
                                "cluster_sizes": sizes.to_dict(),
                                "cluster_centroids": centroid_table,
                            }, table=centroid_table)
    except Exception as e:
        return build_error("Cluster Analysis", "cluster_analysis", str(e), "Check numeric variable selection.")


def run_mediation(df, variables, brief, alpha=0.05):
    """Delegate to regression module mediation (same implementation)."""
    from analysis.engine.tests.regression import run_mediation_analysis
    return run_mediation_analysis(df, variables, brief, alpha)


def run_moderation(df, variables, brief, alpha=0.05):
    """Delegate to regression module moderation (same implementation)."""
    from analysis.engine.tests.regression import run_moderation_analysis
    return run_moderation_analysis(df, variables, brief, alpha)


def run_sem(df, variables, brief, alpha=0.05):
    """Structural Equation Modeling.
    Primary: semopy (full SEM with latent variables + fit indices).
    Fallback: OLS-based path analysis chain — no semopy required.
              Builds direct/indirect path coefficients and global R² per equation.
    """
    try:
        num_cols = [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(num_cols) < 2:
            return build_error("SEM", "sem", "Need ≥ 2 numeric variables.", "Select numeric variables.")
        data = df[num_cols].dropna()
        n = len(data)

        # ── Try semopy first ──────────────────────────────────────────────────
        try:
            import semopy
            model_syntax = brief.get("sem_model_syntax")
            if not model_syntax:
                # Auto-generate simple mediation chain syntax
                if len(num_cols) >= 3:
                    mediators = num_cols[1:-1]
                    dv = num_cols[-1]
                    iv = num_cols[0]
                    lines = [f"{dv} ~ {iv} + {' + '.join(mediators)}"]
                    for med in mediators:
                        lines.append(f"{med} ~ {iv}")
                    model_syntax = "\n".join(lines)
                else:
                    model_syntax = f"{num_cols[-1]} ~ {num_cols[0]}"
            cols = [c for c in variables if c in df.columns]
            model = semopy.Model(model_syntax)
            model.fit(data[cols].dropna())
            # semopy >= 2.x: module-level calc_stats(model) returns a DataFrame
            fit_df = semopy.calc_stats(model)
            row = fit_df.iloc[0]
            _g = lambda key, fallback=np.nan: float(row[key]) if key in fit_df.columns else fallback
            params = model.inspect()
            param_table = params.to_dict(orient="records") if params is not None else []
            cfi_val = _g("CFI"); rmsea_val = _g("RMSEA")
            return build_result("Structural Equation Modeling", "sem",
                                "CFI", cfi_val, n=n,
                                conclusion=f"SEM: CFI={cfi_val:.3f}, RMSEA={rmsea_val:.3f}.",
                                additional_stats={"CFI": round(cfi_val, 4),
                                                 "RMSEA": round(rmsea_val, 4),
                                                 "TLI": round(_g("TLI"), 4),
                                                 "GFI": round(_g("GFI"), 4),
                                                 "chi2": round(_g("chi2"), 4),
                                                 "chi2_pvalue": round(_g("chi2 p-value"), 4),
                                                 "df": int(_g("DoF", 0)),
                                                 "AIC": round(_g("AIC"), 4),
                                                 "BIC": round(_g("BIC"), 4),
                                                 "parameter_estimates": param_table,
                                                 "method": "semopy"})
        except ImportError:
            pass  # Fall through to native OLS path chain

        # ── Native fallback: OLS path-chain ──────────────────────────────────
        if sm is None:
            return build_error("SEM", "sem", "statsmodels not installed.", "pip install statsmodels")

        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_std = pd.DataFrame(
            scaler.fit_transform(data.astype(float)),
            columns=num_cols
        )

        # Build chain: each variable (except IV) predicted by all preceding variables
        iv = num_cols[0]
        equations = []
        all_r2 = []
        path_matrix = {}

        for i in range(1, len(num_cols)):
            dv = num_cols[i]
            predictors = num_cols[:i]  # all variables before this one in chain
            X = sm.add_constant(X_std[predictors].astype(float))
            Y = X_std[dv].astype(float)
            ols = sm.OLS(Y, X).fit()
            paths = {p: {"beta": round(float(ols.params[p]), 4),
                         "se": round(float(ols.bse[p]), 4),
                         "t": round(float(ols.tvalues[p]), 4),
                         "p": round(float(ols.pvalues[p]), 4),
                         "sig": bool(ols.pvalues[p] < alpha)}
                     for p in ols.params.index if p != "const"}
            path_matrix[dv] = paths
            all_r2.append(round(float(ols.rsquared), 4))
            equations.append({
                "outcome": dv,
                "predictors": predictors,
                "R2": round(float(ols.rsquared), 4),
                "adj_R2": round(float(ols.rsquared_adj), 4),
                "F": round(float(ols.fvalue), 4),
                "p_F": round(float(ols.f_pvalue), 4),
                "paths": paths,
            })

        # Compute indirect effect IV → DV via all mediators (product-of-coefficients)
        dv_final = num_cols[-1]
        direct = path_matrix.get(dv_final, {}).get(iv, {}).get("beta", None)
        indirect = None
        if len(num_cols) >= 3:
            mediators = num_cols[1:-1]
            # Simple chain indirect: β(IV→Med1) × β(Med1→DV) [first mediator only for simplicity]
            med = mediators[0]
            b_iv_med = path_matrix.get(med, {}).get(iv, {}).get("beta")
            b_med_dv = path_matrix.get(dv_final, {}).get(med, {}).get("beta")
            if b_iv_med is not None and b_med_dv is not None:
                indirect = round(float(b_iv_med * b_med_dv), 4)

        mean_r2 = round(float(np.mean(all_r2)), 4)
        conclusion = (f"SEM (OLS path chain, {len(equations)} equation(s)): "
                      f"mean R²={mean_r2:.3f}. "
                      f"Direct {iv}→{dv_final}: {direct}. "
                      f"Indirect: {indirect}.")

        return build_result("Structural Equation Modeling (native OLS)", "sem",
                            "mean_R2", mean_r2, n=n,
                            conclusion=conclusion,
                            additional_stats={
                                "method": "native OLS path chain",
                                "n_equations": len(equations),
                                "mean_R2": mean_r2,
                                "direct_effect": direct,
                                "indirect_effect": indirect,
                                "equations": equations,
                                "path_coefficients": path_matrix,
                            }, table=equations)
    except Exception as e:
        return build_error("SEM", "sem", str(e), "Check variable selection and data types.")




def run_path_analysis(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Path Analysis", "path_analysis", "statsmodels not installed.", "pip install statsmodels")
        path_model = brief.get("path_model")
        if not path_model:
            # Build a simple chain: variables[0] is IV, variables[-1] is DV, variables[1:-1] are mediators
            if len(variables) < 2:
                return build_error("Path Analysis", "path_analysis", "Need >= 2 variables.", "Select path variables.")
            dv = variables[-1]; ivs = variables[:-1]
            path_model = {dv: ivs}
        # Run OLS for each endogenous variable
        path_coefs = {}
        for endo, exo_list in path_model.items():
            valid_exo = [c for c in exo_list if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
            valid_endo = endo if endo in df.columns else None
            if not valid_endo or not valid_exo:
                continue
            data = df[[valid_endo] + valid_exo].dropna()
            X = sm.add_constant(data[valid_exo].astype(float))
            model = sm.OLS(data[valid_endo].astype(float), X).fit()
            path_coefs[valid_endo] = {
                "r_squared": round(float(model.rsquared), 4),
                "paths": {name: round(float(model.params[name]), 4) for name in model.params.index[1:]}
            }
        return build_result("Path Analysis", "path_analysis",
                            "N paths", len(path_coefs), n=len(df),
                            additional_stats={"path_coefficients": path_coefs})
    except Exception as e:
        return build_error("Path Analysis", "path_analysis", str(e), "Check path model specification.")
