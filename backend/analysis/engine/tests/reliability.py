# backend/analysis/engine/tests/reliability.py
"""Reliability analysis — Cronbach's Alpha, McDonald's Omega, ICC, KR-20, etc."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error

try:
    import pingouin as pg
except ImportError:
    pg = None


def _interp_alpha(a: float) -> str:
    if a >= 0.90: return "Excellent"
    if a >= 0.80: return "Good"
    if a >= 0.70: return "Acceptable"
    if a >= 0.60: return "Poor"
    return "Unacceptable"


def _get_item_cols(df, variables):
    return [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]


def run_cronbach_alpha(df, variables, brief, alpha=0.05):
    try:
        cols = _get_item_cols(df, variables)
        if len(cols) < 2:
            return build_error("Cronbach's Alpha", "cronbach_alpha",
                               "Need at least 2 numeric item columns.", "Select the Likert scale item columns.")
        data = df[cols].dropna()
        n, k = len(data), len(cols)
        if n < 2:
            return build_error("Cronbach's Alpha", "cronbach_alpha", f"Only {n} complete rows.", "Need >= 2 complete rows.")

        # Try pingouin first
        if pg is not None:
            try:
                ca = pg.cronbach_alpha(data=data)
                alpha_val = float(ca[0])
                ci = ca[1] if len(ca) > 1 else (None, None)
            except Exception:
                alpha_val = None
        else:
            alpha_val = None

        # Fallback: manual formula
        if alpha_val is None:
            item_vars = data.var(axis=0, ddof=1)
            total_var = data.sum(axis=1).var(ddof=1)
            alpha_val = float((k / (k - 1)) * (1 - item_vars.sum() / total_var)) if total_var > 0 else 0.0

        # Item-total correlations and alpha-if-deleted
        item_stats = []
        for col in cols:
            rest = data[[c for c in cols if c != col]].sum(axis=1)
            r, _ = stats.pearsonr(data[col], rest) if len(data) > 2 else (np.nan, np.nan)
            # Alpha if deleted
            sub_cols = [c for c in cols if c != col]
            sub_data = data[sub_cols]
            sub_k = len(sub_cols)
            if sub_k >= 2:
                sub_iv = sub_data.var(axis=0, ddof=1)
                sub_tv = sub_data.sum(axis=1).var(ddof=1)
                a_del = float((sub_k / (sub_k - 1)) * (1 - sub_iv.sum() / sub_tv)) if sub_tv > 0 else np.nan
            else:
                a_del = np.nan
            item_stats.append({
                "item": col, "mean": round(float(data[col].mean()), 4),
                "std": round(float(data[col].std()), 4),
                "item_total_r": round(float(r), 4) if not np.isnan(r) else None,
                "alpha_if_deleted": round(a_del, 4) if not np.isnan(a_del) else None,
                "flag_low_r": bool(not np.isnan(r) and abs(r) < 0.30),
            })

        # Mean inter-item correlation
        corr_matrix = data.corr()
        n_pairs = k * (k - 1) / 2
        mean_iic = float(corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)).stack().mean()) if n_pairs > 0 else 0.0

        return build_result(
            "Cronbach's Alpha (Internal Consistency)", "cronbach_alpha",
            "α", alpha_val, n=n,
            effect_size_name="Cronbach's α", effect_size_value=alpha_val,
            effect_size_interpretation=_interp_alpha(alpha_val),
            additional_stats={
                "alpha": round(alpha_val, 4), "n_items": k, "n_respondents": n,
                "mean_inter_item_correlation": round(mean_iic, 4),
                "interpretation": _interp_alpha(alpha_val),
                "item_statistics": item_stats,
            }
        )
    except Exception as e:
        return build_error("Cronbach's Alpha", "cronbach_alpha", str(e), "Check item column types.")


def run_mcdonald_omega(df, variables, brief, alpha=0.05):
    try:
        cols = _get_item_cols(df, variables)
        if len(cols) < 3:
            return build_error("McDonald's Omega", "mcdonald_omega",
                               "Need at least 3 item columns for omega.", "Select >= 3 Likert items.")
        data = df[cols].dropna()
        if len(data) < 5:
            return build_error("McDonald's Omega", "mcdonald_omega", "Too few complete rows.", "Need >= 5.")
        try:
            from sklearn.decomposition import FactorAnalysis
            fa = FactorAnalysis(n_components=1, random_state=42)
            fa.fit(data)
            loadings = fa.components_[0]
            unique_var = fa.noise_variance_
            sum_loadings = np.sum(np.abs(loadings))
            omega = float(sum_loadings**2 / (sum_loadings**2 + np.sum(unique_var)))
        except Exception:
            # Fallback to Cronbach
            k = len(cols)
            item_vars = data.var(axis=0, ddof=1)
            total_var = data.sum(axis=1).var(ddof=1)
            omega = float((k / (k - 1)) * (1 - item_vars.sum() / total_var)) if total_var > 0 else 0.0
            return build_result("Reliability (Cronbach's Alpha — Omega fallback)", "mcdonald_omega", "ω", omega, n=len(data),
                                effect_size_name="alpha", effect_size_value=omega,
                                effect_size_interpretation=_interp_alpha(omega),
                                additional_stats={"omega": round(omega, 4), "n_items": len(cols),
                                                  "interpretation": _interp_alpha(omega),
                                                  "omega_note": 'Factor analysis failed; Cronbach\'s alpha reported as fallback. For true McDonald\'s Omega, ensure factor_analyzer is installed.'})
        return build_result("McDonald's Omega", "mcdonald_omega", "ω", omega, n=len(data),
                            effect_size_name="ω", effect_size_value=omega,
                            effect_size_interpretation=_interp_alpha(omega),
                            additional_stats={"omega": round(omega, 4), "n_items": len(cols),
                                              "interpretation": _interp_alpha(omega)})
    except Exception as e:
        return build_error("McDonald's Omega", "mcdonald_omega", str(e), "Check column types.")


def run_split_half(df, variables, brief, alpha=0.05):
    try:
        cols = _get_item_cols(df, variables)
        if len(cols) < 2:
            return build_error("Split-Half Reliability", "split_half_reliability",
                               "Need at least 2 item columns.", "Select Likert item columns.")
        data = df[cols].dropna()
        mid = len(cols) // 2
        half1 = data[cols[:mid]].sum(axis=1)
        half2 = data[cols[mid:]].sum(axis=1)
        r, p = stats.pearsonr(half1, half2)
        r_sb = float(2 * r / (1 + r))  # Spearman-Brown
        additional_stats = {"r_half": round(float(r), 4), "r_spearman_brown": round(r_sb, 4),
                                              "interpretation": _interp_alpha(abs(r_sb)),
                                              "half1_items": cols[:mid], "half2_items": cols[mid:]}
        if len(cols[:mid]) != len(cols[mid:]):
            additional_stats['split_note'] = f'Unequal split ({len(cols[:mid])} vs {len(cols[mid:])} items). Spearman-Brown correction assumes parallel equal-length forms; interpret with caution.'
        
        return build_result("Split-Half Reliability", "split_half_reliability", "r_SB", r_sb, n=len(data),
                            additional_stats=additional_stats)
    except Exception as e:
        return build_error("Split-Half Reliability", "split_half_reliability", str(e), "Check column types.")


def run_item_analysis(df, variables, brief, alpha=0.05):
    try:
        cols = _get_item_cols(df, variables)
        if len(cols) < 2:
            return build_error("Item Analysis", "item_analysis", "Need >= 2 item columns.", "Select item columns.")
        data = df[cols].dropna()
        total = data.sum(axis=1)
        table = []
        for col in cols:
            rest_total = total - data[col]
            r, _ = stats.pearsonr(data[col], rest_total) if len(data) > 2 else (np.nan, np.nan)
            sub_cols = [c for c in cols if c != col]
            sub_data = data[sub_cols]
            k2 = len(sub_cols)
            if k2 >= 2:
                iv2 = sub_data.var(axis=0, ddof=1)
                tv2 = sub_data.sum(axis=1).var(ddof=1)
                a_del = float((k2 / (k2 - 1)) * (1 - iv2.sum() / tv2)) if tv2 > 0 else np.nan
            else:
                a_del = np.nan
            table.append({
                "item": col, "mean": round(float(data[col].mean()), 4),
                "std": round(float(data[col].std()), 4),
                "item_total_r": round(float(r), 4) if not np.isnan(r) else None,
                "alpha_if_deleted": round(a_del, 4) if not np.isnan(a_del) else None,
                "flag": "⚠ Low r" if (not np.isnan(r) and abs(r) < 0.30) else "OK",
            })
        return build_result("Item Analysis", "item_analysis", "N items", len(cols), n=len(data),
                            additional_stats={"items": table}, table=table)
    except Exception as e:
        return build_error("Item Analysis", "item_analysis", str(e), "Check item columns.")


def run_icc(df, variables, brief, alpha=0.05):
    try:
        if pg is None:
            return build_error("ICC", "icc", "pingouin library not installed.", "Run: pip install pingouin")
        # Accept either wide-format rater columns or variables list
        cols = _get_item_cols(df, variables)
        if len(cols) < 2:
            return build_error("ICC", "icc", "Need >= 2 numeric columns (raters/occasions).", "Select rater columns.")
        data = df[cols].dropna().reset_index(drop=True)
        if len(data) < 5:
            return build_error("ICC", "icc",
                               f"Too few complete rows (n={len(data)}). Need >= 5.", "Use more data.")
        # Melt into long format for pingouin
        data_reset = data.copy()
        data_reset["targets"] = range(len(data_reset))
        melted = data_reset.melt(id_vars="targets", var_name="raters", value_name="ratings")
        icc_res = pg.intraclass_corr(data=melted, targets="targets", raters="raters", ratings="ratings")
        # Prefer two-way absolute agreement ICC:
        # - Modern pingouin: 'ICC(A,1)' or 'ICC(A,k)'
        # - Older pingouin:  'ICC2' or 'ICC2k'
        preferred_types = ["ICC(A,1)", "ICC2", "ICC(A,k)", "ICC2k"]
        icc_row = None
        for t in preferred_types:
            matched = icc_res[icc_res["Type"] == t]
            if len(matched) > 0:
                icc_row = matched.iloc[0]
                break
        if icc_row is None:
            icc_row = icc_res.iloc[0]  # fallback: first row
        icc_val = float(icc_row["ICC"])
        # Handle both 'CI95%' (old) and 'CI95' (new) column names
        ci_col = next((c for c in ["CI95%", "CI95"] if c in icc_row.index), None)
        ci = icc_row[ci_col] if ci_col else [None, None]
        icc_ci_l = float(ci[0]) if (ci is not None and ci[0] is not None) else None
        icc_ci_u = float(ci[1]) if (ci is not None and ci[1] is not None) else None
        p_col = next((c for c in ["pval", "p-unc", "p"] if c in icc_row.index), None)
        p_val = float(icc_row[p_col]) if p_col else None
        interp = ("poor" if icc_val < 0.5 else
                  ("moderate" if icc_val < 0.75 else
                   ("good" if icc_val < 0.90 else "excellent")))
        return build_result("Intraclass Correlation Coefficient", "icc_reliability",
                            "ICC", icc_val,
                            p_value=p_val, n=len(data),
                            significant=bool(p_val < alpha) if p_val is not None else None,
                            ci_lower=icc_ci_l, ci_upper=icc_ci_u,
                            effect_size_name="ICC", effect_size_value=icc_val,
                            effect_size_interpretation=interp,
                            conclusion=f"ICC = {icc_val:.4f} ({interp} reliability).",
                            additional_stats={
                                "icc_type": str(icc_row["Type"]),
                                "icc": round(icc_val, 4),
                                "interpretation": interp,
                                "F": round(float(icc_row["F"]), 4) if "F" in icc_row.index else None,
                                "df1": int(icc_row["df1"]) if "df1" in icc_row.index else None,
                                "df2": int(icc_row["df2"]) if "df2" in icc_row.index else None,
                            })
    except Exception as e:
        return build_error("ICC", "icc_reliability", str(e), "Ensure all selected columns are numeric rater/occasion scores.")


def run_kr20(df, variables, brief, alpha=0.05):
    try:
        cols = _get_item_cols(df, variables)
        if len(cols) < 2:
            return build_error("KR-20", "kr20", "Need >= 2 binary item columns.", "Select binary (0/1) items.")
        data = df[cols].dropna()
        # Validate binary
        non_binary = [c for c in cols if not set(data[c].dropna().unique()).issubset({0, 1, 0.0, 1.0})]
        if non_binary:
            return build_error("KR-20", "kr20",
                               f"Columns {non_binary} are not binary (0/1). KR-20 requires binary items.",
                               "Convert items to 0/1 coding.")
        k = len(cols)
        p_values = data.mean()
        q_values = 1 - p_values
        pq_sum = float((p_values * q_values).sum())
        total_var = float(data.sum(axis=1).var(ddof=1))
        kr20 = float((k / (k - 1)) * (1 - pq_sum / total_var)) if total_var > 0 else 0.0
        return build_result("Kuder-Richardson 20", "kr20", "KR-20", kr20, n=len(data),
                            effect_size_name="KR-20", effect_size_value=kr20,
                            effect_size_interpretation=_interp_alpha(kr20),
                            additional_stats={"kr20": round(kr20, 4), "n_items": k,
                                              "interpretation": _interp_alpha(kr20),
                                              "item_difficulties": p_values.round(4).to_dict()})
    except Exception as e:
        return build_error("KR-20", "kr20", str(e), "Ensure all items are coded 0/1.")
