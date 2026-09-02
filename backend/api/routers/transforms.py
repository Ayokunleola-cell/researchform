"""api/routers/transforms.py — Data transformation endpoint (recode, compute, bin, standardize, dummy, reverse_score)."""
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.deps import get_db, get_current_user
from api.models.database import AnalysisJob
from config import settings

router = APIRouter(prefix="/api/analysis", tags=["transforms"])


class Operation(BaseModel):
    type: Literal["recode","compute","bin","standardize","dummy","reverse_score"]
    column: Optional[str]       = None
    new_column: Optional[str]   = None
    map: Optional[Dict[str, Any]] = None
    formula: Optional[str]      = None
    items: Optional[List[str]]  = None
    agg: Optional[Literal["mean","sum","min","max"]] = "mean"
    breaks: Optional[List[float]] = None
    labels: Optional[List[str]]   = None
    method: Optional[Literal["zscore","minmax"]] = "zscore"
    reference: Optional[str] = None
    scale_max: Optional[int] = 5


class TransformRequest(BaseModel):
    operations: List[Operation] = Field(..., min_items=1)
    preview_only: bool = False


@router.post("/{job_id}/transform")
async def transform_data(job_id: str, body: TransformRequest,
                         db: AsyncSession = Depends(get_db),
                         user=Depends(get_current_user)):
    """
    Apply data transformations to a job's dataset.
    Returns preview of first 5 rows + transform log.
    """
    import pandas as pd
    import numpy as np

    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Analysis job not found")
    if str(job.user_id) != str(user.id):
        raise HTTPException(403, "Access denied")

    try:
        df = _load_df(str(job.id))
        if df is None or df.empty:
            raise HTTPException(400, "No dataset found for this job")

        applied = []
        errors  = []

        for op in body.operations:
            try:
                if op.type == "recode" and op.column and op.map:
                    df, log = _recode(df, op.column, op.map, op.new_column)
                    applied.append(log)

                elif op.type == "compute":
                    cols = op.items or []
                    agg  = op.agg or "mean"
                    if not cols:
                        errors.append("compute: no items specified")
                        continue
                    new_col = op.new_column or f"{'_'.join(cols[:2])}_{agg}"
                    fns = {"mean": np.nanmean, "sum": np.nansum, "min": np.nanmin, "max": np.nanmax}
                    fn  = fns.get(agg, np.nanmean)
                    df[new_col] = df[cols].apply(lambda r: fn(r.values), axis=1)
                    applied.append({"op": "compute", "new_column": new_col, "items": cols, "agg": agg})

                elif op.type == "reverse_score" and op.column:
                    scale_max = op.scale_max or 5
                    new_col   = op.new_column or f"{op.column}_rev"
                    df[new_col] = scale_max + 1 - df[op.column]
                    applied.append({"op": "reverse_score", "column": op.column,
                                    "new_column": new_col, "scale_max": scale_max})

                elif op.type == "bin" and op.column and op.breaks:
                    new_col = op.new_column or f"{op.column}_grp"
                    lbl = op.labels or [f"G{i+1}" for i in range(len(op.breaks) - 1)]
                    df[new_col] = pd.cut(df[op.column], bins=op.breaks,
                                         labels=lbl, include_lowest=True)
                    applied.append({"op": "bin", "column": op.column,
                                    "new_column": new_col, "breaks": op.breaks})

                elif op.type == "standardize" and op.column:
                    new_col = op.new_column or f"{op.column}_std"
                    if op.method == "zscore":
                        m, s = df[op.column].mean(), df[op.column].std()
                        df[new_col] = (df[op.column] - m) / (s if s != 0 else 1)
                    else:
                        mn, mx = df[op.column].min(), df[op.column].max()
                        df[new_col] = (df[op.column] - mn) / ((mx - mn) if mx != mn else 1)
                    applied.append({"op": "standardize", "column": op.column,
                                    "new_column": new_col, "method": op.method})

                elif op.type == "dummy" and op.column:
                    dummies = pd.get_dummies(df[op.column], prefix=op.column, drop_first=False)
                    if op.reference:
                        ref_col = f"{op.column}_{op.reference}"
                        dummies = dummies.drop(columns=[ref_col], errors="ignore")
                    df = pd.concat([df, dummies.astype(int)], axis=1)
                    applied.append({"op": "dummy", "column": op.column,
                                    "new_columns": list(dummies.columns),
                                    "reference": op.reference})
                else:
                    errors.append(f"Skipped unknown/incomplete op: {op.type}")

            except Exception as e:
                errors.append(f"Error in '{op.type}' on '{op.column}': {str(e)}")

        preview = df.head(5).to_dict(orient="records")

        if not body.preview_only and applied:
            _save_df(str(job.id), df)

        return {
            "applied": applied,
            "errors":  errors,
            "preview_rows": preview,
            "new_columns": list(df.columns),
            "saved": not body.preview_only and bool(applied),
            "n_rows": len(df),
            "n_cols": len(df.columns),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{job_id}/columns")
async def get_columns_info(job_id: str, db: AsyncSession = Depends(get_db),
                           user=Depends(get_current_user)):
    """Return column names, dtypes, and sample values for the transform panel."""
    import pandas as pd
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Analysis job not found")
    if str(job.user_id) != str(user.id):
        raise HTTPException(403, "Access denied")

    df = _load_df(str(job.id))
    if df is None:
        raise HTTPException(400, "No dataset found")

    info = []
    for col in df.columns:
        is_numeric = pd.api.types.is_numeric_dtype(df[col])
        sample = df[col].dropna().head(5).tolist()
        info.append({
            "name":       col,
            "dtype":      str(df[col].dtype),
            "is_numeric": is_numeric,
            "missing_n":  int(df[col].isna().sum()),
            "unique_n":   int(df[col].nunique()),
            "sample":     [str(v) for v in sample],
        })
    return {"columns": info, "n_rows": len(df)}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _recode(df, column, mapping, new_col=None):
    dest = new_col or column

    def _recode_val(v):
        if v is None:
            return v
        try:
            if str(v) != str(v):  # nan
                return v
        except Exception:
            return v
        sv = str(v)
        if sv in mapping:
            return mapping[sv]
        try:
            iv = str(int(float(sv)))
            if iv in mapping:
                return mapping[iv]
        except Exception:
            pass
        return v

    df[dest] = df[column].apply(_recode_val)
    return df, {"op": "recode", "column": column, "new_column": dest, "map": mapping}


def _load_df(job_id: str):
    import pandas as pd
    storage_dir = getattr(settings, "STORAGE_DIR", "storage")
    pkl_dir = os.path.join(storage_dir, "dataframes")
    path = os.path.join(pkl_dir, f"{job_id}.pkl")
    if os.path.exists(path):
        try:
            return pd.read_pickle(path)
        except Exception:
            pass
    return None


def _save_df(job_id: str, df):
    storage_dir = getattr(settings, "STORAGE_DIR", "storage")
    pkl_dir = os.path.join(storage_dir, "dataframes")
    os.makedirs(pkl_dir, exist_ok=True)
    df.to_pickle(os.path.join(pkl_dir, f"{job_id}.pkl"))
