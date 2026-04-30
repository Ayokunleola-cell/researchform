def resolve_labels(df, meta, col_map):
    value_labels = {}
    vl = meta.get("value_labels", {})
    reverse_map = {v: k for k, v in col_map.items()}
    for orig_col, labels in vl.items():
        clean = reverse_map.get(orig_col)
        if clean and clean in df.columns:
            value_labels[clean] = {str(k): str(v) for k, v in labels.items()}
    return df, value_labels
