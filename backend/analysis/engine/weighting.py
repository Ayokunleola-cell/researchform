# backend/analysis/engine/weighting.py
"""
Survey weighting and MICE/KNN imputation helpers for the statistical engine.

_apply_survey_weights: Expands rows proportionally by case weight column.
    Works with ALL existing tests transparently - they see a properly
    weighted DataFrame without needing modification.

_apply_imputation: MICE or KNN imputation for numeric columns.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def _apply_survey_weights(df: pd.DataFrame, weight_col: str):
    """
    Apply survey case weights by row-replication (proportional expansion).

    Strategy:
    1. Normalize weights so they sum to the original N
    2. Compute integer repeat counts (min 1)
    3. Replicate rows, drop the weight column from the expanded frame
    4. Cap expanded N at 5000 to avoid memory issues

    Returns: (weighted_df, meta_dict)
    """
    try:
        w = pd.to_numeric(df[weight_col], errors='coerce').fillna(1.0)
        w = w.clip(lower=0.001)                    # guard against zero/negative weights
        unweighted_n = len(df)
        effective_n  = float((w**2).sum() / (w.sum()**2) * unweighted_n) if w.sum() > 0 else unweighted_n

        # Normalize weights to sum = unweighted_n, then scale to max 5000 total rows
        w_norm = w / w.sum() * unweighted_n
        scale  = min(1.0, 5000 / max(w_norm.sum(), 1))
        counts = np.maximum(1, np.round(w_norm * scale).astype(int))

        # Expand rows
        rows = []
        for i, cnt in enumerate(counts):
            rows.extend([df.iloc[i]] * cnt)
        expanded = pd.DataFrame(rows).reset_index(drop=True)

        # Drop the weight column from analysis frame
        expanded = expanded.drop(columns=[weight_col], errors='ignore')

        meta = {
            "weight_column":  weight_col,
            "unweighted_n":   unweighted_n,
            "effective_n":    round(effective_n, 1),
            "expanded_n":     len(expanded),
            "min_weight":     round(float(w.min()), 4),
            "max_weight":     round(float(w.max()), 4),
            "mean_weight":    round(float(w.mean()), 4),
        }
        logger.info(f"[Weighting] Expanded {unweighted_n} -> {len(expanded)} rows using '{weight_col}'")
        return expanded, meta

    except Exception as e:
        logger.warning(f"[Weighting] Failed to apply survey weights: {e}")
        return df, None


def _apply_imputation(df: pd.DataFrame, method: str = "mice"):
    """
    Impute missing values in all numeric columns using MICE or KNN.

    Returns: (imputed_df, meta_dict)
    """
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    missing_mask = df[num_cols].isnull()
    cols_with_missing = [c for c in num_cols if missing_mask[c].any()]
    total_missing = int(missing_mask.sum().sum())

    if not cols_with_missing or total_missing == 0:
        return df, {"method": method, "cols_imputed": 0, "cells_imputed": 0}

    try:
        df_out = df.copy()

        if method == "mice":
            # Use IterativeImputer (MICE equivalent in sklearn)
            try:
                from sklearn.experimental import enable_iterative_imputer  # noqa
                from sklearn.impute import IterativeImputer
                imp = IterativeImputer(max_iter=10, random_state=42, verbose=0)
                df_out[num_cols] = imp.fit_transform(df_out[num_cols])
                method_label = "MICE (Multivariate Imputation by Chained Equations)"
            except ImportError:
                # Fallback to KNN if iterative imputer unavailable
                from sklearn.impute import KNNImputer
                imp = KNNImputer(n_neighbors=5)
                df_out[num_cols] = imp.fit_transform(df_out[num_cols])
                method_label = "KNN Imputation (MICE fallback - sklearn IterativeImputer not available)"

        elif method == "knn":
            from sklearn.impute import KNNImputer
            imp = KNNImputer(n_neighbors=5, weights="distance")
            df_out[num_cols] = imp.fit_transform(df_out[num_cols])
            method_label = "KNN Imputation (k=5, distance-weighted)"

        else:
            return df, {"method": "none", "cols_imputed": 0, "cells_imputed": 0}

        meta = {
            "method":        method_label,
            "cols_imputed":  len(cols_with_missing),
            "cells_imputed": total_missing,
            "columns":       cols_with_missing,
        }
        logger.info(f"[Imputation] {method_label}: {total_missing} cells across {len(cols_with_missing)} columns")
        return df_out, meta

    except Exception as e:
        logger.warning(f"[Imputation] Failed ({method}): {e}. Returning original df.")
        return df, {"method": f"{method} (FAILED: {e})", "cols_imputed": 0, "cells_imputed": 0}
