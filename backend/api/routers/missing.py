"""api/routers/missing.py — Missing data analysis and MICE imputation endpoints."""
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.deps import get_db, get_current_user
from api.models.database import AnalysisJob
from config import settings

router = APIRouter(prefix="/api/analysis", tags=["missing-data"])


@router.get("/{job_id}/missing")
async def get_missing_report(job_id: str, db: AsyncSession = Depends(get_db),
                              user=Depends(get_current_user)):
    """Return missing data report for this job's dataset."""
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Analysis job not found")
    if str(job.user_id) != str(user.id):
        raise HTTPException(403, "Access denied")
    try:
        df = _load_df(job)
        if df is None or df.empty:
            raise HTTPException(400, "No dataset found for this job")
        from analysis.engine.tests.missing_data import run_missing_analysis
        report = run_missing_analysis(df)
        return report
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


class ImputeRequest(BaseModel):
    strategy: str    = Field("mice", description="'mice' or 'mean' or 'median'")
    n_imputations: int = Field(5, ge=1, le=20)
    max_iter: int      = Field(10, ge=1, le=50)
    columns: Optional[List[str]] = Field(None, description="Specific columns to impute")


@router.post("/{job_id}/impute")
async def impute_missing(job_id: str, body: ImputeRequest,
                         db: AsyncSession = Depends(get_db),
                         user=Depends(get_current_user)):
    """
    Run MICE or simple imputation on this job's dataset.
    Saves imputed DataFrame. Does NOT auto-rerun analysis.
    """
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Analysis job not found")
    if str(job.user_id) != str(user.id):
        raise HTTPException(403, "Access denied")
    try:
        df = _load_df(job)
        if df is None or df.empty:
            raise HTTPException(400, "No dataset found for this job")

        if body.strategy == "mice":
            from analysis.engine.tests.missing_data import run_mice_imputation
            variables = body.columns or list(df.columns)
            res = run_mice_imputation(
                df, variables=variables,
                n_imputations=body.n_imputations,
                max_iter=body.max_iter,
            )
            if "error" in res:
                raise HTTPException(400, res["error"])
            imputed_df = res.pop("imputed_df", None)
            if imputed_df is not None:
                _save_df(str(job.id), imputed_df)
                res["imputed_df_saved"] = True
            return res
        elif body.strategy in ("mean", "median"):
            df_imp = df.copy()
            for col in df_imp.select_dtypes("number").columns:
                if df_imp[col].isna().any():
                    v = df_imp[col].mean() if body.strategy == "mean" else df_imp[col].median()
                    df_imp[col].fillna(v, inplace=True)
            _save_df(str(job.id), df_imp)
            return {
                "strategy": body.strategy,
                "imputed_df_saved": True,
                "columns_imputed": [c for c in df.columns if df[c].isna().any()],
            }
        else:
            raise HTTPException(400, f"Unknown strategy: {body.strategy}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


def _load_df(job):
    """Load the DataFrame for a job."""
    import pandas as pd
    storage_dir = getattr(settings, "STORAGE_DIR", "storage")
    pkl_dir = os.path.join(storage_dir, "dataframes")

    candidates = []
    if getattr(job, 'survey_id', None):
        candidates.append(os.path.join(pkl_dir, f"{job.survey_id}.pkl"))
    if getattr(job, 'source_filename', None):
        candidates.append(os.path.join(pkl_dir, f"{job.source_filename}.pkl"))
    candidates.append(os.path.join(pkl_dir, f"{job.id}.pkl"))

    for p in candidates:
        if os.path.exists(p):
            try:
                return pd.read_pickle(p)
            except Exception:
                pass
    return None


def _save_df(job_id: str, df):
    import pandas as pd
    storage_dir = getattr(settings, "STORAGE_DIR", "storage")
    pkl_dir = os.path.join(storage_dir, "dataframes")
    os.makedirs(pkl_dir, exist_ok=True)
    df.to_pickle(os.path.join(pkl_dir, f"{job_id}.pkl"))
