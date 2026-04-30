# backend/api/routers/analysis.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid, os, shutil
from datetime import datetime

from api.deps import get_db, get_current_user
from api.models.database import AnalysisJob, Survey, JobStatus, User
from config import settings

router = APIRouter()

def job_out(j: AnalysisJob):
    return {
        "id": j.id,
        "survey_id": j.survey_id,
        "status": j.status,
        "source_type": j.source_type,
        "source_filename": j.source_filename,
        "data_dictionary": j.data_dictionary,
        "decode_warnings": j.decode_warnings,
        "n_rows": j.n_rows,
        "n_columns": j.n_columns,
        "n_complete_rows": j.n_complete_rows,
        "missing_strategy": j.missing_strategy,
        "project_brief": j.project_brief,
        "selected_tests": j.selected_tests,
        "generated_code": j.generated_code,
        "results": j.results,
        "chart_paths": j.chart_paths,
        "report_path": j.report_path,
        "error_message": j.error_message,
        "created_at": str(j.created_at),
        "decode_completed_at": str(j.decode_completed_at) if j.decode_completed_at else None,
        "analysis_started_at": str(j.analysis_started_at) if j.analysis_started_at else None,
        "completed_at": str(j.completed_at) if j.completed_at else None,
    }

# ─── Start from survey ────────────────────────────────────────────────
class StartFromSurveyRequest(BaseModel):
    survey_id: str
    project_brief: Optional[dict] = {}

@router.post("/start")
async def start_from_survey(
    data: StartFromSurveyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify survey ownership
    result = await db.execute(select(Survey).where(Survey.id == data.survey_id, Survey.user_id == user.id))
    survey = result.scalar_one_or_none()
    if not survey:
        raise HTTPException(404, "Survey not found")

    brief = data.project_brief or survey.project_brief or {}
    job = AnalysisJob(
        id=str(uuid.uuid4()),
        survey_id=data.survey_id,
        status=JobStatus.pending,
        source_type="survey_db",
        project_brief=brief,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Fire background pipeline
    background_tasks.add_task(_run_pipeline, job.id)
    return job_out(job)

# ─── Start from uploaded file ─────────────────────────────────────────
@router.post("/upload")
async def start_from_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_brief: str = Form("{}"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import json
    try:
        brief = json.loads(project_brief)
    except Exception:
        brief = {}

    # Save uploaded file
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "data.csv")[1].lower()
    upload_path = os.path.join(settings.STORAGE_DIR, f"{job_id}{ext}")
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    source_type = {"xlsx": "excel", "xls": "excel", "csv": "csv", "sav": "spss"}.get(ext.lstrip("."), "csv")

    job = AnalysisJob(
        id=job_id,
        status=JobStatus.pending,
        source_type=source_type,
        source_filename=file.filename,
        project_brief=brief,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(_run_pipeline, job.id, upload_path)
    return job_out(job)

# ─── Job management ───────────────────────────────────────────────────
@router.get("/jobs")
async def list_jobs(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Get all surveys owned by user
    sv_result = await db.execute(select(Survey.id).where(Survey.user_id == user.id))
    survey_ids = [r[0] for r in sv_result.all()]

    result = await db.execute(
        select(AnalysisJob)
        .where(
            (AnalysisJob.survey_id.in_(survey_ids)) | (AnalysisJob.survey_id.is_(None))
        )
        .order_by(AnalysisJob.created_at.desc())
    )
    jobs = result.scalars().all()
    return [job_out(j) for j in jobs]

@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return job_out(job)

# ─── Decode review approval ───────────────────────────────────────────
class ApproveDecodeRequest(BaseModel):
    variable_overrides: dict = {}
    missing_strategy: str = "flag_only"

@router.post("/jobs/{job_id}/approve-decode")
async def approve_decode(
    job_id: str,
    data: ApproveDecodeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != JobStatus.decode_review:
        raise HTTPException(400, f"Job is in {job.status} status, not decode_review")

    job.researcher_overrides = data.variable_overrides
    job.missing_strategy = data.missing_strategy
    job.status = JobStatus.parsing
    job.analysis_started_at = datetime.utcnow()
    await db.commit()

    background_tasks.add_task(_continue_pipeline, job.id)
    return job_out(job)

@router.post("/jobs/{job_id}/reject-decode")
async def reject_decode(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job: raise HTTPException(404)
    job.status = JobStatus.failed
    job.error_message = "Decode rejected by researcher"
    await db.commit()
    return job_out(job)

# ─── Report download ──────────────────────────────────────────────────
@router.get("/jobs/{job_id}/report")
async def download_report(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job or not job.report_path:
        raise HTTPException(404, "Report not ready")
    if not os.path.exists(job.report_path):
        raise HTTPException(404, "Report file not found on disk")
    return FileResponse(job.report_path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        filename=f"Chapter4_{job_id[:8]}.docx")

@router.get("/jobs/{job_id}/charts/{index}")
async def get_chart(job_id: str, index: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job or not job.chart_paths or index >= len(job.chart_paths):
        raise HTTPException(404)
    path = job.chart_paths[index]
    if not os.path.exists(path):
        raise HTTPException(404)
    return FileResponse(path, media_type="image/png")

# ─── Background pipeline runner ───────────────────────────────────────
async def _run_pipeline(job_id: str, file_path: str = None):
    """Runs stages 1-2 (assembly + decode), then pauses for review."""
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine

    engine = create_engine(settings.SYNC_DATABASE_URL)
    with Session(engine) as db:
        job = db.get(AnalysisJob, job_id)
        if not job:
            return

        try:
            # Stage 1 — Assemble
            job.status = "assembling"
            db.commit()

            # Stage 2 — Decode
            job.status = "decoding"
            db.commit()

            from analysis.decode import decode_file, decode_from_db
            if file_path and os.path.exists(file_path):
                result = decode_file(file_path)
            elif job.survey_id:
                result = decode_from_db(job.survey_id, db)
            else:
                raise ValueError("No data source available")

            job.data_dictionary = result["data_dictionary"]
            job.decode_warnings = result["warnings"]
            job.n_rows = result["n_rows"]
            job.n_columns = result["n_columns"]
            job.n_complete_rows = result["n_complete_rows"]
            job.decode_completed_at = datetime.utcnow()
            job.status = "decode_review"
            db.commit()

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()

async def _continue_pipeline(job_id: str):
    """Continues from stage 3 after researcher approves decode."""
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine

    engine = create_engine(settings.SYNC_DATABASE_URL)
    with Session(engine) as db:
        job = db.get(AnalysisJob, job_id)
        if not job:
            return

        try:
            from analysis.pipeline import run_stages_3_to_9
            run_stages_3_to_9(job, db)
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
