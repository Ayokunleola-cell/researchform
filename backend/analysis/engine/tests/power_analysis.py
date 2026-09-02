"""
analysis/engine/tests/power_analysis.py

Statistical Power Analysis & Sample Size Calculator.
Uses scipy.stats and statsmodels.stats.power.

Supports:
  - Independent-samples t-test
  - Paired t-test / one-sample t-test
  - One-way ANOVA
  - Pearson / Spearman correlation
  - Chi-square goodness-of-fit
  - Multiple regression (R² change)
  - General sample size solver
"""
from __future__ import annotations
import math
import numpy as np
from scipy import stats as _stats
from analysis.engine.schema import build_result, build_error


def _safe(v):
    if v is None:
        return None
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None
    if fv != fv:  # NaN check
        return None
    return round(fv, 4)


def _ceil(v):
    """Safely ceil a numpy scalar or float to int."""
    import math
    try:
        return math.ceil(float(v))
    except (TypeError, ValueError, OverflowError):
        return int(v) if v else 0


# ─── Effect size reference tables ─────────────────────────────────────────────

COHEN_D_GUIDE = {"small": 0.2, "medium": 0.5, "large": 0.8}
COHEN_F_GUIDE = {"small": 0.10, "medium": 0.25, "large": 0.40}
COHEN_W_GUIDE = {"small": 0.10, "medium": 0.30, "large": 0.50}
R_GUIDE       = {"small": 0.10, "medium": 0.30, "large": 0.50}
F2_GUIDE      = {"small": 0.02, "medium": 0.15, "large": 0.35}


def _effect_label(value: float, guide: dict) -> str:
    if value >= guide["large"]:  return "large"
    if value >= guide["medium"]: return "medium"
    return "small"


# ─── Power curve helper ────────────────────────────────────────────────────────

def _power_curve(analysis_obj, ns: list[int]) -> list[dict]:
    """Compute power at each n for a power curve chart."""
    curve = []
    for n in ns:
        try:
            pwr = analysis_obj.power(nobs=n) if hasattr(analysis_obj, 'power') else None
            if pwr is not None:
                curve.append({"n": n, "power": round(float(pwr), 4)})
        except Exception:
            pass
    return curve


# ─── Test implementations ──────────────────────────────────────────────────────

def run_power_t_independent(df=None, variables=None, brief=None, alpha=0.05,
                             effect_size=0.5, power=0.80, n=None, **kw):
    """
    Power analysis for independent-samples t-test.
    Solves for whichever of (effect_size, power, n) is None/missing.
    """
    from statsmodels.stats.power import TTestIndPower
    analysis = TTestIndPower()
    try:
        if n is None:
            # Solve for required n
            n_required = analysis.solve_power(effect_size=effect_size, alpha=alpha, power=power)
            n_per_group = _ceil(n_required)
            achieved_power = analysis.power(effect_size=effect_size, nobs1=n_per_group, alpha=alpha)
            solved = "n"
        elif power is None:
            achieved_power = analysis.power(effect_size=effect_size, nobs1=n, alpha=alpha)
            n_per_group = int(n)
            solved = "power"
        else:
            n_required = analysis.solve_power(effect_size=effect_size, alpha=alpha, power=power)
            n_per_group = _ceil(n_required)
            achieved_power = analysis.power(effect_size=effect_size, nobs1=n_per_group, alpha=alpha)
            solved = "n"

        # Power curve (n = 10 to 300)
        ns = list(range(10, 301, 10))
        curve_data = []
        for ni in ns:
            try:
                p = analysis.power(effect_size=effect_size, nobs1=ni, alpha=alpha)
                curve_data.append({"n": ni, "power": round(float(p), 4)})
            except Exception:
                pass

        res = {
            "test_name": "Power Analysis — Independent t-test",
            "test_function": "power_t_independent",
            "solved_for": solved,
            "inputs": {
                "effect_size_d": _safe(effect_size),
                "alpha": _safe(alpha),
                "target_power": _safe(power),
                "effect_label": _effect_label(abs(effect_size), COHEN_D_GUIDE),
            },
            "result": {
                "n_per_group": n_per_group,
                "total_n": n_per_group * 2,
                "achieved_power": _safe(achieved_power),
                "alpha": _safe(alpha),
                "effect_size_d": _safe(effect_size),
            },
            "power_curve": curve_data,
            "interpretation": (
                f"To detect a {'small' if abs(effect_size) < 0.5 else 'medium' if abs(effect_size) < 0.8 else 'large'} "
                f"effect (d={effect_size:.2f}) with {power*100:.0f}% power at α={alpha}, "
                f"you need **{n_per_group} participants per group** ({n_per_group*2} total)."
            ),
            "effect_size_guide": COHEN_D_GUIDE,
        }
        return build_result(
            test_name=res["test_name"],
            test_function=res["test_function"],
            statistic_label='Power',
            statistic_value=round(float(achieved_power), 4) if achieved_power is not None else None,
            p_value=None,
            n=int(n_per_group * 2) if n_per_group else None,
            conclusion=res["interpretation"],
            additional_stats=res
        )
    except Exception as e:
        return build_error(
            test_name="Power Analysis — Independent t-test",
            test_function="power_t_independent",
            reason=str(e),
            suggestion="Check power analysis inputs."
        )


def run_power_t_paired(df=None, variables=None, brief=None, alpha=0.05,
                        effect_size=0.5, power=0.80, n=None, **kw):
    """Power analysis for paired/one-sample t-test."""
    from statsmodels.stats.power import TTestPower
    analysis = TTestPower()
    try:
        if n is None:
            n_required = analysis.solve_power(effect_size=effect_size, alpha=alpha, power=power)
            n_pairs = _ceil(n_required)
            achieved_power = analysis.power(effect_size=effect_size, nobs=n_pairs, alpha=alpha)
        else:
            n_pairs = int(n)
            achieved_power = analysis.power(effect_size=effect_size, nobs=n_pairs, alpha=alpha)

        ns = list(range(5, 201, 5))
        curve_data = []
        for ni in ns:
            try:
                p = analysis.power(effect_size=effect_size, nobs=ni, alpha=alpha)
                curve_data.append({"n": ni, "power": round(float(p), 4)})
            except Exception:
                pass

        res = {
            "test_name": "Power Analysis — Paired t-test",
            "test_function": "power_t_paired",
            "result": {
                "n_pairs": n_pairs,
                "achieved_power": _safe(achieved_power),
                "alpha": _safe(alpha),
                "effect_size_d": _safe(effect_size),
            },
            "power_curve": curve_data,
            "interpretation": (
                f"You need **{n_pairs} matched pairs** to detect d={effect_size:.2f} "
                f"with {power*100:.0f}% power at α={alpha}."
            ),
            "effect_size_guide": COHEN_D_GUIDE,
        }
        return build_result(
            test_name=res["test_name"],
            test_function=res["test_function"],
            statistic_label='Power',
            statistic_value=round(float(achieved_power), 4) if achieved_power is not None else None,
            p_value=None,
            n=int(n_pairs) if n_pairs else None,
            conclusion=res["interpretation"],
            additional_stats=res
        )
    except Exception as e:
        return build_error(
            test_name="Power Analysis — Paired t-test",
            test_function="power_t_paired",
            reason=str(e),
            suggestion="Check power analysis inputs."
        )


def run_power_anova(df=None, variables=None, brief=None, alpha=0.05,
                    effect_size=0.25, power=0.80, k_groups=3, n=None, **kw):
    """Power analysis for one-way ANOVA (Cohen's f)."""
    from statsmodels.stats.power import FTestAnovaPower
    analysis = FTestAnovaPower()
    try:
        if n is None:
            n_required = analysis.solve_power(effect_size=effect_size, alpha=alpha,
                                               power=power, k_groups=k_groups)
            n_per_group = _ceil(n_required)
            achieved_power = analysis.power(effect_size=effect_size, nobs=n_per_group,
                                             alpha=alpha, k_groups=k_groups)
        else:
            n_per_group = int(n)
            achieved_power = analysis.power(effect_size=effect_size, nobs=n_per_group,
                                             alpha=alpha, k_groups=k_groups)

        ns = list(range(5, 201, 5))
        curve_data = []
        for ni in ns:
            try:
                p = analysis.power(effect_size=effect_size, nobs=ni, alpha=alpha, k_groups=k_groups)
                curve_data.append({"n": ni, "power": round(float(p), 4)})
            except Exception:
                pass

        res = {
            "test_name": f"Power Analysis — One-way ANOVA ({k_groups} groups)",
            "test_function": "power_anova",
            "result": {
                "n_per_group": n_per_group,
                "total_n": n_per_group * k_groups,
                "k_groups": k_groups,
                "achieved_power": _safe(achieved_power),
                "alpha": _safe(alpha),
                "effect_size_f": _safe(effect_size),
            },
            "power_curve": curve_data,
            "interpretation": (
                f"For a {k_groups}-group ANOVA with f={effect_size:.2f}, "
                f"you need **{n_per_group} per group** ({n_per_group*k_groups} total) "
                f"for {power*100:.0f}% power."
            ),
            "effect_size_guide": COHEN_F_GUIDE,
        }
        return build_result(
            test_name=res["test_name"],
            test_function=res["test_function"],
            statistic_label='Power',
            statistic_value=round(float(achieved_power), 4) if achieved_power is not None else None,
            p_value=None,
            n=int(n_per_group * k_groups) if n_per_group else None,
            conclusion=res["interpretation"],
            additional_stats=res
        )
    except Exception as e:
        return build_error(
            test_name="Power Analysis — ANOVA",
            test_function="power_anova",
            reason=str(e),
            suggestion="Check power analysis inputs."
        )


def run_power_correlation(df=None, variables=None, brief=None, alpha=0.05,
                           effect_size=0.3, power=0.80, n=None, **kw):
    """Power analysis for Pearson correlation (r)."""
    try:
        r = effect_size  # r is the effect size here
        # Use Fisher z approximation
        if n is None:
            # Binary search for n
            for n_try in range(5, 2001):
                r_safe = max(-0.9999, min(0.9999, r))
                z_r = 0.5 * math.log((1 + r_safe) / (1 - r_safe))
                se = 1.0 / math.sqrt(n_try - 3)
                z_alpha = _stats.norm.ppf(1 - alpha / 2)
                pwr = 1 - _stats.norm.cdf(z_alpha - z_r / se) + _stats.norm.cdf(-z_alpha - z_r / se)
                if pwr >= power:
                    n_required = n_try
                    achieved_power = pwr
                    break
            else:
                n_required = 2000
                achieved_power = power
        else:
            n_required = int(n)
            z_r = 0.5 * math.log((1 + abs(r)) / (1 - abs(r) + 1e-9))
            se = 1.0 / math.sqrt(max(n_required - 3, 1))
            z_alpha = _stats.norm.ppf(1 - alpha / 2)
            achieved_power = 1 - _stats.norm.cdf(z_alpha - z_r / se) + _stats.norm.cdf(-z_alpha - z_r / se)

        ns = list(range(5, 301, 5))
        curve_data = []
        for ni in ns:
            try:
                z_r = 0.5 * math.log((1 + abs(r)) / (1 - abs(r) + 1e-9))
                se = 1.0 / math.sqrt(max(ni - 3, 1))
                z_alpha = _stats.norm.ppf(1 - alpha / 2)
                p = 1 - _stats.norm.cdf(z_alpha - z_r / se) + _stats.norm.cdf(-z_alpha - z_r / se)
                curve_data.append({"n": ni, "power": round(float(min(p, 1.0)), 4)})
            except Exception:
                pass

        res = {
            "test_name": "Power Analysis — Pearson Correlation",
            "test_function": "power_correlation",
            "result": {
                "n_required": n_required,
                "achieved_power": _safe(achieved_power),
                "alpha": _safe(alpha),
                "r": _safe(r),
            },
            "power_curve": curve_data,
            "interpretation": (
                f"To detect r={r:.2f} with {power*100:.0f}% power at α={alpha}, "
                f"you need **{n_required} participants**."
            ),
            "effect_size_guide": R_GUIDE,
        }
        return build_result(
            test_name=res["test_name"],
            test_function=res["test_function"],
            statistic_label='Power',
            statistic_value=round(float(achieved_power), 4) if achieved_power is not None else None,
            p_value=None,
            n=int(n_required) if n_required else None,
            conclusion=res["interpretation"],
            additional_stats=res
        )
    except Exception as e:
        return build_error(
            test_name="Power Analysis — Correlation",
            test_function="power_correlation",
            reason=str(e),
            suggestion="Check power analysis inputs."
        )


def run_power_chi_square(df=None, variables=None, brief=None, alpha=0.05,
                          effect_size=0.3, power=0.80, df_val=1, n=None, **kw):
    """Power analysis for chi-square test (Cohen's w)."""
    from statsmodels.stats.power import GofChisquarePower
    analysis = GofChisquarePower()
    try:
        if n is None:
            n_required = analysis.solve_power(effect_size=effect_size, alpha=alpha,
                                               power=power, n_bins=df_val + 1)
            n_required = _ceil(n_required)
            achieved_power = analysis.power(effect_size=effect_size, nobs=n_required,
                                             alpha=alpha, n_bins=df_val + 1)
        else:
            n_required = int(n)
            achieved_power = analysis.power(effect_size=effect_size, nobs=n_required,
                                             alpha=alpha, n_bins=df_val + 1)

        ns = list(range(10, 401, 10))
        curve_data = []
        for ni in ns:
            try:
                p = analysis.power(effect_size=effect_size, nobs=ni, alpha=alpha, n_bins=df_val + 1)
                curve_data.append({"n": ni, "power": round(float(p), 4)})
            except Exception:
                pass

        res = {
            "test_name": f"Power Analysis — Chi-square (df={df_val})",
            "test_function": "power_chi_square",
            "result": {
                "n_required": n_required,
                "achieved_power": _safe(achieved_power),
                "alpha": _safe(alpha),
                "effect_size_w": _safe(effect_size),
                "df": df_val,
            },
            "power_curve": curve_data,
            "interpretation": (
                f"To detect w={effect_size:.2f} (df={df_val}) with {power*100:.0f}% power, "
                f"you need **{n_required} participants**."
            ),
            "effect_size_guide": COHEN_W_GUIDE,
        }
        return build_result(
            test_name=res["test_name"],
            test_function=res["test_function"],
            statistic_label='Power',
            statistic_value=round(float(achieved_power), 4) if achieved_power is not None else None,
            p_value=None,
            n=int(n_required) if n_required else None,
            conclusion=res["interpretation"],
            additional_stats=res
        )
    except Exception as e:
        return build_error(
            test_name="Power Analysis — Chi-square",
            test_function="power_chi_square",
            reason=str(e),
            suggestion="Check power analysis inputs."
        )


def run_power_regression(df=None, variables=None, brief=None, alpha=0.05,
                          effect_size=0.15, power=0.80, predictors=3, n=None, **kw):
    """Power analysis for multiple regression (Cohen's f²).

    Uses scipy non-central F directly — avoids statsmodels FTestPower which
    returns numpy arrays that are incompatible with math.ceil / float().

    Non-centrality parameter:  ncp = f² × n
    Critical value:            F_crit at (df_num, df_denom) with alpha
    Power:                     P( F' > F_crit )  where F' ~ ncf(df_num, df_denom, ncp)
    """
    from scipy import stats as _sp
    try:
        p_pred = int(predictors)          # number of predictors = df_num
        f2     = float(effect_size)       # Cohen's f² effect size
        alpha  = float(alpha)
        power  = float(power)

        def _reg_power(n_obs: int) -> float:
            """Return power (plain Python float) for a given total n."""
            df_denom = n_obs - p_pred - 1
            if df_denom < 1:
                return 0.0
            ncp    = f2 * float(n_obs)
            f_crit = float(_sp.f.ppf(1.0 - alpha, p_pred, df_denom))
            pwr    = float(1.0 - _sp.ncf.cdf(f_crit, p_pred, df_denom, ncp))
            return min(max(pwr, 0.0), 1.0)

        if n is None:
            # Linear search for minimum N achieving the target power
            n_required = p_pred + 2
            for n_try in range(p_pred + 2, 5001):
                if _reg_power(n_try) >= power:
                    n_required = n_try
                    break
            else:
                n_required = 5000
        else:
            n_required = int(n)

        achieved_power = _reg_power(n_required)

        # Power curve: n from (predictors+2) to 400, step 10
        curve_data = []
        for ni in range(p_pred + 2, 401, 10):
            curve_data.append({"n": ni, "power": round(_reg_power(ni), 4)})

        label = "small" if f2 < 0.15 else ("medium" if f2 < 0.35 else "large")
        res = {
            "test_name": f"Power Analysis — Multiple Regression ({p_pred} predictor{'s' if p_pred != 1 else ''})",
            "test_function": "power_regression",
            "result": {
                "n_required": n_required,
                "achieved_power": _safe(achieved_power),
                "alpha": _safe(alpha),
                "effect_size_f2": _safe(f2),
                "predictors": p_pred,
            },
            "power_curve": curve_data,
            "interpretation": (
                f"For regression with {p_pred} predictor(s) and {label} effect "
                f"(f²={f2:.2f}), you need **{n_required} participants** "
                f"for {power*100:.0f}% power at α={alpha}."
            ),
            "effect_size_guide": F2_GUIDE,
        }
        return build_result(
            test_name=res["test_name"],
            test_function=res["test_function"],
            statistic_label='Power',
            statistic_value=round(float(achieved_power), 4) if achieved_power is not None else None,
            p_value=None,
            n=int(n_required) if n_required else None,
            conclusion=res["interpretation"],
            additional_stats=res
        )
    except Exception as e:
        return build_error(
            test_name="Power Analysis — Regression",
            test_function="power_regression",
            reason=str(e),
            suggestion="Check power analysis inputs."
        )



def run_sample_size_calculator(df=None, variables=None, brief=None, **kw):
    """
    General sample size calculator — dispatches to appropriate test.
    Reads parameters from brief or kw.
    """
    test_type   = kw.get("test_type", brief.get("power_test_type", "independent_t") if brief else "independent_t")
    effect_size = float(kw.get("effect_size", brief.get("effect_size", 0.5) if brief else 0.5))
    alpha       = float(kw.get("alpha", 0.05))
    power       = float(kw.get("power", 0.80))
    k_groups    = int(kw.get("k_groups", 3))
    predictors  = int(kw.get("predictors", 3))
    df_val      = int(kw.get("df_val", 1))

    dispatch = {
        "independent_t":   run_power_t_independent,
        "paired_t":        run_power_t_paired,
        "one_sample_t":    run_power_t_paired,
        "anova":           run_power_anova,
        "correlation":     run_power_correlation,
        "chi_square":      run_power_chi_square,
        "regression":      run_power_regression,
    }
    fn = dispatch.get(test_type, run_power_t_independent)
    return fn(df=df, variables=variables, brief=brief,
              alpha=alpha, effect_size=effect_size, power=power,
              k_groups=k_groups, predictors=predictors, df_val=df_val)
