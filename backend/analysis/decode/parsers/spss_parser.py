# SPSS .sav parser
def parse_spss(path: str):
    import pyreadstat, pandas as pd
    df, meta = pyreadstat.read_sav(path, apply_value_formats=False)
    m = {
        "value_labels": meta.variable_value_labels,
        "column_labels": meta.column_labels,
        "measurement_levels": meta.readstat_variable_types,
        "missing_ranges": getattr(meta, "missing_ranges", {}),
        "source": "spss",
    }
    return df, m
