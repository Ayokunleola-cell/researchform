def infer_levels(df, meta, col_map, warnings):
    levels = {}
    spss_levels = meta.get("measurement_levels", {})
    db_levels = meta.get("measurement_levels", {})
    reverse_map = {v: k for k, v in col_map.items()}

    for col in df.columns:
        # Priority 1: SPSS metadata
        orig = col_map.get(col, col)
        if orig in spss_levels and spss_levels[orig]:
            l = str(spss_levels[orig]).lower()
            if l in ("nominal", "ordinal", "interval", "ratio", "scale"):
                levels[col] = "ratio" if l == "scale" else l
                continue
        # Priority 2: DB measurement level (with alias normalization for robustness)
        if col in db_levels and db_levels[col]:
            raw = str(db_levels[col]).strip().lower()
            _ML_NORM = {
                # continuous / numeric variants
                "continuous": "ratio",    "numeric": "ratio",      "quantitative": "ratio",
                "scale": "ratio",         "continuous_scale": "ratio",
                # categorical / qualitative
                "categorical": "nominal", "qualitative": "nominal", "binary": "nominal",
                "dichotomous": "nominal", "dummy": "nominal",      "discrete": "nominal",
                # ranked / ordered
                "ranked": "ordinal",      "rank": "ordinal",        "likert": "ordinal",
                "ordered": "ordinal",     "ordinal_scale": "ordinal",
            }
            _VALID = {"nominal", "ordinal", "interval", "ratio"}
            levels[col] = _ML_NORM.get(raw, raw if raw in _VALID else "nominal")
            continue

        # Priority 3: Heuristics
        s = df[col]
        n_unique = s.nunique()
        dtype = str(s.dtype)
        if "float" in dtype or "int" in dtype:
            if n_unique <= 7:
                levels[col] = "ordinal"
                warnings.append({"severity":"info","variable":col,"message":f"Assumed ordinal ({n_unique} unique numeric values)","suggestion":"Verify measurement level"})
            elif n_unique <= 2:
                levels[col] = "nominal"
            else:
                levels[col] = "ratio"
        elif "object" in dtype or "category" in dtype:
            non_nulls = s.dropna()
            if len(non_nulls) > 0 and n_unique > 5:
                # Check for open-ended text (high variance and long strings)
                avg_len = non_nulls.astype(str).str.len().mean()
                if avg_len > 30 and (n_unique / len(non_nulls) > 0.5):
                    levels[col] = "text"
                else:
                    levels[col] = "ordinal" if n_unique <= 10 else "nominal"
            else:
                levels[col] = "ordinal" if n_unique <= 10 else "nominal"
        else:
            levels[col] = "nominal"
    return levels
