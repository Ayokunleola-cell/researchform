import re
def clean_columns(df, meta):
    import pandas as pd
    col_map = {}
    seen = {}
    new_cols = []
    for col in df.columns:
        c = str(col).strip().lower()
        c = re.sub(r"[^a-z0-9_]", "_", c)
        c = re.sub(r"_+", "_", c).strip("_")
        if not c: c = "var"
        c = c[:40]
        if c in seen:
            seen[c] += 1
            c = f"{c}_{seen[c]}"
        else:
            seen[c] = 0
        col_map[c] = str(col)
        new_cols.append(c)
    df.columns = new_cols
    return df, col_map
