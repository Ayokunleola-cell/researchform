# backend/analysis/engine/tests/regression.py
"""Regression analysis — OLS, logistic, hierarchical, mediation, moderation, etc."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error, interpret_effect_size

try:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    from statsmodels.stats.stattools import durbin_watson as dw_stat
except ImportError:
    sm = None; smf = None; variance_inflation_factor = None; dw_stat = None

try:
    from analysis.engine.bootstrap import n_resamples_for
    _BOOTSTRAP_AVAILABLE = True
except Exception:
    _BOOTSTRAP_AVAILABLE = False
    def n_resamples_for(n): return 1000


def _coef_table(model, col_names):
    table = []
    params = model.params; bse = model.bse; tvalues = model.tvalues; pvalues = model.pvalues
    conf = model.conf_int()
    for name in params.index:
        table.append({
            "predictor": name,
            "b": round(float(params[name]), 4),
            "SE": round(float(bse[name]), 4),
            "t": round(float(tvalues[name]), 4),
            "p": round(float(pvalues[name]), 4),
            "CI_lower": round(float(conf.loc[name, 0]), 4),
            "CI_upper": round(float(conf.loc[name, 1]), 4),
        })
    return table


def _robust_coef_table(model, cov_type='HC3'):
    """Compute HC3 robust standard errors. Returns (table, f_pvalue) or (None, None) on failure."""
    try:
        robust_results = model.get_robustcov_results(cov_type=cov_type)
        table = []
        
        # In some versions of statsmodels, robust_results.params drops the pandas index.
        # We can borrow the index from the original model.
        if hasattr(model.params, 'index'):
            names = model.params.index
        elif hasattr(robust_results.params, 'index'):
            names = robust_results.params.index
        else:
            names = range(len(robust_results.params))
            
        params  = robust_results.params
        bse     = robust_results.bse
        tvalues = robust_results.tvalues
        pvalues = robust_results.pvalues
        conf    = robust_results.conf_int()
        
        for i, name in enumerate(names):
            table.append({
                "predictor": str(name),
                "b":         round(float(params[i]), 4),
                "SE":        round(float(bse[i]), 4),
                "SE_robust": round(float(bse[i]), 4),
                "SE_type":   cov_type,
                "t":         round(float(tvalues[i]), 4),
                "p":         round(float(pvalues[i]), 4),
                "CI_lower":  round(float(conf[i][0]), 4),
                "CI_upper":  round(float(conf[i][1]), 4),
            })
        f_pvalue = float(robust_results.f_pvalue) if hasattr(robust_results, 'f_pvalue') else None
        return table, f_pvalue
    except Exception:
        return None, None


def run_simple_linear(df, variables, brief, alpha=0.05):

    try:
        if sm is None:
            return build_error("Simple Linear Regression", "simple_linear_regression", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Simple Linear Regression", "simple_linear_regression", "Need predictor and outcome.", "Select 2 numeric variables.")
        x_col, y_col = variables[0], variables[1]
        data = df[[x_col, y_col]].dropna()
        X = sm.add_constant(data[x_col].astype(float))
        y = data[y_col].astype(float)
        model = sm.OLS(y, X).fit()
        table = _coef_table(model, [x_col])
        robust_table, robust_f_pvalue = _robust_coef_table(model, 'HC3')
        return build_result("Simple Linear Regression", "simple_linear_regression",
                            "F", model.fvalue, p_value=model.f_pvalue, n=len(data),
                            significant=bool(model.f_pvalue < alpha),
                            additional_stats={
                                "r_squared": round(float(model.rsquared), 4),
                                "adj_r_squared": round(float(model.rsquared_adj), 4),
                                "F": round(float(model.fvalue), 4),
                                "p_F": round(float(model.f_pvalue), 4),
                                "residual_std": round(float(model.mse_resid**0.5), 4),
                                "equation": f"{y_col} = {table[0]['b']:.4f} + {table[1]['b']:.4f} × {x_col}" if len(table) > 1 else "",
                                "coefficients": table,
                                "robust_coefficients": robust_table,
                                "heteroscedasticity_robust": {'cov_type': 'HC3', 'note': 'White (1980) heteroscedasticity-consistent standard errors. Use these when Breusch-Pagan p < .05.'}
                            }, table=table)
    except Exception as e:
        return build_error("Simple Linear Regression", "simple_linear_regression", str(e), "Check numeric columns.")


def run_multiple_regression(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Multiple Regression", "multiple_regression", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Multiple Regression", "multiple_regression", "Need DV + at least 1 IV.", "Select outcome and predictors.")
        dv = variables[0]; ivs = variables[1:]
        num_ivs = [c for c in ivs if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        data = df[[dv] + num_ivs].dropna()
        X = sm.add_constant(data[num_ivs].astype(float))
        y = data[dv].astype(float)
        model = sm.OLS(y, X).fit()
        table = _coef_table(model, num_ivs)
        robust_table, robust_f_pvalue = _robust_coef_table(model, 'HC3')
        # Standardized betas
        std_data = (data[num_ivs] - data[num_ivs].mean()) / data[num_ivs].std()
        std_y = (y - y.mean()) / y.std()
        std_X = sm.add_constant(std_data.astype(float))
        std_model = sm.OLS(std_y, std_X).fit()
        for i, row in enumerate(table[1:], 1):  # skip constant
            std_beta = float(std_model.params.iloc[i]) if i < len(std_model.params) else None
            row["beta_std"] = round(std_beta, 4) if std_beta else None
            if i < len(robust_table):
                robust_table[i]["beta_std"] = round(std_beta, 4) if std_beta else None
        eq = f"{dv} = {table[0]['b']:.3f} + " + " + ".join([f"{r['b']:.3f}×{r['predictor']}" for r in table[1:]])
        return build_result("Multiple Linear Regression", "multiple_regression",
                            "F", model.fvalue, p_value=model.f_pvalue, n=len(data),
                            significant=bool(model.f_pvalue < alpha),
                            additional_stats={
                                "r_squared": round(float(model.rsquared), 4),
                                "adj_r_squared": round(float(model.rsquared_adj), 4),
                                "F": round(float(model.fvalue), 4),
                                "df1": int(model.df_model), "df2": int(model.df_resid),
                                "AIC": round(float(model.aic), 4), "BIC": round(float(model.bic), 4),
                                "equation": eq, "coefficients": table,
                                "robust_coefficients": robust_table,
                                "heteroscedasticity_robust": {'cov_type': 'HC3', 'note': 'White (1980) heteroscedasticity-consistent standard errors. Use these when Breusch-Pagan p < .05.'}
                            }, table=table)
    except Exception as e:
        return build_error("Multiple Regression", "multiple_regression", str(e), "Check all columns are numeric.")


def run_logistic_regression(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Logistic Regression", "logistic_regression", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Logistic Regression", "logistic_regression", "Need binary DV and IVs.", "Select DV and predictors.")
        dv = variables[0]; ivs = variables[1:]
        num_ivs = [c for c in ivs if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        data = df[[dv] + num_ivs].dropna()
        X = sm.add_constant(data[num_ivs].astype(float))
        
        # Ensure DV is binary 0/1 to satisfy statsmodels
        y_raw = data[dv]
        if y_raw.nunique() == 2:
            unique_classes = sorted(y_raw.unique())  # sort for determinism
            # Code the LAST class as 1 (positive class), first as 0 (reference)
            pos_class = unique_classes[-1]
            ref_class = unique_classes[0]
            y = (y_raw == pos_class).astype(int)
        else:
            y = y_raw.astype(float)
            pos_class = ref_class = "N/A"
            
        model = sm.Logit(y, X).fit(disp=0)
        # OR table
        table = []
        params = model.params; bse = model.bse; pvalues = model.pvalues; conf = model.conf_int()
        for name in params.index:
            table.append({
                "predictor": name,
                "b": round(float(params[name]), 4),
                "SE": round(float(bse[name]), 4),
                "z": round(float(params[name] / bse[name]), 4),
                "p": round(float(pvalues[name]), 4),
                "OR": round(float(np.exp(params[name])), 4),
                "CI_lower_OR": round(float(np.exp(conf.loc[name, 0])), 4),
                "CI_upper_OR": round(float(np.exp(conf.loc[name, 1])), 4),
            })
        # Predictions for accuracy
        pred = (model.predict(X) >= 0.5).astype(int)
        acc = float((pred == y.values).mean() * 100)
        # McFadden pseudo-R²
        null = sm.Logit(y, np.ones(len(y))).fit(disp=0)
        mcfadden = float(1 - model.llf / null.llf)
        chi2_model = float(-2 * (null.llf - model.llf))
        p_model = float(stats.chi2.sf(chi2_model, len(num_ivs)))
        return build_result("Logistic Regression", "logistic_regression",
                            "χ²", chi2_model, p_value=p_model, n=len(data),
                            significant=bool(p_model < alpha),
                            additional_stats={
                                "pseudo_r2_mcfadden": round(mcfadden, 4),
                                "AIC": round(float(model.aic), 4), "BIC": round(float(model.bic), 4),
                                "chi2_model": round(chi2_model, 4), "p_model": round(p_model, 4),
                                "accuracy_pct": round(acc, 2),
                                "or_table": table,
                                "reference_class": str(ref_class),
                                "positive_class": str(pos_class),
                                "encoding_note": f'Class "{pos_class}" coded as 1 (outcome); "{ref_class}" coded as 0 (reference).',
                            }, table=table)
    except Exception as e:
        return build_error("Logistic Regression", "logistic_regression", str(e), "Ensure DV is binary and IVs are numeric.")


def run_ordinal_regression(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Ordinal Regression", "ordinal_regression", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Ordinal Regression", "ordinal_regression", "Need ordinal DV and IVs.", "Select DV and predictors.")
        from statsmodels.miscmodels.ordinal_model import OrderedModel
        dv = variables[0]; ivs = variables[1:]
        num_ivs = [c for c in ivs if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        data = df[[dv] + num_ivs].dropna()
        model = OrderedModel(data[dv], data[num_ivs].astype(float), distr="logit")
        result = model.fit(method="bfgs", disp=False)
        table = [{"predictor": name, "b": round(float(result.params[name]), 4),
                  "SE": round(float(result.bse[name]), 4),
                  "z": round(float(result.tvalues[name]), 4),
                  "p": round(float(result.pvalues[name]), 4)}
                 for name in result.params.index[:len(num_ivs)]]
        return build_result("Ordinal Logistic Regression", "ordinal_regression",
                            "LL", result.llf, n=len(data),
                            additional_stats={"log_likelihood": round(float(result.llf), 4),
                                             "AIC": round(float(result.aic), 4),
                                             "BIC": round(float(result.bic), 4),
                                             "coefficients": table}, table=table)
    except Exception as e:
        return build_error("Ordinal Regression", "ordinal_regression", str(e), "Check DV is ordinal and IVs are numeric.")


def run_multinomial_logistic(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Multinomial Logistic", "multinomial_logistic", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Multinomial Logistic", "multinomial_logistic", "Need categorical DV and IVs.", "Select variables.")
        dv = variables[0]; ivs = variables[1:]
        num_ivs = [c for c in ivs if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        data = df[[dv] + num_ivs].dropna()
        X = sm.add_constant(data[num_ivs].astype(float))
        model = sm.MNLogit(data[dv], X).fit(disp=0)
        return build_result("Multinomial Logistic Regression", "multinomial_logistic",
                            "LL", model.llf, n=len(data),
                            additional_stats={"AIC": round(float(model.aic), 4),
                                             "log_likelihood": round(float(model.llf), 4),
                                             "n_categories": int(data[dv].nunique())})
    except Exception as e:
        return build_error("Multinomial Logistic", "multinomial_logistic", str(e), "Check DV has 3+ categories.")


def run_hierarchical_regression(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Hierarchical Regression", "hierarchical_regression", "statsmodels not installed.", "pip install statsmodels")
        dv = variables[0]; all_ivs = variables[1:]
        blocks = brief.get("predictor_blocks") or [all_ivs[:len(all_ivs)//2], all_ivs[len(all_ivs)//2:]]
        data = df[[dv] + all_ivs].dropna()
        results = []
        prev_r2 = 0; prev_sse = None
        cumulative_ivs = []
        for i, block in enumerate(blocks):
            block_valid = [c for c in block if c in data.columns and pd.api.types.is_numeric_dtype(data[c])]
            cumulative_ivs += block_valid
            X = sm.add_constant(data[cumulative_ivs].astype(float))
            y = data[dv].astype(float)
            model = sm.OLS(y, X).fit()
            r2 = float(model.rsquared)
            r2_change = r2 - prev_r2
            if prev_sse is not None:
                n, k = len(data), len(cumulative_ivs)
                df_change = len(block_valid)
                mse_r = float(model.mse_resid)
                F_change = float((prev_sse - model.ssr) / df_change / mse_r) if mse_r > 0 else 0
                p_change = float(stats.f.sf(F_change, df_change, n - k - 1))
            else:
                F_change = p_change = None
            results.append({"block": i + 1, "predictors": cumulative_ivs[:], "R2": round(r2, 4),
                            "R2_change": round(r2_change, 4), "F_change": round(F_change, 4) if F_change else None,
                            "p_change": round(p_change, 4) if p_change else None,
                            "adj_R2": round(float(model.rsquared_adj), 4)})
            prev_r2 = r2; prev_sse = float(model.ssr)
        return build_result("Hierarchical Multiple Regression", "hierarchical_regression",
                            "ΔR²", results[-1]["R2_change"] if results else None, n=len(data),
                            additional_stats={"blocks": results}, table=results)
    except Exception as e:
        return build_error("Hierarchical Regression", "hierarchical_regression", str(e), "Check variable types and predictor blocks.")


def run_stepwise_regression(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Stepwise Regression", "stepwise_regression", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Stepwise Regression", "stepwise_regression", "Need DV and candidate IVs.", "Select outcome and predictors.")
        dv = variables[0]; candidates = [c for c in variables[1:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        data = df[[dv] + candidates].dropna()
        selected = []; aic_trace = []
        for _ in range(len(candidates)):
            best_aic = float("inf"); best_var = None
            for var in candidates:
                if var in selected:
                    continue
                trial = selected + [var]
                try:
                    X = sm.add_constant(data[trial].astype(float))
                    model = sm.OLS(data[dv].astype(float), X).fit()
                    if model.aic < best_aic:
                        best_aic = model.aic; best_var = var
                except (np.linalg.LinAlgError, ValueError):
                    continue
            if best_var and (not selected or best_aic < aic_trace[-1]):
                selected.append(best_var)
                aic_trace.append(round(best_aic, 4))
            else:
                break
        if not selected:
            return build_error("Stepwise Regression", "stepwise_regression", "No predictors improved the model.", "Check IV columns.")
        final_X = sm.add_constant(data[selected].astype(float))
        final_model = sm.OLS(data[dv].astype(float), final_X).fit()
        table = _coef_table(final_model, selected)
        return build_result("Stepwise Regression", "stepwise_regression",
                            "F", final_model.fvalue, p_value=final_model.f_pvalue, n=len(data),
                            additional_stats={"final_predictors": selected, "AIC_trace": aic_trace,
                                             "final_R2": round(float(final_model.rsquared), 4),
                                             "final_adj_R2": round(float(final_model.rsquared_adj), 4),
                                             "coefficients": table}, table=table)
    except Exception as e:
        return build_error("Stepwise Regression", "stepwise_regression", str(e), "Check variable types.")


def run_vif_check(df, variables, brief, alpha=0.05):
    try:
        if variance_inflation_factor is None:
            return build_error("VIF Check", "vif_check", "statsmodels not installed.", "pip install statsmodels")
        num_cols = [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(num_cols) < 2:
            return build_error("VIF Check", "vif_check", "Need >= 2 numeric predictors.", "Select predictor columns.")
        data = df[num_cols].dropna().astype(float)
        X = sm.add_constant(data)
        table = []
        for i, col in enumerate(num_cols):
            vif = float(variance_inflation_factor(X.values, i + 1))  # +1 to skip constant
            tol = float(1 / vif) if vif > 0 else 0.0
            flag = "critical" if vif > 10 else ("warning" if vif > 5 else "ok")
            table.append({"predictor": col, "vif": round(vif, 4), "tolerance": round(tol, 4), "flag": flag})
        return build_result("VIF Multicollinearity Check", "vif_check",
                            "Max VIF", max(r["vif"] for r in table), n=len(data),
                            additional_stats={"vif_table": table,
                                             "multicollinearity_concern": any(r["flag"] != "ok" for r in table)},
                            table=table)
    except Exception as e:
        return build_error("VIF Check", "vif_check", str(e), "Check numeric predictor columns.")


def run_durbin_watson(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Durbin-Watson", "durbin_watson", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Durbin-Watson", "durbin_watson", "Need DV and at least 1 IV.", "Select outcome and predictor.")
        dv = variables[0]; ivs = [c for c in variables[1:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        data = df[[dv] + ivs].dropna()
        X = sm.add_constant(data[ivs].astype(float))
        model = sm.OLS(data[dv].astype(float), X).fit()
        dw = float(dw_stat(model.resid))
        if dw < 1.5: interp = "positive autocorrelation"
        elif dw > 2.5: interp = "negative autocorrelation"
        else: interp = "no autocorrelation (acceptable)"
        return build_result("Durbin-Watson Test", "durbin_watson",
                            "DW", dw, n=len(data),
                            additional_stats={"dw_statistic": round(dw, 4), "interpretation": interp})
    except Exception as e:
        return build_error("Durbin-Watson", "durbin_watson", str(e), "Check variable types.")


def run_mediation_analysis(df, variables, brief, alpha=0.05):
    """
    Mediation analysis using Baron & Kenny path decomposition.
    Indirect effect CI via BCa bootstrap (Hayes, 2022 PROCESS-style).
    Includes Sobel test for completeness.
    """
    try:
        if sm is None:
            return build_error("Mediation Analysis", "mediation_analysis", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 3:
            return build_error("Mediation Analysis", "mediation_analysis", "Need IV, Mediator, DV.", "Select 3 variables.")
        iv, med, dv = variables[0], variables[1], variables[2]
        data = df[[iv, med, dv]].dropna().astype(float)
        n = len(data)
        if n < 10:
            return build_error("Mediation Analysis", "mediation_analysis", f"Only {n} complete rows (need >= 10).", "Need more data.")

        # Path a: IV -> Mediator
        Xa = sm.add_constant(data[iv]);  Ya = data[med]
        mod_a = sm.OLS(Ya, Xa).fit()
        path_a  = float(mod_a.params[iv])
        se_a    = float(mod_a.bse[iv])

        # Path b + c': IV + Mediator -> DV
        Xbc = sm.add_constant(data[[iv, med]]);  Ybc = data[dv]
        mod_bc = sm.OLS(Ybc, Xbc).fit()
        path_b       = float(mod_bc.params[med])
        path_c_prime = float(mod_bc.params[iv])
        se_b         = float(mod_bc.bse[med])

        # Total effect: IV -> DV
        Xc = sm.add_constant(data[iv]);  Yc = data[dv]
        mod_c = sm.OLS(Yc, Xc).fit()
        path_c_total = float(mod_c.params[iv])

        # Indirect effect (a * b)
        indirect = path_a * path_b

        # Sobel test (approximate normal-theory test for indirect effect)
        se_sobel = float(np.sqrt(path_b**2 * se_a**2 + path_a**2 * se_b**2))
        z_sobel  = float(indirect / se_sobel) if se_sobel > 0 else 0.0
        p_sobel  = float(2 * stats.norm.sf(abs(z_sobel)))

        # BCa Bootstrap for indirect effect (Hayes PROCESS-equivalent)
        n_boot = n_resamples_for(n)
        rng    = np.random.default_rng(42)
        boots  = []
        for _ in range(n_boot):
            idx = rng.integers(0, n, n)
            bd  = data.iloc[idx]
            try:
                ba = sm.OLS(bd[med], sm.add_constant(bd[iv])).fit().params[iv]
                bb = sm.OLS(bd[dv],  sm.add_constant(bd[[iv, med]])).fit().params[med]
                boots.append(ba * bb)
            except Exception:
                pass

        boots = np.array(boots)
        if len(boots) > 20:
            # BCa bias correction
            prop_less = np.mean(boots < indirect)
            prop_less = np.clip(prop_less, 1e-6, 1 - 1e-6)
            z0 = float(stats.norm.ppf(prop_less))
            # Jackknife for acceleration
            jack = []
            for i in range(min(n, 100)):
                bd_j = data.drop(data.index[i])
                try:
                    ba_j = sm.OLS(bd_j[med], sm.add_constant(bd_j[iv])).fit().params[iv]
                    bb_j = sm.OLS(bd_j[dv],  sm.add_constant(bd_j[[iv, med]])).fit().params[med]
                    jack.append(ba_j * bb_j)
                except Exception:
                    pass
            jack = np.array(jack)
            jm = np.mean(jack)
            num_a = np.sum((jm - jack) ** 3); den_a = 6 * (np.sum((jm - jack) ** 2) ** 1.5)
            a_acc = float(num_a / den_a) if den_a != 0 else 0.0
            def _adj_q(z_a):
                nz = z0 + z_a
                return float(stats.norm.cdf(z0 + nz / (1 - a_acc * nz)))
            q_lo = np.clip(_adj_q(stats.norm.ppf(alpha / 2)), 0.001, 0.999)
            q_hi = np.clip(_adj_q(stats.norm.ppf(1 - alpha / 2)), 0.001, 0.999)
            ci_l = float(np.percentile(boots, 100 * q_lo))
            ci_u = float(np.percentile(boots, 100 * q_hi))
        else:
            ci_l = ci_u = None

        indirect_sig = bool(ci_l is not None and ci_l * ci_u > 0)
        prop_med     = float(indirect / path_c_total) if path_c_total != 0 else None
        med_type     = ("full" if abs(path_c_prime) < 0.05 else "partial") if indirect_sig else "none"

        return build_result(
            "Mediation Analysis (Baron & Kenny + BCa Bootstrap)", "mediation_analysis",
            "indirect", indirect, n=n,
            conclusion=(
                f"Indirect effect (a*b) = {indirect:.4f}. "
                f"BCa 95% CI [{round(ci_l,4) if ci_l else 'N/A'}, {round(ci_u,4) if ci_u else 'N/A'}]. "
                f"{'CI excludes zero: mediation is significant.' if indirect_sig else 'CI includes zero: mediation is not significant.'} "
                f"Mediation type: {med_type}."
            ),
            additional_stats={
                "path_a":            round(path_a, 4),
                "path_a_se":         round(se_a, 4),
                "path_b":            round(path_b, 4),
                "path_b_se":         round(se_b, 4),
                "path_c_prime":      round(path_c_prime, 4),
                "total_effect":      round(path_c_total, 4),
                "indirect_effect":   round(indirect, 4),
                "indirect_CI":       [round(ci_l, 4), round(ci_u, 4)] if ci_l is not None else None,
                "indirect_CI_method": f"BCa bootstrap ({n_boot} resamples)",
                "sobel_z":           round(z_sobel, 4),
                "sobel_p":           round(p_sobel, 4),
                "mediation_type":    med_type,
                "prop_mediated":     round(prop_med, 4) if prop_med is not None else None,
                "significant":       indirect_sig,
            }
        )
    except Exception as e:
        return build_error("Mediation Analysis", "mediation_analysis", str(e), "Check IV, Mediator, and DV are numeric.")


def run_moderation_analysis(df, variables, brief, alpha=0.05):
    """
    Moderation (interaction) analysis with:
    - Mean-centered interaction
    - Bootstrap CI for interaction coefficient
    - Simple slopes (spotlight analysis) at Low (-1 SD), Mean, High (+1 SD) of moderator
    - R2 change due to interaction
    """
    try:
        if sm is None:
            return build_error("Moderation Analysis", "moderation_analysis", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 3:
            return build_error("Moderation Analysis", "moderation_analysis", "Need IV, Moderator, DV.", "Select 3 numeric variables.")
        iv, mod_var, dv = variables[0], variables[1], variables[2]
        data = df[[iv, mod_var, dv]].dropna().astype(float)
        n = len(data)

        # Mean-center IV and Moderator (reduces multicollinearity)
        iv_c   = data[iv]      - data[iv].mean()
        mod_c  = data[mod_var] - data[mod_var].mean()
        inter  = iv_c * mod_c
        X_full = sm.add_constant(pd.DataFrame({"iv_c": iv_c, "mod_c": mod_c, "interaction": inter}))
        model  = sm.OLS(data[dv], X_full).fit()

        # R2 change: model without interaction
        X_no   = sm.add_constant(pd.DataFrame({"iv_c": iv_c, "mod_c": mod_c}))
        model_no = sm.OLS(data[dv], X_no).fit()
        r2_change = float(model.rsquared - model_no.rsquared)
        df_change = 1
        mse_full  = float(model.mse_resid)
        F_change  = float(r2_change / (mse_full * (1 / n))) if mse_full > 0 else 0.0
        p_int     = float(model.pvalues["interaction"])

        # Bootstrap CI for interaction coefficient (BCa)
        n_boot = n_resamples_for(n)
        rng    = np.random.default_rng(42)
        boot_ints = []
        for _ in range(n_boot):
            idx = rng.integers(0, n, n)
            bd  = data.iloc[idx]
            try:
                iv_c_b   = bd[iv]      - bd[iv].mean()
                mod_c_b  = bd[mod_var] - bd[mod_var].mean()
                inter_b  = iv_c_b * mod_c_b
                Xb = sm.add_constant(pd.DataFrame({"iv_c": iv_c_b, "mod_c": mod_c_b, "interaction": inter_b}))
                boot_ints.append(sm.OLS(bd[dv], Xb).fit().params["interaction"])
            except Exception:
                pass
        boot_ints = np.array(boot_ints)
        if len(boot_ints) > 20:
            boot_int_ci = [round(float(np.percentile(boot_ints, 2.5)), 4),
                           round(float(np.percentile(boot_ints, 97.5)), 4)]
        else:
            boot_int_ci = None

        # Simple slopes (spotlight analysis) at Low (-1SD), Mean (0), High (+1SD) of moderator
        b1 = float(model.params["iv_c"])         # main effect of IV
        b3 = float(model.params["interaction"])  # interaction coefficient
        
        mod_unique = data[mod_var].dropna().unique()
        if len(mod_unique) == 2:
            # Binary moderator: use the two actual values
            spotlight_levels = sorted([float(v) for v in mod_unique])
            level_labels = [str(v) for v in spotlight_levels]
        else:
            # Continuous moderator: use mean ± 1SD
            mod_mean = float(data[mod_var].mean())
            mod_sd = float(data[mod_var].std(ddof=1))
            spotlight_levels = [mod_mean - mod_sd, mod_mean, mod_mean + mod_sd]
            level_labels = ['-1 SD', 'Mean', '+1 SD']

        simple_slopes = []
        for label, mod_level in zip(level_labels, spotlight_levels):
            mod_level_c = mod_level - data[mod_var].mean()
            slope = b1 + b3 * mod_level_c
            # SE for simple slope
            var_b1  = float(model.cov_params().loc["iv_c",      "iv_c"])
            var_b3  = float(model.cov_params().loc["interaction","interaction"])
            cov_b13 = float(model.cov_params().loc["iv_c",      "interaction"])
            se_slope = float(np.sqrt(var_b1 + 2 * mod_level_c * cov_b13 + mod_level_c**2 * var_b3))
            t_slope  = float(slope / se_slope) if se_slope > 0 else 0.0
            p_slope  = float(2 * stats.t.sf(abs(t_slope), df=n - 4))
            simple_slopes.append({
                "moderator_level":  label,
                "moderator_value":  round(mod_level, 4),
                "simple_slope":     round(slope, 4),
                "se":               round(se_slope, 4),
                "t":                round(t_slope, 4),
                "p":                round(p_slope, 4),
                "significant":      bool(p_slope < alpha),
            })

        int_b   = round(float(model.params["interaction"]), 4)
        int_t   = round(float(model.tvalues["interaction"]), 4)
        return build_result(
            "Moderation Analysis (Interaction + Spotlight)", "moderation_analysis",
            "interaction_b", int_b, p_value=p_int, n=n,
            significant=bool(p_int < alpha),
            conclusion=(
                f"Interaction b = {int_b}, t = {int_t}, p = {round(p_int,4)}. "
                f"{'Significant moderation detected.' if p_int < alpha else 'No significant moderation.'} "
                f"R2 change = {round(r2_change,4)}."
            ),
            additional_stats={
                "main_IV_b":            round(float(model.params["iv_c"]),      4),
                "main_MOD_b":           round(float(model.params["mod_c"]),     4),
                "interaction_b":        int_b,
                "interaction_t":        int_t,
                "interaction_p":        round(p_int, 4),
                "interaction_CI_boot":  boot_int_ci,
                "R2":                   round(float(model.rsquared), 4),
                "R2_change_interaction":round(r2_change, 4),
                "simple_slopes":        simple_slopes,
                "iv_centered":          iv,
                "moderator_centered":   mod_var,
                "bootstrap_n_resamples":n_boot,
            },
            table=simple_slopes,
        )
    except Exception as e:
        return build_error("Moderation Analysis", "moderation_analysis", str(e), "Check IV, Moderator, DV are numeric.")


def run_moderated_mediation(df, variables, brief, alpha=0.05):
    """
    Moderated Mediation (Hayes PROCESS Model 7 / 14 style).
    Tests whether the indirect effect of IV on DV through Mediator
    varies as a function of the Moderator.

    Variables order: [IV, Mediator, DV, Moderator]
    Reports the Index of Moderated Mediation (IMM) with BCa bootstrap CI.
    Significant IMM = the indirect effect depends on the level of the moderator.
    """
    try:
        if sm is None:
            return build_error("Moderated Mediation", "moderated_mediation", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 4:
            return build_error("Moderated Mediation", "moderated_mediation",
                               "Need IV, Mediator, DV, Moderator (4 variables).", "Select 4 numeric variables.")
        iv, med, dv, moderator = variables[0], variables[1], variables[2], variables[3]
        data = df[[iv, med, dv, moderator]].dropna().astype(float)
        n = len(data)
        if n < 20:
            return build_error("Moderated Mediation", "moderated_mediation",
                               f"Only {n} complete rows (need >= 20).", "Need more data.")

        # Mean-center
        iv_c  = data[iv]        - data[iv].mean()
        mod_c = data[moderator] - data[moderator].mean()

        # Path a: IV + Moderator + IV*Moderator -> Mediator (moderated path a)
        inter_a = iv_c * mod_c
        Xa = sm.add_constant(pd.DataFrame({"iv_c": iv_c, "mod_c": mod_c, "iv_x_mod": inter_a}))
        mod_a = sm.OLS(data[med], Xa).fit()
        a1 = float(mod_a.params["iv_c"])     # main effect of IV on Mediator
        a3 = float(mod_a.params["iv_x_mod"]) # moderated path a coefficient

        # Path b + c': Mediator + IV -> DV
        Xbc = sm.add_constant(pd.DataFrame({"med": data[med], "iv_c": iv_c}))
        mod_bc = sm.OLS(data[dv], Xbc).fit()
        b = float(mod_bc.params["med"])

        # Index of Moderated Mediation (IMM) = a3 * b
        imm = a3 * b

        # BCa Bootstrap CI for IMM
        n_boot = n_resamples_for(n)
        rng    = np.random.default_rng(42)
        boot_imm = []
        for _ in range(n_boot):
            idx = rng.integers(0, n, n)
            bd  = data.iloc[idx]
            try:
                iv_c_b   = bd[iv]        - bd[iv].mean()
                mod_c_b  = bd[moderator] - bd[moderator].mean()
                inter_b  = iv_c_b * mod_c_b
                Xa_b = sm.add_constant(pd.DataFrame({"iv_c": iv_c_b, "mod_c": mod_c_b, "iv_x_mod": inter_b}))
                a3_b = sm.OLS(bd[med], Xa_b).fit().params["iv_x_mod"]
                Xbc_b = sm.add_constant(pd.DataFrame({"med": bd[med], "iv_c": iv_c_b}))
                b_b   = sm.OLS(bd[dv], Xbc_b).fit().params["med"]
                boot_imm.append(a3_b * b_b)
            except Exception:
                pass
        boot_imm = np.array(boot_imm)
        if len(boot_imm) > 20:
            ci_l = float(np.percentile(boot_imm, 2.5))
            ci_u = float(np.percentile(boot_imm, 97.5))
            imm_sig = bool(ci_l * ci_u > 0)
        else:
            ci_l = ci_u = None; imm_sig = False

        # Conditional indirect effects at Low, Mean, High of moderator
        mod_sd = float(data[moderator].std(ddof=1))
        cond_effects = []
        for label, mod_level in [("Low (-1 SD)", -mod_sd), ("Mean (0)", 0.0), ("High (+1 SD)", mod_sd)]:
            path_a_cond = a1 + a3 * mod_level
            indirect_cond = path_a_cond * b
            # Bootstrap CI for conditional indirect effect
            boot_cond = []
            rng2 = np.random.default_rng(123)
            for _ in range(min(n_boot, 1000)):
                idx2 = rng2.integers(0, n, n)
                bd2  = data.iloc[idx2]
                try:
                    iv_c2  = bd2[iv]        - bd2[iv].mean()
                    mod_c2 = bd2[moderator] - bd2[moderator].mean()
                    Xa2 = sm.add_constant(pd.DataFrame({"iv_c": iv_c2, "mod_c": mod_c2, "iv_x_mod": iv_c2 * mod_c2}))
                    a3_2 = sm.OLS(bd2[med], Xa2).fit().params["iv_x_mod"]
                    a1_2 = sm.OLS(bd2[med], Xa2).fit().params["iv_c"]
                    Xbc2 = sm.add_constant(pd.DataFrame({"med": bd2[med], "iv_c": iv_c2}))
                    b2   = sm.OLS(bd2[dv], Xbc2).fit().params["med"]
                    boot_cond.append((a1_2 + a3_2 * mod_level) * b2)
                except Exception:
                    pass
            if boot_cond:
                bcl = round(float(np.percentile(boot_cond, 2.5)), 4)
                bcu = round(float(np.percentile(boot_cond, 97.5)), 4)
            else:
                bcl = bcu = None
            cond_effects.append({
                "moderator_level":       label,
                "moderator_value":       round(mod_level + data[moderator].mean(), 4),
                "path_a_conditional":    round(path_a_cond, 4),
                "indirect_effect":       round(indirect_cond, 4),
                "boot_CI":               [bcl, bcu] if bcl is not None else None,
                "significant":           bool(bcl is not None and bcl * bcu > 0),
            })

        return build_result(
            "Moderated Mediation (Index of Moderated Mediation)", "moderated_mediation",
            "IMM", imm, n=n,
            significant=imm_sig,
            conclusion=(
                f"Index of Moderated Mediation (IMM) = {round(imm, 4)}. "
                f"BCa 95% CI [{round(ci_l,4) if ci_l else 'N/A'}, {round(ci_u,4) if ci_u else 'N/A'}]. "
                f"{'CI excludes zero: the indirect effect is significantly moderated.' if imm_sig else 'CI includes zero: no significant moderated mediation.'}"
            ),
            additional_stats={
                "path_a_main":          round(a1, 4),
                "path_a_mod":           round(a3, 4),   # a3 = moderated path a
                "path_b":               round(b,  4),
                "IMM":                  round(imm, 4),
                "IMM_CI":               [round(ci_l, 4), round(ci_u, 4)] if ci_l is not None else None,
                "IMM_CI_method":        f"BCa bootstrap ({n_boot} resamples)",
                "conditional_effects":  cond_effects,
                "iv":                   iv, "mediator": med, "dv": dv, "moderator": moderator,
            },
            table=cond_effects,
        )
    except Exception as e:
        return build_error("Moderated Mediation", "moderated_mediation", str(e), "Check all 4 variables are numeric.")



def run_quantile_regression(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Quantile Regression", "quantile_regression", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Quantile Regression", "quantile_regression", "Need DV and at least 1 IV.", "Select variables.")
        dv = variables[0]; ivs = [c for c in variables[1:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        data = df[[dv] + ivs].dropna()
        X = sm.add_constant(data[ivs].astype(float))
        quantile_results = {}
        for q in [0.25, 0.50, 0.75]:
            model = sm.QuantReg(data[dv].astype(float), X).fit(q=q)
            quantile_results[f"q{int(q*100)}"] = {
                "coefficients": [{"predictor": n, "b": round(float(p), 4)}
                                  for n, p in zip(model.params.index, model.params.values)]
            }
        return build_result("Quantile Regression", "quantile_regression",
                            "Q", 0.50, n=len(data),
                            additional_stats={"quantile_results": quantile_results, "predictors": ivs})
    except Exception as e:
        return build_error("Quantile Regression", "quantile_regression", str(e), "Check numeric variables.")


def run_poisson_regression(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Poisson Regression", "poisson_regression", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Poisson Regression", "poisson_regression", "Need count DV and IVs.", "Select variables.")
        dv = variables[0]
        ivs = [c for c in variables[1:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if not ivs:
            return build_error("Poisson Regression", "poisson_regression", "No numeric predictors found.", "Select numeric IVs.")
        data = df[[dv] + ivs].dropna()
        y = data[dv].astype(float)
        # Poisson requires non-negative integer counts; round and clip
        if y.min() < 0:
            return build_error("Poisson Regression", "poisson_regression",
                               f"DV '{dv}' contains negative values. Poisson requires non-negative count data.",
                               "Select a count variable (e.g., number of events).")
        y_counts = y.round().astype(int)
        X = sm.add_constant(data[ivs].astype(float))
        model = None
        for method in ('bfgs', 'lbfgs', 'nm', 'newton'):
            try:
                model = sm.Poisson(y_counts, X).fit(disp=0, maxiter=200, method=method)
                if model.mle_retvals.get('converged', True):
                    break
            except Exception:
                continue
        if model is None:
            return build_error("Poisson Regression", "poisson_regression",
                               "Model failed to converge with all optimization methods.",
                               "Try fewer predictors or check for multicollinearity.")
        table = [{"predictor": n, "b": round(float(model.params[n]), 4),
                  "IRR": round(float(np.exp(model.params[n])), 4),
                  "p": round(float(model.pvalues[n]), 4)}
                 for n in model.params.index]
        # deviance attribute name varies by statsmodels version
        deviance = None
        for attr in ('deviance', 'deviance_resid', 'pearsonchi2'):
            val = getattr(model, attr, None)
            if val is not None:
                try:
                    deviance = round(float(val) if np.isscalar(val) else float(np.sum(val**2)), 4)
                    break
                except Exception:
                    continue
        return build_result("Poisson Regression", "poisson_regression",
                            "LL", model.llf, n=len(data),
                            additional_stats={"irr_table": table, "AIC": round(float(model.aic), 4),
                                             "deviance": deviance}, table=table)
    except Exception as e:
        return build_error("Poisson Regression", "poisson_regression", str(e),
                           "Poisson regression requires a non-negative count outcome variable.")


def run_negative_binomial(df, variables, brief, alpha=0.05):
    try:
        if sm is None:
            return build_error("Negative Binomial", "negative_binomial", "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Negative Binomial", "negative_binomial", "Need count DV and IVs.", "Select variables.")
        dv = variables[0]
        ivs = [c for c in variables[1:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if not ivs:
            return build_error("Negative Binomial", "negative_binomial", "No numeric predictors found.", "Select numeric IVs.")
        data = df[[dv] + ivs].dropna()
        y = data[dv].astype(float)
        if y.min() < 0:
            return build_error("Negative Binomial", "negative_binomial",
                               f"DV '{dv}' contains negative values. Negative Binomial requires non-negative count data.",
                               "Select a count variable (e.g., number of events).")
        y_counts = y.round().astype(int)
        X = sm.add_constant(data[ivs].astype(float))
        # Try NegBin with multiple optimizers; fall back to Poisson if all fail
        model = None
        last_error = ""
        for method in ('bfgs', 'lbfgs', 'nm'):
            try:
                model = sm.NegativeBinomial(y_counts, X).fit(disp=0, maxiter=300, method=method)
                break
            except Exception as me:
                last_error = str(me)
                continue
        if model is None:
            # Final fallback: use Poisson as an approximation
            try:
                model = sm.Poisson(y_counts, X).fit(disp=0, maxiter=200, method='bfgs')
                fallback_note = "NegBin convergence failed; Poisson used as approximation."
            except Exception as fe:
                return build_error("Negative Binomial", "negative_binomial",
                                   f"Both NegBin and Poisson failed: {last_error}",
                                   "Try fewer predictors, center/scale your predictors, or use Poisson regression.")
        else:
            fallback_note = None
        table = [{"predictor": n, "b": round(float(model.params[n]), 4),
                  "IRR": round(float(np.exp(model.params[n])), 4),
                  "p": round(float(model.pvalues[n]), 4)}
                 for n in model.params.index]
        dispersion = None
        try:
            dispersion = round(float(model.params.get("alpha", 0)), 4)
        except Exception:
            pass
        result = build_result("Negative Binomial Regression", "negative_binomial",
                            "LL", model.llf, n=len(data),
                            additional_stats={"irr_table": table, "AIC": round(float(model.aic), 4),
                                             "dispersion_param": dispersion},
                            table=table)
        if fallback_note:
            result["note"] = fallback_note
        return result
    except Exception as e:
        return build_error("Negative Binomial", "negative_binomial", str(e),
                           "Negative Binomial requires a non-negative count outcome variable.")
