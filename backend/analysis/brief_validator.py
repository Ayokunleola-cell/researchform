# backend/analysis/brief_validator.py
"""
Research Brief Validator & Sanitiser.

Runs BEFORE the analysis pipeline starts on every job.
Guarantees the pipeline always receives a well-formed brief dict —
no None values, no injection strings, no out-of-range numbers.

Usage:
    from analysis.brief_validator import validate_and_clean_brief
    brief = validate_and_clean_brief(raw_brief)
"""
from __future__ import annotations
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
_MAX_TOPIC          = 300
_MAX_STR_FIELD      = 500
_MAX_HYPOTHESIS_LEN = 400
_MAX_OBJECTIVES     = 15
_MAX_HYPOTHESES     = 15
_MAX_KEYWORDS       = 20
_VALID_SIG_LEVELS   = (0.001, 0.10)   # clamp range
_DEFAULT_SIG        = 0.05
_VALID_REPORT_TYPES = {
    "chapter4", "business_report", "policy_brief",
    "executive_summary", "technical_report", "literature_review",
    "slide_deck", "academic_report", "research_paper",
}
_VALID_TRADITIONS   = {"standard", "apa", "chicago", "harvard", "ieee", "nigerian", "uk"}
_VALID_USER_CLASSES = {
    "bsc",          # Undergraduate dissertation
    "msc",          # Master's dissertation
    "phd",          # Doctoral thesis
    "researcher",   # Academic / independent researcher
    "business",     # Business analyst / corporate report
}
_VALID_RESEARCH_DESIGNS = {
    "cross_sectional",  # One-time data collection from a sample
    "longitudinal",     # Same group measured at multiple time points
    "experimental",     # Controlled experiment / A-B test
    "survey",           # Structured questionnaire / opinion data
    "pre_post",         # Measurement before and after an intervention
    "correlational",    # Relationship-focused, no manipulation
    "case_study",       # In-depth study of one or few cases
    "exploratory",      # Discovery-based, no prior hypothesis
}
_VALID_SCALE_TYPES = {
    "nominal",      # Categories with no order (e.g. Gender, Region)
    "ordinal",      # Ranked categories (e.g. Low/Medium/High)
    "likert_5",     # Likert 1–5 scale
    "likert_7",     # Likert 1–7 scale
    "interval",     # Equal spacing, no true zero (e.g. temperature in °C)
    "ratio",        # True zero, equal spacing (e.g. age, income)
    "continuous",   # Alias for ratio
    "binary",       # 0/1 or Yes/No
}
_VALID_STUDY_TYPES  = {
    "quantitative", "qualitative", "mixed", "descriptive",
    "experimental", "correlation", "trend", "segmentation",
    "survey", "case_study", "action",
}
_VALID_MISSING      = {"auto", "mean_impute", "median_impute", "mode_impute",
                       "drop_rows", "flag_only", "knn_impute", "mice_impute"}


# Characters that must never appear in LLM prompt strings
_CONTROL_CHAR_RE  = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
# Strip HTML tags
_HTML_TAG_RE      = re.compile(r'<[^>]{0,200}>')
# Collapse whitespace
_WHITESPACE_RE    = re.compile(r'[ \t]{2,}')


# ─── Core sanitiser ──────────────────────────────────────────────────────────

def _clean_str(value: Any, max_len: int = _MAX_STR_FIELD) -> str:
    """Return a safe, trimmed string from any input."""
    if value is None:
        return ""
    s = str(value)
    s = _HTML_TAG_RE.sub("", s)           # strip HTML
    s = _CONTROL_CHAR_RE.sub("", s)       # strip control chars
    s = _WHITESPACE_RE.sub(" ", s)        # collapse double spaces
    return s.strip()[:max_len]


def _clean_list_of_strings(lst: Any, item_max: int, list_max: int) -> list[str]:
    """Sanitise a list of strings, removing empties and capping length."""
    if not isinstance(lst, list):
        return []
    result = []
    for item in lst[:list_max]:
        cleaned = _clean_str(item, item_max)
        if cleaned:
            result.append(cleaned)
    return result


def _clamp_float(value: Any, lo: float, hi: float, default: float) -> float:
    """Parse and clamp a float to [lo, hi], using default on failure."""
    try:
        f = float(value)
        return max(lo, min(hi, f))
    except (TypeError, ValueError):
        return default


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


# ─── Main public function ─────────────────────────────────────────────────────

def validate_and_clean_brief(raw: dict | None) -> dict:
    """
    Validate, sanitise and fill-in-defaults for every field in a research brief.

    Returns a clean dict the pipeline can safely use without None-checks.
    Never raises — all errors produce logged warnings + sensible defaults.
    """
    if not isinstance(raw, dict):
        logger.warning("[BriefValidator] brief is not a dict (%s); using defaults.", type(raw))
        raw = {}

    cleaned: dict = {}

    try:
        # ── Core identification ──────────────────────────────────────────────
        cleaned["topic"] = _clean_str(raw.get("topic"), _MAX_TOPIC) or "Research Study"
        cleaned["population"] = _clean_str(raw.get("population"))
        cleaned["dependent_variable"]   = _clean_str(raw.get("dependent_variable"))
        cleaned["independent_variable"] = _clean_str(raw.get("independent_variable"))
        cleaned["control_variables"]    = _clean_str(raw.get("control_variables"))
        # Also accept the singular form used by the frontend wizard
        cleaned["control_variable"]     = _clean_str(raw.get("control_variable") or raw.get("control_variables"))
        # Mediating variable(s): explains HOW the IV affects the DV (e.g. Psychological Safety)
        cleaned["mediating_variable"]   = _clean_str(raw.get("mediating_variable"))
        # Moderating variable(s): changes the STRENGTH of IV → DV (e.g. Leadership Support)
        cleaned["moderating_variable"]  = _clean_str(raw.get("moderating_variable"))
        cleaned["study_context"]        = _clean_str(raw.get("study_context"))
        cleaned["research_gap"]         = _clean_str(raw.get("research_gap"))
        cleaned["theoretical_framework"]= _clean_str(raw.get("theoretical_framework"))
        # Rich narrative context for AI-generated reports (all optional)
        cleaned["research_background"]  = _clean_str(raw.get("research_background"))
        cleaned["problem_statement"]    = _clean_str(raw.get("problem_statement"))
        cleaned["study_aim"]            = _clean_str(raw.get("study_aim"))

        # ── Lists ────────────────────────────────────────────────────────────
        # Golden Rule: Research Questions come FIRST — they drive all test selection
        # RQ → Outcome → Predictor → Variable Type → Study Design → Groups → Assumptions → Test → Effect Size → Interpretation
        cleaned["research_questions"] = _clean_list_of_strings(
            raw.get("research_questions"), _MAX_HYPOTHESIS_LEN, _MAX_OBJECTIVES)
        cleaned["objectives"]  = _clean_list_of_strings(
            raw.get("objectives"), _MAX_HYPOTHESIS_LEN, _MAX_OBJECTIVES)
        cleaned["hypotheses"]  = _clean_list_of_strings(
            raw.get("hypotheses"), _MAX_HYPOTHESIS_LEN, _MAX_HYPOTHESES)
        cleaned["keywords"]    = _clean_list_of_strings(
            raw.get("keywords"), 80, _MAX_KEYWORDS)

        # Ensure at least one objective exists so prompts are not empty
        if not cleaned["objectives"] and cleaned["topic"]:
            cleaned["objectives"] = [f"To investigate {cleaned['topic'][:120]}"]

        # ── Numeric parameters ───────────────────────────────────────────────
        cleaned["significance_level"] = _clamp_float(
            raw.get("significance_level"), *_VALID_SIG_LEVELS, _DEFAULT_SIG)
        cleaned["sample_size"] = _clamp_int(raw.get("sample_size"), 1, 1_000_000, 0)
        cleaned["n_cases"]     = _clamp_int(raw.get("n_cases"), 1, 1000, 1)

        # ── Categorical / enum fields ────────────────────────────────────────
        raw_report = str(raw.get("report_type", "chapter4")).strip().lower()
        cleaned["report_type"] = raw_report if raw_report in _VALID_REPORT_TYPES else "chapter4"

        raw_tradition = str(raw.get("academic_tradition", "standard")).strip().lower()
        cleaned["academic_tradition"] = raw_tradition if raw_tradition in _VALID_TRADITIONS else "standard"

        raw_missing = str(raw.get("missing_strategy", "auto")).strip().lower()
        cleaned["missing_strategy"] = raw_missing if raw_missing in _VALID_MISSING else "auto"

        # ── User class (REQUIRED — determines Claude token budget) ───────────
        raw_class = str(raw.get("user_class", "")).strip().lower()
        if not raw_class or raw_class not in _VALID_USER_CLASSES:
            logger.warning(
                "[BriefValidator] user_class=%r is not valid. "
                "Must be one of: %s. Defaulting to 'bsc'.",
                raw_class, ", ".join(sorted(_VALID_USER_CLASSES))
            )
            raw_class = "bsc"
        cleaned["user_class"] = raw_class

        # ── Research Design (required — determines test family constraints) ──
        raw_design = str(raw.get("research_design", "")).strip().lower()
        cleaned["research_design"] = raw_design if raw_design in _VALID_RESEARCH_DESIGNS else ""

        # ── Variable Scale Types — dict of {variable_name: scale_type} ───────
        raw_scales = raw.get("variable_scales") or {}
        if isinstance(raw_scales, dict):
            cleaned["variable_scales"] = {
                str(k)[:100].strip(): str(v).strip().lower()
                for k, v in raw_scales.items()
                if str(v).strip().lower() in _VALID_SCALE_TYPES
            }
        else:
            cleaned["variable_scales"] = {}

        # ── Likert Constructs — explicit scale definitions ────────────────────
        raw_constructs = raw.get("likert_constructs") or []
        if isinstance(raw_constructs, list):
            cleaned["likert_constructs"] = [
                {
                    "name":    str(c.get("name", ""))[:100].strip(),
                    "columns": [
                        str(col)[:100].strip()
                        for col in (c.get("columns") or [])
                        if col and str(col).strip()
                    ][:20],  # cap at 20 columns per construct
                }
                for c in raw_constructs
                if isinstance(c, dict)
                   and c.get("name", "").strip()
                   and c.get("columns")
            ]
        else:
            cleaned["likert_constructs"] = []


        raw_types = raw.get("study_types", ["quantitative"])
        if isinstance(raw_types, str):
            raw_types = [raw_types]
        cleaned["study_types"] = [
            t for t in (str(x).strip().lower() for x in (raw_types or []))
            if t in _VALID_STUDY_TYPES
        ] or ["quantitative"]

        # ── Boolean flags ────────────────────────────────────────────────────
        cleaned["has_pretest_posttest"] = bool(raw.get("has_pretest_posttest", False))
        cleaned["has_control_group"]    = bool(raw.get("has_control_group", False))

        cleaned["case_analysis_approach"] = (
            "within" if str(raw.get("case_analysis_approach", "within")).strip()
            not in ("within", "cross") else str(raw.get("case_analysis_approach")).strip()
        )

        # ── Formatting / citation ─────────────────────────────────────────────
        fmt = raw.get("formatting_options") or {}
        if not isinstance(fmt, dict):
            fmt = {}
        cleaned["formatting_options"] = {
            "citation_style": _clean_str(fmt.get("citation_style", "APA 7th Edition"), 60),
            "font_name":      _clean_str(fmt.get("font_name", "Times New Roman"), 60),
            "font_size":      _clamp_int(fmt.get("font_size", 12), 8, 18, 12),
            "line_spacing":   _clamp_float(fmt.get("line_spacing", 2.0), 1.0, 3.0, 2.0),
            "margin_inches":  _clamp_float(fmt.get("margin_inches", 1.0), 0.5, 2.0, 1.0),
        }

        # ── Pass-through safe fields (already validated upstream) ────────────
        for passthrough in (
            "auto_viz", "selected_viz", "auto_tables", "selected_tables",
            "auto_select_techniques", "selected_techniques",
            "qual_coding_approach", "qual_min_themes",
            # Variable Advisor fields
            "grouping_variables", "variable_coding",
        ):
            cleaned[passthrough] = raw.get(passthrough)

        logger.debug("[BriefValidator] Brief validated OK. topic=%r study_types=%s",
                     cleaned["topic"], cleaned["study_types"])

    except Exception as exc:
        logger.error("[BriefValidator] Unexpected validation error: %s", exc, exc_info=True)
        # Last resort: return a minimal safe brief so pipeline can still run
        cleaned.setdefault("topic", "Research Study")
        cleaned.setdefault("research_questions", [])
        cleaned.setdefault("objectives", ["To analyse survey data"])
        cleaned.setdefault("hypotheses", [])
        cleaned.setdefault("significance_level", 0.05)
        cleaned.setdefault("study_types", ["quantitative"])
        cleaned.setdefault("report_type", "chapter4")
        cleaned.setdefault("missing_strategy", "auto")

    return cleaned


def brief_is_minimal(brief: dict) -> bool:
    """Return True if the brief has the absolute minimum needed for analysis."""
    return bool(brief.get("topic"))
