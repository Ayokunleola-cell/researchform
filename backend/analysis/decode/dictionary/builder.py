from datetime import datetime, date, time
import math

def _clean_key(k):
    if k is None:
        return "null"
    if isinstance(k, (datetime, date, time)):
        return k.isoformat()
    type_name = type(k).__name__
    if type_name in ("Timestamp", "Timedelta", "Period"):
        return str(k)
    if hasattr(k, "item") and callable(k.item):
        try:
            return str(k.item())
        except Exception:
            pass
    return str(k)


def to_json_serializable(val):
    """
    Recursively sanitize any Python/Pandas/NumPy object so that standard json.dumps()
    never fails with TypeError (e.g. Timestamp, datetime, np.int64, np.float64, NaN, etc.).
    """
    if val is None:
        return None
    if isinstance(val, (datetime, date, time)):
        return val.isoformat()
    # Check for pandas/numpy datetime/timestamp/timedelta
    type_name = type(val).__name__
    if type_name in ("Timestamp", "Timedelta", "Period"):
        return str(val)
    if hasattr(val, "isoformat") and callable(val.isoformat):
        try:
            return val.isoformat()
        except Exception:
            return str(val)
    # Check for float NaN / Inf
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    # Check for integer types
    if isinstance(val, int) and not isinstance(val, bool):
        return int(val)
    # NumPy scalar types
    if hasattr(val, "item") and callable(val.item):
        try:
            native = val.item()
            if isinstance(native, float) and (math.isnan(native) or math.isinf(native)):
                return None
            if isinstance(native, (datetime, date, time)):
                return native.isoformat()
            return native
        except Exception:
            pass
    # Pandas DataFrame / Series / Index
    if hasattr(val, "to_dict") and callable(val.to_dict):
        try:
            return to_json_serializable(val.to_dict())
        except Exception:
            pass
    if hasattr(val, "tolist") and callable(val.tolist):
        try:
            return to_json_serializable(val.tolist())
        except Exception:
            pass
    if isinstance(val, dict):
        return {_clean_key(k): to_json_serializable(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [to_json_serializable(x) for x in val]
    return val


def build_dictionary(df, col_map, value_labels, levels, missing_stats, meta, source_type,
                     source_filename=None, survey_id=None, warnings=None):
    variables = []
    for col in df.columns:
        s = df[col]
        ms = missing_stats.get(col, {})
        n_total = len(s)
        n_missing = int(ms.get("n_missing", 0))
        n_valid = n_total - n_missing
        level = levels.get(col, "nominal")
        col_labels = meta.get("column_labels", {})
        orig = col_map.get(col, col)
        lbl = col_labels.get(orig) or col_labels.get(col) or col

        # Clean unique and sample values through to_json_serializable
        raw_uniques = s.dropna().unique().tolist()[:20]
        uniques = [to_json_serializable(u) for u in raw_uniques]

        raw_samples = s.dropna().head(5).tolist()
        samples = [to_json_serializable(sm) for sm in raw_samples]

        # Numeric stats with safe bounds
        val_min = None
        val_max = None
        val_mean = None
        if str(s.dtype) in ("float64", "int64", "float32", "int32"):
            try:
                min_v = s.min()
                if min_v is not None and not (isinstance(min_v, float) and math.isnan(min_v)):
                    val_min = float(min_v)
            except Exception:
                pass
            try:
                max_v = s.max()
                if max_v is not None and not (isinstance(max_v, float) and math.isnan(max_v)):
                    val_max = float(max_v)
            except Exception:
                pass
            try:
                mean_v = s.mean()
                if mean_v is not None and not (isinstance(mean_v, float) and math.isnan(mean_v)):
                    val_mean = float(mean_v)
            except Exception:
                pass

        v = {
            "original_name": str(orig), "clean_name": str(col), "label": str(lbl)[:100],
            "dtype": str(s.dtype), "measurement_level": level,
            "inferred_by": "spss_metadata" if orig in meta.get("measurement_levels", {}) else "heuristic",
            "n_total": n_total, "n_valid": n_valid, "n_missing": n_missing,
            "pct_missing": float(ms.get("pct_missing", 0.0)),
            "value_labels": to_json_serializable(value_labels.get(col)),
            "unique_values": uniques if len(uniques) <= 20 else None,
            "value_min": val_min,
            "value_max": val_max,
            "value_mean": val_mean,
            "sample_values": samples,
            "high_missing": bool(ms.get("pct_missing", 0) > 20),
            "level_uncertain": bool(level in ("ordinal", "nominal") and str(s.dtype) in ("float64", "int64")),
            "has_value_labels": bool(col in value_labels),
        }
        variables.append(v)

    nominal  = [v["clean_name"] for v in variables if v["measurement_level"] == "nominal"]
    ordinal  = [v["clean_name"] for v in variables if v["measurement_level"] == "ordinal"]
    interval = [v["clean_name"] for v in variables if v["measurement_level"] == "interval"]
    ratio    = [v["clean_name"] for v in variables if v["measurement_level"] == "ratio"]

    # Build LLM context string
    llm_lines = [f"Dataset: {source_type} | {len(df)} rows | {len(df.columns)} variables"]
    for v in variables:
        llm_lines.append(f"  {v['clean_name']} ({v['measurement_level']}) label={v['label'][:50]} dtype={v['dtype']} n_valid={v['n_valid']}")
    llm_context = "\n".join(llm_lines)

    result_dict = {
        "source_type": source_type, "source_filename": source_filename, "survey_id": survey_id,
        "decoded_at": datetime.utcnow().isoformat(),
        "n_rows": len(df), "n_columns": len(df.columns),
        "n_complete_rows": int(df.dropna().shape[0]),
        "variables": variables,
        "nominal_vars": nominal, "ordinal_vars": ordinal,
        "interval_vars": interval, "ratio_vars": ratio,
        "warnings": warnings or [],
        "llm_context": llm_context,
    }
    return to_json_serializable(result_dict)
