# backend/analysis/engine/tests/multilevel.py
"""Multilevel / Mixed-effects models — LMM, GLMM, ICC, Random Effects."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error

try:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    from statsmodels.regression.mixed_linear_model import MixedLM
    _sm = True
except ImportError:
    _sm = False

try:
    import pingouin as pg
    _pg = True
except ImportError:
    _pg = False


def _num_cols(df, variables):
    return [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]


def run_lmm(df, variables, brief, alpha=0.05):
    """Hierarchical / Linear Mixed Model — fixed + multiple random intercepts."""
    try:
        if not _sm:
            return build_error("LMM", "linear_mixed_model",
                               "statsmodels not installed.", "pip install statsmodels")
        
        # Determine nesting structure from brief or variables
        raw_nesting = brief.get('nesting_variable', '') if brief else ''
        nesting_vars = [v.strip() for v in raw_nesting.split(',')] if raw_nesting else []
        
        if nesting_vars:
            # If nesting is defined explicitly in UI
            outcome_col = variables[0]
            group_col = nesting_vars[0] # Highest level
            lower_levels = nesting_vars[1:]
            predictors = [c for c in variables if c != outcome_col and c not in nesting_vars]
        else:
            # Fallback to older LLM behavior: outcome, group, predictors...
            if len(variables) < 3:
                return build_error("LMM", "linear_mixed_model",
                                   "Need outcome_col, group_col, and at least 1 predictor.",
                                   "Select 3+ variables.")
            outcome_col, group_col = variables[0], variables[1]
            lower_levels = []
            predictors = [c for c in variables[2:]]
            nesting_vars = [group_col]

        # Filter predictors to numeric
        predictors = [c for c in predictors if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        
        if outcome_col not in df.columns or group_col not in df.columns:
            return build_error("LMM", "linear_mixed_model",
                               "Outcome or primary group column not found.", "Check variable names.")
        if not pd.api.types.is_numeric_dtype(df[outcome_col]):
            return build_error("LMM", "linear_mixed_model",
                               f"Outcome '{outcome_col}' must be numeric.", "Use numeric outcome.")
        if not predictors:
            return build_error("LMM", "linear_mixed_model",
                               "No numeric predictors found.", "Select numeric predictors.")

        cols_to_keep = [outcome_col, group_col] + lower_levels + predictors
        # Ensure all columns exist
        cols_to_keep = [c for c in cols_to_keep if c in df.columns]
        data = df[cols_to_keep].dropna().copy()
        
        if len(data) < 10:
            return build_error("LMM", "linear_mixed_model",
                               f"Too few observations (n={len(data)}). Need >= 10.", "Use more data.")
        
        X_fixed = sm.add_constant(data[predictors].astype(float))
        y = data[outcome_col].astype(float)
        groups = data[group_col].astype(str)
        
        # Build Variance Components formula for lower levels (HLM)
        vc_formula = {}
        if lower_levels:
            for i, level in enumerate(lower_levels):
                # To prevent crossing, we combine IDs (e.g. School_Classroom)
                combined_id = data[group_col].astype(str)
                for j in range(i + 1):
                    combined_id = combined_id + "_" + data[lower_levels[j]].astype(str)
                data[f"__hlm_level_{level}"] = combined_id
                vc_formula[level] = f"0 + C(__hlm_level_{level})"
        
        # Initialize model
        fixed_formula = f"{outcome_col} ~ {' + '.join(predictors)}" if predictors else f"{outcome_col} ~ 1"
        if vc_formula:
            model = MixedLM.from_formula(fixed_formula, data=data, groups=group_col, re_formula="1", vc_formula=vc_formula)
        else:
            model = MixedLM.from_formula(fixed_formula, data=data, groups=group_col)
            
        try:
            result = model.fit(reml=True)
        except Exception:
            result = model.fit(reml=False)
            
        # Fixed effects table
        fe_table = []
        for name in result.params.index:
            fe_table.append({
                "predictor": name,
                "estimate": round(float(result.params[name]), 4),
                "SE": round(float(result.bse[name]), 4),
                "z": round(float(result.tvalues[name]), 4) if hasattr(result, "tvalues") else None,
                "p": round(float(result.pvalues[name]), 4),
                "CI_lower": round(float(result.conf_int().loc[name, 0]), 4),
                "CI_upper": round(float(result.conf_int().loc[name, 1]), 4),
            })
            
        # Variance Components & ICC
        re_var_primary = float(result.cov_re.values[0, 0]) if hasattr(result, "cov_re") else 0.0
        resid_var = float(result.scale) if hasattr(result, "scale") else 0.0
        
        variance_components = []
        variance_components.append({
            "level": group_col,
            "variance": round(re_var_primary, 4)
        })
        
        total_random_var = re_var_primary
        if hasattr(result, 'vcomp') and result.vcomp is not None:
            vc_names = list(vc_formula.keys()) if isinstance(vc_formula, dict) else [f"Level_{i}" for i in range(len(result.vcomp))]
            if hasattr(result.model, "exog_vc") and hasattr(result.model.exog_vc, "names"):
                vc_names = result.model.exog_vc.names
                
            for i, v_val in enumerate(result.vcomp):
                v_name = vc_names[i] if i < len(vc_names) else f"Level_{i}"
                val = float(v_val)
                total_random_var += val
                variance_components.append({
                    "level": v_name,
                    "variance": round(val, 4)
                })
                
        total_var = total_random_var + resid_var
        for vc in variance_components:
            vc["icc"] = round(vc["variance"] / total_var, 4) if total_var > 0 else 0.0
            
        variance_components.append({
            "level": "Residual",
            "variance": round(resid_var, 4),
            "icc": round(resid_var / total_var, 4) if total_var > 0 else 0.0
        })

        return build_result("Hierarchical Linear Model (HLM)", "linear_mixed_model",
                            "Log-Lik", result.llf, n=len(data),
                            additional_stats={
                                "fixed_effects": fe_table,
                                "variance_components": variance_components,
                                "total_icc": round(total_random_var / total_var, 4) if total_var > 0 else 0.0,
                                "AIC": round(float(result.aic), 4),
                                "BIC": round(float(result.bic), 4),
                                "log_likelihood": round(float(result.llf), 4),
                                "n_groups": int(data[group_col].nunique()),
                                "nesting_structure": " > ".join(nesting_vars)
                            }, table=fe_table)
    except Exception as e:
        return build_error("HLM", "linear_mixed_model", str(e),
                           "Check numeric outcome, and nesting variables.")


def run_glmm(df, variables, brief, alpha=0.05):
    """Generalized Linear Mixed Model — logistic/Poisson with random effects."""
    try:
        if not _sm:
            return build_error("GLMM", "glmm",
                               "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 3:
            return build_error("GLMM", "glmm",
                               "Need outcome_col, group_col, predictor(s).",
                               "Select 3+ variables.")
        outcome_col, group_col = variables[0], variables[1]
        predictors = [c for c in variables[2:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if not predictors:
            return build_error("GLMM", "glmm", "No numeric predictors found.", "Select predictor columns.")
        family_name = str(brief.get("family", "binomial") or "binomial")
        data = df[[outcome_col, group_col] + predictors].dropna()
        # Rename columns to safe names to avoid formula parsing issues
        safe_data = data.copy()
        safe_data.columns = ["outcome"] + ["group"] + [f"x{i}" for i in range(len(predictors))]
        safe_predictors = [f"x{i}" for i in range(len(predictors))]
        pred_formula = " + ".join(safe_predictors)
        formula = f"outcome ~ group + {pred_formula}" if pred_formula else "outcome ~ group"
        # Map family
        if family_name == "binomial":
            family = sm.families.Binomial()
        elif family_name == "poisson":
            family = sm.families.Poisson()
        elif family_name == "gaussian":
            family = sm.families.Gaussian()
        else:
            family = sm.families.Binomial()
        try:
            model_std = smf.glm(formula=formula, data=safe_data, family=family)
            result = model_std.fit()
        except Exception as fe:
            return build_error("GLMM", "glmm", str(fe),
                               "Check outcome, group, and predictor columns.")
        coef_table = []
        for name in result.params.index:
            # Map back safe predictor names to real column names
            display_name = name
            if name.startswith("x") and name[1:].isdigit():
                idx = int(name[1:])
                display_name = predictors[idx] if idx < len(predictors) else name
            elif name == "Intercept":
                display_name = "Intercept"
            coef_table.append({
                "predictor": display_name,
                "estimate": round(float(result.params[name]), 4),
                "SE": round(float(result.bse[name]), 4),
                "p": round(float(result.pvalues[name]), 4),
                "OR": round(float(np.exp(result.params[name])), 4) if family_name == "binomial" else None,
            })
        return build_result("GLMM (Fixed Effects Approximation)", "glmm",
                            "AIC", result.aic, n=len(data),
                            conclusion=" Note: Groups modeled as fixed effects; use R glmer() for proper random effects.",
                            additional_stats={
                                "family": family_name,
                                "AIC": round(float(result.aic), 4),
                                "log_likelihood": round(float(result.llf), 4),
                                "coefficients": coef_table,
                                "n_groups": int(data[group_col].nunique()),
                                "note": "Random effects approximated; full GLMM requires glmmTMB or lme4 in R.",
                                "method_note": "True GLMM not available in statsmodels. Groups treated as fixed effects (GEE-like approximation). For proper GLMM, use R lme4::glmer.",
                            }, table=coef_table)
    except Exception as e:
        return build_error("GLMM", "glmm", str(e),
                           "Check outcome, group, and predictor columns. Set 'family' in brief (binomial/poisson/gaussian).")


def run_icc(df, variables, brief, alpha=0.05):
    """Intraclass Correlation Coefficient (ICC) for reliability / clustering."""
    try:
        if _pg:
            if len(variables) < 2:
                return build_error("ICC", "icc", "Need rater columns.", "Select rater/occasion columns.")
            cols = [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
            if len(cols) < 2:
                return build_error("ICC", "icc", "Need >= 2 numeric rater columns.", "Select rater columns.")
            data = df[cols].dropna()
            n_subjects, n_raters = len(data), len(cols)
            # Melt to long format
            data_long = data.copy()
            data_long["subject"] = range(n_subjects)
            melted = data_long.melt(id_vars="subject", var_name="rater", value_name="score")
            icc_result = pg.intraclass_corr(data=melted, targets="subject", raters="rater", ratings="score")
            icc_table = icc_result.to_dict(orient="records")
            # Preferred type: ICC(A,1) (modern pingouin) or ICC2 (older pingouin)
            preferred = ["ICC(A,1)", "ICC2", "ICC(A,k)", "ICC2k"]
            icc21 = None
            for t in preferred:
                matched = icc_result[icc_result["Type"] == t]
                if len(matched) > 0:
                    icc21 = matched.iloc[0]
                    break
            if icc21 is None:
                icc21 = icc_result.iloc[0]
            icc_val = float(icc21["ICC"])
            # Handle both 'CI95%' (old pingouin) and 'CI95' (new pingouin)
            ci_col = next((c for c in ["CI95%", "CI95"] if c in icc21.index), None)
            ci = icc21[ci_col] if ci_col else [None, None]
            icc_ci_l = float(ci[0]) if (ci is not None and ci[0] is not None) else None
            icc_ci_u = float(ci[1]) if (ci is not None and ci[1] is not None) else None
            p_col = next((c for c in ["pval", "p-unc", "p"] if c in icc21.index), None)
            p_val = float(icc21[p_col]) if p_col else None
            interp = "poor" if icc_val < 0.5 else ("moderate" if icc_val < 0.75 else ("good" if icc_val < 0.90 else "excellent"))
        else:
            # Manual one-way ANOVA ICC
            cols = [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
            if len(cols) < 2:
                return build_error("ICC", "icc", "Need >= 2 numeric rater columns.", "Select rater columns.")
            data = df[cols].dropna()
            n_subjects, k = len(data), len(cols)
            grand_mean = float(data.values.mean())
            SS_b = k * float(np.sum((data.mean(axis=1) - grand_mean)**2))
            SS_w = float(np.sum((data.values - data.mean(axis=1).values[:, None])**2))
            MS_b = SS_b / (n_subjects - 1) if n_subjects > 1 else 0
            MS_w = SS_w / (n_subjects * (k - 1)) if (n_subjects * (k - 1)) > 0 else 0
            icc_val = float((MS_b - MS_w) / (MS_b + (k - 1) * MS_w)) if (MS_b + (k - 1) * MS_w) > 0 else 0
            F = MS_b / MS_w if MS_w > 0 else 0
            p_val = float(stats.f.sf(F, n_subjects - 1, n_subjects * (k - 1)))
            icc_ci_l = icc_ci_u = None
            icc_table = [{"Type": "ICC(1,1)", "ICC": round(icc_val, 4), "F": round(F, 4), "p": round(p_val, 4)}]
            interp = "poor" if icc_val < 0.5 else ("moderate" if icc_val < 0.75 else ("good" if icc_val < 0.90 else "excellent"))
        return build_result("Intraclass Correlation Coefficient (ICC)", "icc",
                            "ICC", icc_val, p_value=p_val, n=len(data) if not isinstance(data, int) else 0,
                            significant=bool(p_val < alpha) if p_val else None,
                            ci_lower=icc_ci_l, ci_upper=icc_ci_u,
                            effect_size_name="ICC", effect_size_value=icc_val,
                            effect_size_interpretation=interp,
                            conclusion=f"ICC = {icc_val:.4f} ({interp} reliability).",
                            additional_stats={"icc": round(icc_val, 4), "interpretation": interp,
                                             "icc_types": icc_table},
                            table=icc_table)
    except Exception as e:
        return build_error("ICC", "icc", str(e), "Check rater/occasion columns are numeric.")


def run_random_effects_anova(df, variables, brief, alpha=0.05):
    """One-way Random Effects ANOVA (groups are a random sample of all groups)."""
    try:
        if len(variables) < 2:
            return build_error("Random Effects ANOVA", "random_effects_anova",
                               "Need group_col and outcome_col.", "Select 2 variables.")
        group_col, outcome_col = variables[0], variables[1]
        if group_col not in df.columns or outcome_col not in df.columns:
            return build_error("Random Effects ANOVA", "random_effects_anova",
                               "Columns not found.", "Check variable names.")
        data = df[[group_col, outcome_col]].dropna()
        groups = {str(name): grp[outcome_col].values for name, grp in data.groupby(group_col) if len(grp) >= 2}
        k = len(groups); n = sum(len(g) for g in groups.values())
        if k < 2:
            return build_error("Random Effects ANOVA", "random_effects_anova",
                               f"Need >= 2 groups, found {k}.", "Check group column.")
        grand_mean = np.mean(np.concatenate(list(groups.values())))
        SS_b = float(sum(len(g) * (np.mean(g) - grand_mean)**2 for g in groups.values()))
        SS_w = float(sum(np.sum((g - np.mean(g))**2) for g in groups.values()))
        df_b = k - 1; df_w = n - k
        MS_b = SS_b / df_b if df_b > 0 else 0
        MS_w = SS_w / df_w if df_w > 0 else 0
        F = float(MS_b / MS_w) if MS_w > 0 else 0
        p = float(stats.f.sf(F, df_b, df_w))
        # Average group size
        n_bar = float(n / k)
        # Variance components
        sigma2_e = float(MS_w)  # within-group (error) variance
        sigma2_u = float((MS_b - MS_w) / n_bar)  # between-group (random effect) variance
        sigma2_u = max(0.0, sigma2_u)
        icc = float(sigma2_u / (sigma2_u + sigma2_e)) if (sigma2_u + sigma2_e) > 0 else 0.0
        group_table = [{"group": name, "n": len(g), "mean": round(float(np.mean(g)), 4), "sd": round(float(np.std(g, ddof=1)), 4)}
                       for name, g in groups.items()]
        return build_result("One-Way Random Effects ANOVA", "random_effects_anova",
                            "F", F, p_value=p, n=n, df_val=df_b,
                            significant=bool(p < alpha),
                            conclusion=f"F({df_b},{df_w}) = {F:.3f}, p = {p:.4f}. {'Significant' if p<alpha else 'Non-significant'} group effect. ICC = {icc:.4f}.",
                            additional_stats={
                                "F": round(F, 4), "df_between": df_b, "df_within": df_w,
                                "MS_between": round(MS_b, 4), "MS_within": round(MS_w, 4),
                                "sigma2_between": round(sigma2_u, 4),
                                "sigma2_within": round(sigma2_e, 4),
                                "icc": round(icc, 4),
                                "group_table": group_table,
                            }, table=group_table)
    except Exception as e:
        return build_error("Random Effects ANOVA", "random_effects_anova", str(e), "Check group and outcome columns.")


def run_cross_classified_mlm(df, variables, brief, alpha=0.05):
    """Cross-classified multilevel model via LMM with two grouping factors."""
    try:
        if not _sm:
            return build_error("Cross-Classified MLM", "cross_classified_mlm",
                               "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 3:
            return build_error("Cross-Classified MLM", "cross_classified_mlm",
                               "Need outcome_col, group1_col, group2_col, and optional predictors.",
                               "Select 3+ variables.")
        outcome_col, group1_col, group2_col = variables[0], variables[1], variables[2]
        if outcome_col not in df.columns or not pd.api.types.is_numeric_dtype(df[outcome_col]):
            return build_error("Cross-Classified MLM", "cross_classified_mlm",
                               f"Outcome '{outcome_col}' must be a numeric column.",
                               "Select a numeric outcome variable as the first variable.")
        predictors = [c for c in variables[3:] if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        data = df[[outcome_col, group1_col, group2_col] + predictors].dropna()
        y = data[outcome_col].astype(float)
        if predictors:
            X = sm.add_constant(data[predictors].astype(float))
        else:
            X = pd.DataFrame({"const": np.ones(len(data))}, index=data.index)

        # Fit ONE combined model with both grouping factors as fixed effects
        # and as the primary grouping variable
        X_fixed = pd.get_dummies(data[[group1_col, group2_col]].astype(str), drop_first=True).astype(float)
        X_combined = pd.concat([X, X_fixed], axis=1)
        data['combined_group'] = data[group1_col].astype(str) + "_" + data[group2_col].astype(str)
        
        results = {}
        try:
            m = MixedLM(y, X_combined, groups=data['combined_group'])
            r = m.fit(reml=True)
            re_var = float(r.cov_re.values[0, 0]) if hasattr(r, "cov_re") else None
            resid_var = float(r.scale) if hasattr(r, "scale") else None
            results["combined"] = {
                "random_variance": round(re_var, 4) if re_var else None,
                "residual_variance": round(resid_var, 4) if resid_var else None,
                "icc": round(float(re_var / (re_var + resid_var)), 4) if (re_var and resid_var and re_var + resid_var > 0) else None,
                "AIC": round(float(r.aic), 4),
            }
        except Exception as ex:
            results["combined"] = {"error": str(ex)}
        return build_result("Cross-Classified Multilevel Model", "cross_classified_mlm",
                            "N", len(data), n=len(data),
                            additional_stats={
                                "grouping_results": results,
                                "n_group1_clusters": int(data[group1_col].nunique()),
                                "n_group2_clusters": int(data[group2_col].nunique()),
                                "method_note": "Cross-classified random effects approximated: both grouping factors included as fixed effects. Full cross-classified random effects require R lme4::lmer with (1|g1) + (1|g2) syntax.",
                            })
    except Exception as e:
        return build_error("Cross-Classified MLM", "cross_classified_mlm", str(e),
                           "Check outcome, two group columns, and optional predictors.")


def run_growth_curve_model(df, variables, brief, alpha=0.05):
    """Growth Curve Model (Latent Growth Curve via LMM with time predictor)."""
    try:
        if not _sm:
            return build_error("Growth Curve", "growth_curve_model",
                               "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 3:
            return build_error("Growth Curve", "growth_curve_model",
                               "Need outcome_col, time_col, subject_col.",
                               "Select 3 columns: outcome, time, subject ID.")
        outcome_col = variables[0]
        # Variable order: outcome, subject_col, time_col (optional more predictors)
        subject_col = variables[1] if len(variables) > 1 else None
        time_col = variables[2] if len(variables) > 2 else None
        if not subject_col or not time_col:
            return build_error("Growth Curve", "growth_curve_model",
                               "Need outcome_col, subject_col, time_col.",
                               "Select 3 columns: outcome, subject ID, time.")
        if not pd.api.types.is_numeric_dtype(df[outcome_col]):
            return build_error("Growth Curve", "growth_curve_model",
                               f"Outcome '{outcome_col}' must be numeric.",
                               "Select a numeric outcome as the first variable.")
        if not pd.api.types.is_numeric_dtype(df[time_col]):
            return build_error("Growth Curve", "growth_curve_model",
                               f"Time column '{time_col}' must be numeric.",
                               "Select a numeric time variable as the third variable.")
        data = df[[outcome_col, subject_col, time_col]].dropna()
        if len(data) < 10:
            return build_error("Growth Curve", "growth_curve_model",
                               f"Too few observations (n={len(data)}). Need >= 10.", "Use more data.")
        y = data[outcome_col].astype(float)
        X = sm.add_constant(data[time_col].astype(float))
        groups = data[subject_col].astype(str)
        # LMM with random intercept and slope for time
        model = MixedLM(y, X, groups=groups, exog_re=data[time_col].astype(float).values.reshape(-1, 1))
        try:
            result = model.fit(reml=True)
        except Exception:
            model_ri = MixedLM(y, X, groups=groups)
            result = model_ri.fit(reml=True)
        intercept = round(float(result.params.get("const", result.params.iloc[0])), 4)
        slope = round(float(result.params.get(time_col, result.params.iloc[-1])), 4)
        fe_table = [{"predictor": name, "estimate": round(float(result.params[name]), 4),
                     "SE": round(float(result.bse[name]), 4),
                     "p": round(float(result.pvalues[name]), 4)}
                    for name in result.params.index]
        return build_result("Growth Curve Model", "growth_curve_model",
                            "slope", slope, n=len(data),
                            significant=bool(result.pvalues.get(time_col, 1) < alpha),
                            conclusion=f"Average trajectory: intercept = {intercept}, slope = {slope} per time unit.",
                            additional_stats={
                                "intercept": intercept,
                                "slope": slope,
                                "fixed_effects": fe_table,
                                "AIC": round(float(result.aic), 4),
                                "n_subjects": int(data[subject_col].nunique()),
                                "n_timepoints_mean": round(float(len(data) / data[subject_col].nunique()), 2),
                            }, table=fe_table)
    except Exception as e:
        return build_error("Growth Curve", "growth_curve_model", str(e),
                           "Check outcome, time, and subject columns.")


def run_multilevel_mediation(df, variables, brief, alpha=0.05):
    """Multilevel mediation: 1-1-1 mediation within clusters."""
    try:
        if not _sm:
            return build_error("Multilevel Mediation", "multilevel_mediation",
                               "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 4:
            return build_error("Multilevel Mediation", "multilevel_mediation",
                               "Need IV, Mediator, DV, group_col.",
                               "Select 4 variables.")
        iv_col, med_col, dv_col, group_col = variables[0], variables[1], variables[2], variables[3]
        data = df[[iv_col, med_col, dv_col, group_col]].dropna()
        n = len(data)
        # Path a: IV → Mediator (LMM)
        Xa = sm.add_constant(data[iv_col].astype(float))
        mod_a = MixedLM(data[med_col].astype(float), Xa, groups=data[group_col].astype(str)).fit(reml=False)
        path_a = float(mod_a.params.get(iv_col, mod_a.params.iloc[-1]))
        # Path b + c': IV + Med → DV (LMM)
        Xbc = sm.add_constant(data[[iv_col, med_col]].astype(float))
        mod_bc = MixedLM(data[dv_col].astype(float), Xbc, groups=data[group_col].astype(str)).fit(reml=False)
        path_b = float(mod_bc.params.get(med_col, mod_bc.params.iloc[-1]))
        path_c_prime = float(mod_bc.params.get(iv_col, mod_bc.params.iloc[1] if len(mod_bc.params) > 1 else 0.0))
        # Total: IV → DV (LMM)
        Xc = sm.add_constant(data[iv_col].astype(float))
        mod_c = MixedLM(data[dv_col].astype(float), Xc, groups=data[group_col].astype(str)).fit(reml=False)
        path_c_total = float(mod_c.params.get(iv_col, mod_c.params.iloc[-1]))
        indirect = path_a * path_b
        prop_mediated = float(indirect / path_c_total) if path_c_total != 0 else None
        return build_result("Multilevel Mediation (1-1-1)", "multilevel_mediation",
                            "indirect", indirect, n=n,
                            additional_stats={
                                "path_a": round(path_a, 4),
                                "path_b": round(path_b, 4),
                                "path_c_prime": round(path_c_prime, 4),
                                "total_effect": round(path_c_total, 4),
                                "indirect_effect": round(indirect, 4),
                                "prop_mediated": round(prop_mediated, 4) if prop_mediated else None,
                                "n_clusters": int(data[group_col].nunique()),
                            })
    except Exception as e:
        return build_error("Multilevel Mediation", "multilevel_mediation", str(e),
                           "Check IV, Mediator, DV, and group columns.")
