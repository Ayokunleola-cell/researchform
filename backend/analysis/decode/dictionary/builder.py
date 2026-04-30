from datetime import datetime
def build_dictionary(df, col_map, value_labels, levels, missing_stats, meta, source_type,
                     source_filename=None, survey_id=None, warnings=None):
    variables = []
    for col in df.columns:
        s = df[col]
        ms = missing_stats.get(col, {})
        n_total = len(s)
        n_missing = ms.get("n_missing", 0)
        n_valid = n_total - n_missing
        level = levels.get(col, "nominal")
        col_labels = meta.get("column_labels", {})
        orig = col_map.get(col, col)
        lbl = col_labels.get(orig) or col_labels.get(col) or col
        uniques = s.dropna().unique().tolist()[:20]
        v = {
            "original_name": orig, "clean_name": col, "label": str(lbl)[:100],
            "dtype": str(s.dtype), "measurement_level": level,
            "inferred_by": "spss_metadata" if orig in meta.get("measurement_levels",{}) else "heuristic",
            "n_total": n_total, "n_valid": n_valid, "n_missing": n_missing,
            "pct_missing": ms.get("pct_missing", 0.0),
            "value_labels": value_labels.get(col),
            "unique_values": uniques if len(uniques) <= 20 else None,
            "value_min": float(s.min()) if str(s.dtype) in ("float64","int64") else None,
            "value_max": float(s.max()) if str(s.dtype) in ("float64","int64") else None,
            "value_mean": float(s.mean()) if str(s.dtype) in ("float64","int64") else None,
            "sample_values": s.dropna().head(5).tolist(),
            "high_missing": ms.get("pct_missing", 0) > 20,
            "level_uncertain": level in ("ordinal","nominal") and str(s.dtype) in ("float64","int64"),
            "has_value_labels": col in value_labels,
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

    return {
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
