# backend/analysis/engine/schema.py
"""
Standardized result schema for every statistical test.
Every test function returns build_result() or build_error() — nothing else.
"""
from __future__ import annotations


def build_result(
    test_name: str,
    test_function: str,
    statistic_label: str,
    statistic_value,
    p_value: float = None,
    n: int = None,
    effect_size_name: str = None,
    effect_size_value: float = None,
    effect_size_interpretation: str = None,
    ci_lower: float = None,
    ci_upper: float = None,
    ci_level: float = 0.95,
    df=None,
    df_val=None,          # alias for df (degrees of freedom) — accepted for compatibility
    additional_stats: dict = None,
    assumptions: dict = None,
    conclusion: str = None,
    significant: bool = None,
    alpha: float = 0.05,
    table: list = None,
    test_key: str = None,  # registry key — stamped by dispatcher
) -> dict:
    """
    Universal result container for ALL statistical tests.
    Claude receives this and writes the report — it never recalculates.
    """
    # Support df_val as alias for df (degrees of freedom)
    if df is None and df_val is not None:
        df = df_val

    if significant is None and p_value is not None:
        significant = bool(p_value < alpha)

    _round = lambda v, d=4: round(float(v), d) if v is not None else None

    return {
        "test_name": test_name,
        "test_key": test_key,           # registry key — stamped by dispatcher after creation
        "test_function": test_function,
        "statistic_label": statistic_label,  # convenience top-level alias
        "statistic": {
            "label": statistic_label,
            "value": _round(statistic_value),
        },
        "df": df,
        "p_value": _round(p_value),
        "significant": significant,
        "alpha": alpha,
        "n": int(n) if n is not None else None,
        "effect_size": {
            "name": effect_size_name,
            "value": _round(effect_size_value),
            "interpretation": effect_size_interpretation,
        },
        "confidence_interval": {
            "lower": _round(ci_lower),
            "upper": _round(ci_upper),
            "level": ci_level,
        },
        "additional_stats": additional_stats or {},
        "assumptions": assumptions or {},
        "conclusion": conclusion or _auto_conclusion(test_name, statistic_label, statistic_value, df, p_value, alpha, significant),
        "table": table,  # for matrices, post-hoc tables, etc.
    }


def build_error(test_name: str, test_function: str, reason: str, suggestion: str, test_key: str = None) -> dict:
    """Returned when a test cannot run — data incompatibility or runtime error."""
    return {
        "test_name": test_name,
        "test_key": test_key,
        "test_function": test_function,
        "statistic_label": None,
        "error": True,
        "reason": reason,
        "suggestion": suggestion,
        "statistic": {"label": None, "value": None},
        "p_value": None,
        "significant": None,
        "n": None,
        "effect_size": {"name": None, "value": None, "interpretation": None},
        "confidence_interval": {"lower": None, "upper": None, "level": 0.95},
        "additional_stats": {},
        "assumptions": {},
        "conclusion": None,
        "table": None,
    }


def _auto_conclusion(test_name, stat_label, stat_val, df, p_value, alpha, significant) -> str:
    """Generate a standard APA conclusion sentence."""
    if p_value is None:
        return ""
    stat_str = f"{stat_label}"
    if df is not None:
        stat_str += f"({df})"
    if stat_val is not None:
        stat_str += f" = {round(float(stat_val), 3)}"
    p_str = f"p = {round(float(p_value), 3)}" if p_value >= 0.001 else "p < .001"
    decision = "rejected" if significant else "not rejected"
    return (
        f"The {test_name} yielded {stat_str}, {p_str}, which is "
        f"{'less' if significant else 'greater'} than α = {alpha}. "
        f"Therefore, the null hypothesis is {decision}."
    )


def interpret_effect_size(name: str, value: float) -> str:
    """Universal effect size interpreter."""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if name in ("Cohen's d",):
        if abs_val < 0.2:   return "negligible"
        if abs_val < 0.5:   return "small"
        if abs_val < 0.8:   return "medium"
        return "large"
    if name in ("eta-squared", "partial eta-squared", "omega-squared"):
        if abs_val < 0.01:  return "negligible"
        if abs_val < 0.06:  return "small"
        if abs_val < 0.14:  return "medium"
        return "large"
    if name in ("r", "Pearson r", "Spearman rho", "point-biserial r"):
        if abs_val < 0.1:   return "negligible"
        if abs_val < 0.3:   return "small"
        if abs_val < 0.5:   return "medium"
        return "large"
    if name in ("Cramer's V", "phi"):
        if abs_val < 0.1:   return "negligible"
        if abs_val < 0.3:   return "small"
        if abs_val < 0.5:   return "medium"
        return "large"
    if name == "R-squared":
        if abs_val < 0.02:  return "negligible"
        if abs_val < 0.13:  return "small"
        if abs_val < 0.26:  return "medium"
        return "large"
    return "see guidelines"
