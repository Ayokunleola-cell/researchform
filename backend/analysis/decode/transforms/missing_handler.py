def handle_missing(df, warnings):
    missing_stats = {}
    for col in df.columns:
        n_miss = int(df[col].isna().sum())
        pct = round(n_miss / len(df) * 100, 1) if len(df) > 0 else 0.0
        missing_stats[col] = {"n_missing": n_miss, "pct_missing": pct}
        if pct > 20:
            warnings.append({"severity":"warning","variable":col,"message":f"High missing data: {pct}% of values are missing","suggestion":"Consider drop_rows or mean_impute strategy"})
    return df, missing_stats
