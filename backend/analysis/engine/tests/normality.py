# backend/analysis/engine/tests/normality.py
"""All normality test functions — pre-built and deterministic."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error


def _get_numeric(df, variables):
    return [c for c in (variables or df.columns) if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]


def _run_one(series: pd.Series, alpha: float):
    s = series.dropna()
    n = len(s)
    if n < 3:
        return None
    if n < 50:
        stat, p = stats.shapiro(s)
        return {"test": "Shapiro-Wilk", "statistic": round(float(stat), 4),
                "p_value": round(float(p), 4), "normal": bool(p > alpha), "n": n}
    else:
        stat, p = stats.kstest((s - s.mean()) / s.std(), "norm")
        return {"test": "Kolmogorov-Smirnov", "statistic": round(float(stat), 4),
                "p_value": round(float(p), 4), "normal": bool(p > alpha), "n": n}


def run_normality_check(df, variables, brief, alpha=0.05):
    try:
        cols = _get_numeric(df, variables)
        if not cols:
            return build_error("Normality Check", "normality_check",
                               "No numeric columns found in the selected variables.", "Select numeric columns.")
        results = {}
        for col in cols:
            r = _run_one(df[col], alpha)
            if r:
                results[col] = r

        # Promote the first (or worst non-normal) column to top-level for summary table
        primary = None
        for col, r in results.items():
            if primary is None or (not r["normal"] and primary.get("normal", True)):
                primary = r
        top_stat = primary["statistic"] if primary else None
        top_p = primary["p_value"] if primary else None
        top_label = primary["test"].split("-")[0][0] if primary else "W"
        n_non_normal = sum(1 for r in results.values() if not r["normal"])
        conclusion = (
            f"Normality tested for {len(results)} variable(s): "
            f"{n_non_normal} non-normal at alpha={alpha}."
        ) if results else ""
        return build_result(
            "Normality Check", "normality_check",
            top_label, top_stat, p_value=top_p, n=len(df),
            significant=bool(top_p is not None and top_p < alpha),
            effect_size_name=None, effect_size_value=None,
            conclusion=conclusion,
            additional_stats={"columns": results}
        )
    except Exception as e:
        return build_error("Normality Check", "normality_check", str(e), "Ensure numeric columns with >= 3 observations.")


def run_shapiro_wilk_all(df, variables, brief, alpha=0.05):
    try:
        cols = _get_numeric(df, variables)
        results = {}
        for col in cols:
            s = df[col].dropna()
            if len(s) < 3:
                continue
            if len(s) > 5000:
                s = s.sample(5000, random_state=42)
            stat, p = stats.shapiro(s)
            results[col] = {"W": round(float(stat), 4), "p_value": round(float(p), 4),
                            "normal": bool(p > alpha), "n": len(s),
                            "interpretation": "Normal distribution" if p > alpha else "Non-normal distribution"}
        return build_result("Shapiro-Wilk Test", "shapiro_wilk_all", "W", None, n=len(df),
                            additional_stats={"columns": results})
    except Exception as e:
        return build_error("Shapiro-Wilk Test", "shapiro_wilk_all", str(e), "Need >= 3 numeric values.")


def run_ks_test(df, variables, brief, alpha=0.05):
    try:
        cols = _get_numeric(df, variables)
        results = {}
        for col in cols:
            s = df[col].dropna()
            if len(s) < 5:
                continue
            s_clean = s
            try:
                from statsmodels.stats.diagnostic import lilliefors as sm_lilliefors
                stat, p = sm_lilliefors(s_clean, dist='norm')
                method_used = 'Lilliefors'
            except ImportError:
                stat, p = stats.kstest((s_clean - s_clean.mean()) / max(s_clean.std(), 1e-10), 'norm')
                method_used = 'KS (estimated params, conservative)'
            results[col] = {"D": round(float(stat), 4), "p_value": round(float(p), 4),
                            "normal": bool(p > alpha), "n": len(s), "method": method_used}

        # Promote worst (smallest p) column to top-level for summary
        primary = None
        if results:
            primary = min(results.values(), key=lambda r: r["p_value"])
        top_D = primary["D"] if primary else None
        top_p = primary["p_value"] if primary else None
        n_non_normal = sum(1 for r in results.values() if not r["normal"])
        conclusion = (
            f"KS test for {len(results)} variable(s): {n_non_normal} non-normal at alpha={alpha}."
        ) if results else ""
        return build_result(
            "Kolmogorov-Smirnov Test", "kolmogorov_smirnov",
            "D", top_D, p_value=top_p, n=len(df),
            significant=bool(top_p is not None and top_p < alpha),
            conclusion=conclusion,
            additional_stats={"columns": results}
        )
    except Exception as e:
        return build_error("Kolmogorov-Smirnov Test", "kolmogorov_smirnov", str(e), "Need >= 5 observations.")


def run_anderson_darling(df, variables, brief, alpha=0.05):
    try:
        cols = _get_numeric(df, variables)
        results = {}
        for col in cols:
            s = df[col].dropna()
            if len(s) < 3:
                continue
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning, module="scipy")
                result = stats.anderson(s, dist="norm")
            sig_levels = [15, 10, 5, 2.5, 1]
            passed_at = {}
            for sl, cv in zip(sig_levels, result.critical_values):
                passed_at[f"{sl}%"] = bool(result.statistic < cv)
            # Derive a p-value proxy: compare A² to 5% critical value
            crit_5pct_idx = 2  # index for 5% in sig_levels
            crit_5pct = result.critical_values[crit_5pct_idx]
            # Approximate p: use ratio of statistic to critical value as a proxy
            # We use 0.05 if fails at 5%, else 0.10, 0.15, etc.
            non_normal_p = None
            for sl, cv in zip([0.01, 0.025, 0.05, 0.10, 0.15],
                               list(reversed(result.critical_values))):
                if result.statistic > cv:
                    non_normal_p = sl
                    break
            if non_normal_p is None:
                non_normal_p = 0.15  # passes all levels
            results[col] = {
                "A2": round(float(result.statistic), 4),
                "p_approx": non_normal_p,
                "critical_values": {f"{sl}%": round(float(cv), 4) for sl, cv in zip(sig_levels, result.critical_values)},
                "passed_at_significance": passed_at,
                "normal_at_5pct": passed_at.get("5%", False), "n": len(s),
            }

        # Promote worst column (highest A2) to top-level
        primary = None
        if results:
            primary = max(results.values(), key=lambda r: r["A2"])
        top_A2 = primary["A2"] if primary else None
        top_p = primary["p_approx"] if primary else None
        n_non_normal = sum(1 for r in results.values() if not r["normal_at_5pct"])
        conclusion = (
            f"Anderson-Darling for {len(results)} variable(s): {n_non_normal} non-normal at 5%."
        ) if results else ""
        return build_result(
            "Anderson-Darling Test", "anderson_darling",
            "A2", top_A2, p_value=top_p, n=len(df),
            significant=bool(top_p is not None and top_p < alpha),
            conclusion=conclusion,
            additional_stats={"columns": results}
        )
    except Exception as e:
        return build_error("Anderson-Darling Test", "anderson_darling", str(e), "Need >= 3 observations.")


def run_jarque_bera(df, variables, brief, alpha=0.05):
    try:
        cols = _get_numeric(df, variables)
        results = {}
        for col in cols:
            s = df[col].dropna()
            if len(s) < 3:
                continue
            jb, p = stats.jarque_bera(s)
            results[col] = {"JB": round(float(jb), 4), "p_value": round(float(p), 4),
                            "normal": bool(p > alpha), "n": len(s),
                            "skewness": round(float(s.skew()), 4), "kurtosis": round(float(s.kurtosis()), 4)}
        return build_result("Jarque-Bera Test", "jarque_bera", "JB", None, n=len(df),
                            additional_stats={"columns": results})
    except Exception as e:
        return build_error("Jarque-Bera Test", "jarque_bera", str(e), "Need >= 3 numeric observations.")


def run_dagostino_pearson(df, variables, brief, alpha=0.05):
    try:
        cols = _get_numeric(df, variables)
        results = {}
        for col in cols:
            s = df[col].dropna()
            if len(s) < 8:
                continue
            stat, p = stats.normaltest(s)
            results[col] = {"K2": round(float(stat), 4), "p_value": round(float(p), 4),
                            "normal": bool(p > alpha), "n": len(s)}
        return build_result("D'Agostino-Pearson Test", "dagostino_pearson", "K²", None, n=len(df),
                            additional_stats={"columns": results})
    except Exception as e:
        return build_error("D'Agostino-Pearson Test", "dagostino_pearson", str(e), "Need >= 8 observations.")


def run_omnibus_normality(df, variables, brief, alpha=0.05):
    try:
        cols = _get_numeric(df, variables)
        table = []
        for col in cols:
            s = df[col].dropna()
            n = len(s)
            if n < 3:
                continue
            row = {"variable": col, "n": n}
            # Shapiro-Wilk
            try:
                samp = s if n <= 5000 else s.sample(5000, random_state=42)
                sw_s, sw_p = stats.shapiro(samp)
                row["shapiro_W"] = round(float(sw_s), 4)
                row["shapiro_p"] = round(float(sw_p), 4)
                row["shapiro_normal"] = bool(sw_p > alpha)
            except Exception:
                row["shapiro_W"] = None; row["shapiro_p"] = None; row["shapiro_normal"] = None
            # K-S
            try:
                std_s = (s - s.mean()) / s.std()
                ks_s, ks_p = stats.kstest(std_s, "norm")
                row["ks_D"] = round(float(ks_s), 4); row["ks_p"] = round(float(ks_p), 4)
                row["ks_normal"] = bool(ks_p > alpha)
            except Exception:
                row["ks_D"] = None; row["ks_p"] = None; row["ks_normal"] = None
            # Jarque-Bera
            try:
                jb_s, jb_p = stats.jarque_bera(s)
                row["jb_stat"] = round(float(jb_s), 4); row["jb_p"] = round(float(jb_p), 4)
                row["jb_normal"] = bool(jb_p > alpha)
            except Exception:
                row["jb_stat"] = None; row["jb_p"] = None; row["jb_normal"] = None
            # D'Agostino
            try:
                if n >= 8:
                    dp_s, dp_p = stats.normaltest(s)
                    row["dp_K2"] = round(float(dp_s), 4); row["dp_p"] = round(float(dp_p), 4)
                    row["dp_normal"] = bool(dp_p > alpha)
                else:
                    row["dp_K2"] = None; row["dp_p"] = None; row["dp_normal"] = None
            except Exception:
                row["dp_K2"] = None; row["dp_p"] = None; row["dp_normal"] = None
            # Overall verdict: majority vote among available tests
            verdicts = [v for v in [row.get("shapiro_normal"), row.get("ks_normal"),
                                     row.get("jb_normal"), row.get("dp_normal")] if v is not None]
            row["overall_verdict"] = "normal" if (sum(verdicts) / len(verdicts) >= 0.5) else "non-normal"
            table.append(row)
        return build_result("Omnibus Normality Tests", "omnibus_normality", "N", len(df), n=len(df),
                            additional_stats={"table": table}, table=table)
    except Exception as e:
        return build_error("Omnibus Normality Tests", "omnibus_normality", str(e), "Need numeric columns >= 3 obs.")
