"""
composite_means.py
Auto-computes composite mean columns for Likert scale constructs.
Research standard: use scale means (job_performance_mean) not individual items.
"""
from __future__ import annotations
import re, numpy as np, pandas as pd
from collections import defaultdict
from typing import Optional

def _is_likert_item(series: pd.Series, max_unique: int = 9) -> bool:
    try:
        s = pd.to_numeric(series.dropna(), errors="coerce").dropna()
        if len(s) == 0: return False
        n_unique = s.nunique()
        if n_unique < 2 or n_unique > max_unique: return False
        vmin, vmax = s.min(), s.max()
        if vmin < 0 or vmax > 10: return False
        if not np.allclose(s, s.round(0), atol=0.01): return False
        return True
    except Exception:
        return False

_ITEM_SUFFIX_RE = re.compile(r'^(.+?)_(\d+)$')

def _detect_groups(df: pd.DataFrame) -> dict:
    groups: dict = defaultdict(list)
    for col in df.columns:
        m = _ITEM_SUFFIX_RE.match(col)
        if not m: continue
        prefix, num = m.group(1), int(m.group(2))
        if _is_likert_item(df[col]):
            groups[prefix].append((num, col))
    result = {}
    for prefix, items in groups.items():
        if len(items) < 2: continue
        result[prefix] = [col for _, col in sorted(items)]
    return result

def compute_composite_means(df: pd.DataFrame, brief: dict, data_dict: Optional[dict] = None):
    """
    Compute composite mean columns for all detected Likert item groups.
    Returns: (df, brief, log_list)
    """
    log = []
    groups = _detect_groups(df)
    if not groups:
        return df, brief, log

    created = {}

    for prefix, item_cols in groups.items():
        mean_col = f"{prefix}_mean"
        if mean_col in df.columns:
            created[mean_col] = item_cols
            log.append(f"[Composite] '{mean_col}' already exists — kept ({len(item_cols)} items)")
            continue
        min_count = max(1, len(item_cols) // 2)
        numeric_items = df[item_cols].apply(pd.to_numeric, errors="coerce")
        df[mean_col] = numeric_items.mean(axis=1, skipna=True)
        valid_count = numeric_items.notna().sum(axis=1)
        df.loc[valid_count < min_count, mean_col] = np.nan
        created[mean_col] = item_cols
        log.append(f"[Composite] Created '{mean_col}' = mean({', '.join(item_cols)}) [{len(item_cols)} items]")

    if not created:
        return df, brief, log

    # Update brief: resolve variable references to composite mean names
    ROLE_FIELDS = [
        "dependent_variable", "independent_variable", "mediating_variable",
        "moderating_variable", "control_variable", "covariate_variable",
        "group_variable", "exclude_variable",
        "dv_column", "iv_column", "mediating_column", "moderating_column",
    ]
    all_mean_cols = set(created.keys())
    all_df_cols   = set(df.columns)

    def _resolve(name: str) -> str:
        name = name.strip()
        if name in all_mean_cols or (name.endswith("_mean") and name in all_df_cols):
            return name
        candidate = f"{name}_mean"
        if candidate in all_mean_cols:
            return candidate
        return name

    for field in ROLE_FIELDS:
        raw = brief.get(field, "") or ""
        if not raw: continue
        parts    = [v.strip() for v in raw.split(",") if v.strip()]
        resolved = [_resolve(p) for p in parts]
        if resolved != parts:
            brief[field] = ", ".join(resolved)
            log.append(f"[Composite] Brief '{field}': {parts} -> {resolved}")

    # Update data_dict with composite column metadata
    if data_dict is not None:
        ratio_vars = data_dict.get("ratio_vars", []) or []
        for mean_col in created:
            if mean_col not in ratio_vars:
                ratio_vars.append(mean_col)
        data_dict["ratio_vars"] = ratio_vars

        existing_vars = data_dict.get("variables", []) or []
        existing_names = {v.get("clean_name") for v in existing_vars}
        for mean_col, items in created.items():
            if mean_col not in existing_names:
                existing_vars.append({
                    "clean_name": mean_col, "original_name": mean_col,
                    "scale": "ratio", "role": "", "inferred_by": "composite_mean",
                    "n_unique": int(df[mean_col].nunique()), "composite_items": items,
                })
        data_dict["variables"] = existing_vars
        data_dict["composite_means"] = {k: v for k, v in created.items()}

    log.append(f"[Composite] Total composites: {len(created)}")
    return df, brief, log
