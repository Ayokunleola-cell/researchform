# CSV parser with encoding sniffing
def parse_csv(path: str):
    import pandas as pd, chardet
    with open(path, "rb") as f:
        enc = chardet.detect(f.read(50000)).get("encoding", "utf-8") or "utf-8"
    for sep in [",", "\t", ";", "|"]:
        try:
            df = pd.read_csv(path, encoding=enc, sep=sep, on_bad_lines="skip")
            if df.shape[1] > 1:
                break
        except Exception:
            continue
    # Drop Google Forms Timestamp column if present
    if "Timestamp" in df.columns:
        df.drop(columns=["Timestamp"], inplace=True, errors="ignore")
    return df, {"source": "csv", "value_labels": {}, "column_labels": {}, "measurement_levels": {}}
