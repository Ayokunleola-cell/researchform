"""
decode/transforms/missing_handler.py
Comprehensive missing value analysis with per-column strategy recommendations.
"""


def handle_missing(df, warnings):
    """
    Analyse missing values across all columns.
    Returns a per-column stats dict and appends diagnostic warnings.

    Strategy decision tree:
        0%         → none_needed
        <5%        → median_impute (numeric) / mode_impute (categorical)
        5–14%      → knn_impute (numeric) / mode_impute (categorical)
        15–39%     → mice_impute (numeric) / indicator_flag (categorical)
        40–59%     → indicator_flag (add binary missingness column before imputing)
        >=60%      → drop_column recommendation
        time-series detected → ffill/bfill

    MNAR risk: flagged when pct>20% + low cardinality + numeric
               (the missingness itself may carry information)
    """
    try:
        import pandas as pd
    except ImportError:
        pass

    missing_stats = {}

    for col in df.columns:
        n_miss = int(df[col].isna().sum())
        pct = round(n_miss / len(df) * 100, 1) if len(df) > 0 else 0.0
        n_uniq = df[col].nunique()
        is_num = _is_numeric(df, col)
        is_dt = _is_datetime(df, col)

        # ── Strategy selection ────────────────────────────────────────
        if is_dt and pct > 0:
            strategy = "ffill"
        elif pct == 0:
            strategy = "none_needed"
        elif pct < 5:
            strategy = "median_impute" if is_num else "mode_impute"
        elif pct < 15:
            strategy = "knn_impute" if is_num else "mode_impute"
        elif pct < 40:
            strategy = "mice_impute" if is_num else "indicator_flag"
        elif pct < 60:
            strategy = "indicator_flag"
        else:
            strategy = "drop_column"

        # ── MNAR risk ─────────────────────────────────────────────────
        mnar_risk = pct > 20 and n_uniq <= 5 and is_num

        missing_stats[col] = {
            "n_missing": n_miss,
            "pct_missing": pct,
            "recommended_strategy": strategy,
            "mnar_risk": mnar_risk,
        }

        # ── Emit warnings ─────────────────────────────────────────────
        if pct == 0:
            pass  # No warning needed

        elif strategy == "drop_column":
            warnings.append({
                "severity": "error",
                "variable": col,
                "message": f"Critically high missing data: {pct}% of values are missing",
                "suggestion": f"Consider dropping this column or applying indicator_flag strategy",
            })

        elif pct >= 40:
            warnings.append({
                "severity": "warning",
                "variable": col,
                "message": f"Very high missing data: {pct}% — missingness itself may carry information",
                "suggestion": f"Add a binary indicator column ({col}_missing=1) before imputing",
            })

        elif pct > 20:
            warnings.append({
                "severity": "warning",
                "variable": col,
                "message": f"High missing data: {pct}% of values are missing",
                "suggestion": f"Recommended: {strategy}",
            })

        elif pct > 5:
            warnings.append({
                "severity": "info",
                "variable": col,
                "message": f"Moderate missing data: {pct}% of values are missing",
                "suggestion": f"Recommended: {strategy}",
            })

        if mnar_risk:
            warnings.append({
                "severity": "warning",
                "variable": col,
                "message": f"Possible MNAR pattern in '{col}' — missingness may not be random",
                "suggestion": "Create a missingness indicator flag before imputing to preserve this signal",
            })

    return df, missing_stats


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_numeric(df, col):
    try:
        import pandas as pd
        return pd.api.types.is_numeric_dtype(df[col])
    except Exception:
        return False


def _is_datetime(df, col):
    try:
        import pandas as pd
        return pd.api.types.is_datetime64_any_dtype(df[col])
    except Exception:
        return False

