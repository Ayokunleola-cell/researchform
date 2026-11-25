import re

# Column name patterns that strongly indicate a particular measurement level
_NAME_RATIO = re.compile(
    r"(^age$|^years?|^income|^salary|score$|_score$|gpa|duration|hours|count|"
    r"composite|index$|total$|amount|weight|height|bmi|rate|distance|time_)",
    re.IGNORECASE,
)
_NAME_BINARY = re.compile(
    r"(^gender$|^sex$|^is_|^has_|_flag$|^yes_no|^binary|^dummy|^employed$)",
    re.IGNORECASE,
)
_NAME_NOMINAL = re.compile(
    r"(department|dept|profession|faculty|hospital|site|region|country|city|"
    r"shift|type$|_type$|category|group$|_group$|employment|contract|mode$|"
    r"model$|status$|_status$|sector|industry|ethnicity|race|religion|marital)",
    re.IGNORECASE,
)
_NAME_LIKERT = re.compile(
    r"(^q\d+_|_q\d+$|likert|satisfaction|agreement|attitude|perception|opinion|"
    r"belief|confidence|motivation|engagement|support|trust|commitment|loyalty)",
    re.IGNORECASE,
)
_NAME_ID = re.compile(r"(^id$|_id$|respondent|participant|subject|uuid|code$)", re.IGNORECASE)


def _infer_single(col: str, s, spss_level: str = None) -> dict:
    """
    Returns {measurement_level, scale_subtype, inferred_by} for one column.
    Priority:
      1. SPSS / DB metadata (authoritative)
      2. Column name heuristics (high confidence)
      3. Numeric dtype + unique-count rules
      4. Object/string dtype fallback
    """
    name = col.lower()
    n_unique = s.nunique()
    dtype = str(s.dtype)

    # ── Priority 1: SPSS / explicit metadata ────────────────────────────────
    if spss_level:
        lv = spss_level.strip().lower()
        _P1_MAP = {
            "scale": ("ratio", None), "continuous": ("ratio", None),
            "ratio": ("ratio", None), "interval": ("interval", None),
            "ordinal": ("ordinal", None), "nominal": ("nominal", None),
        }
        if lv in _P1_MAP:
            ml, sub = _P1_MAP[lv]
            # Refine ordinal to Likert if name/unique count suggests it
            if ml == "ordinal" and n_unique <= 7:
                sub = "likert_5" if n_unique <= 5 else "likert_7"
            return {"measurement_level": ml, "scale_subtype": sub, "inferred_by": "spss_metadata"}

    # ── Priority 2: Column name heuristics ──────────────────────────────────
    if _NAME_ID.search(name):
        return {"measurement_level": "nominal", "scale_subtype": "id", "inferred_by": "name_heuristic"}

    if _NAME_BINARY.search(name) or n_unique <= 2:
        return {"measurement_level": "nominal", "scale_subtype": "binary", "inferred_by": "name_heuristic"}

    if _NAME_RATIO.search(name):
        return {"measurement_level": "ratio", "scale_subtype": None, "inferred_by": "name_heuristic"}

    if _NAME_NOMINAL.search(name):
        return {"measurement_level": "nominal", "scale_subtype": "categorical", "inferred_by": "name_heuristic"}

    if _NAME_LIKERT.search(name):
        sub = "likert_5" if n_unique <= 5 else "likert_7" if n_unique <= 7 else "ordinal"
        return {"measurement_level": "ordinal", "scale_subtype": sub, "inferred_by": "name_heuristic"}

    # ── Priority 3: Numeric dtype + unique count ─────────────────────────────
    if "float" in dtype or "int" in dtype:
        if n_unique <= 2:
            return {"measurement_level": "nominal", "scale_subtype": "binary", "inferred_by": "numeric_unique"}
        if n_unique <= 5:
            return {"measurement_level": "ordinal", "scale_subtype": "likert_5", "inferred_by": "numeric_unique"}
        if n_unique <= 7:
            return {"measurement_level": "ordinal", "scale_subtype": "likert_7", "inferred_by": "numeric_unique"}
        # Check if it looks like year (4-digit integer)
        try:
            sample = s.dropna().head(10)
            if all(1900 <= int(x) <= 2100 for x in sample):
                return {"measurement_level": "ordinal", "scale_subtype": "year", "inferred_by": "numeric_unique"}
        except Exception:
            pass
        return {"measurement_level": "ratio", "scale_subtype": None, "inferred_by": "numeric_unique"}

    # ── Priority 4: Object / string / category dtype ─────────────────────────
    if "object" in dtype or "category" in dtype or "str" in dtype:
        non_nulls = s.dropna()
        if len(non_nulls) > 0:
            avg_len = non_nulls.astype(str).str.len().mean()
            # Open-ended text (long strings, high cardinality)
            if avg_len > 40 and (n_unique / max(len(non_nulls), 1) > 0.4):
                return {"measurement_level": "text", "scale_subtype": "open_ended", "inferred_by": "string_analysis"}
        # Short categorical strings → nominal
        return {"measurement_level": "nominal", "scale_subtype": "categorical", "inferred_by": "dtype_fallback"}

    return {"measurement_level": "nominal", "scale_subtype": None, "inferred_by": "default_fallback"}


def infer_levels(df, meta, col_map, warnings):
    """
    Main entry point — returns {col: measurement_level} for backward compatibility.
    Also stores extended info in meta['_inferred_detail'] for use by builder.py.
    """
    levels = {}
    detail = {}  # col → {measurement_level, scale_subtype, inferred_by}
    spss_levels = meta.get("measurement_levels", {})

    for col in df.columns:
        orig = col_map.get(col, col)
        spss_level = None
        if orig in spss_levels and spss_levels[orig]:
            spss_level = str(spss_levels[orig])

        result = _infer_single(col, df[col], spss_level)
        levels[col] = result["measurement_level"]
        detail[col] = result

        # Warn when uncertain (numeric column with small unique count)
        if result["inferred_by"] == "numeric_unique" and result["measurement_level"] == "ordinal":
            n_u = df[col].nunique()
            warnings.append({
                "severity": "info",
                "variable": col,
                "message": f"Assumed ordinal/Likert ({n_u} unique numeric values — subtype: {result.get('scale_subtype', '?')})",
                "suggestion": "Confirm measurement level in Variable Scale Types panel",
            })

    # Store detail for builder
    meta["_inferred_detail"] = detail
    return levels
