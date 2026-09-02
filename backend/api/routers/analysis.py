# backend/api/routers/analysis.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel
from typing import Optional
import uuid, os, shutil
from datetime import datetime

from api.deps import get_db, get_current_user, limiter
from api.models.database import AnalysisJob, Survey, JobStatus, User
from config import settings
from services.credits import (
    billing_breakdown,
    credits_from_llm_usage,
    deduct_credits_sync,
    InsufficientCreditsError,
)
from decimal import Decimal

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
        "inspection_report": j.inspection_report,
        "cleaning_summary": j.cleaning_summary,
        "n_rows": j.n_rows,
        "n_columns": j.n_columns,
        "n_complete_rows": j.n_complete_rows,
        "missing_strategy": j.missing_strategy,
        "project_brief": j.project_brief,
        "selected_tests": j.selected_tests,
        "generated_code": j.generated_code,
        "results": j.results,
        "chart_paths": j.chart_paths,
        "html_tables": j.html_tables or {},

        "report_path": j.report_path,
        "error_message": j.error_message,
        "created_at": str(j.created_at),
        "decode_completed_at": str(j.decode_completed_at) if j.decode_completed_at else None,
        "analysis_started_at": str(j.analysis_started_at) if j.analysis_started_at else None,
        "completed_at": str(j.completed_at) if j.completed_at else None,
        "chapter_texts": {k: bool(v) for k, v in (j.chapter_texts or {}).items()},
        "report_type": j.report_type or "chapter4",
        "academic_tradition": j.academic_tradition or "standard",
        "formatting_options": j.formatting_options or {},
        # Technique selection
        "auto_select_techniques": j.auto_select_techniques if j.auto_select_techniques is not None else True,
        "selected_techniques": j.selected_techniques or [],
        # Multi-strand research design
        "study_types": j.study_types or ["quantitative"],
        "sample_size": j.sample_size,
        "qualitative_files": [{"name": f.get("name")} for f in (j.qualitative_files or [])],
        "thematic_results": j.thematic_results or {},
        "qual_coding_approach": j.qual_coding_approach or "inductive",
        "qual_min_themes": j.qual_min_themes or 3,
        "has_pretest_posttest": j.has_pretest_posttest or False,
        "has_control_group": j.has_control_group or False,
        "n_cases": j.n_cases or 1,
        "case_analysis_approach": j.case_analysis_approach or "within",
        # Visualization
        "auto_viz": j.auto_viz if j.auto_viz is not None else True,
        "selected_viz": j.selected_viz or [],
        # Billing
        "llm_usage": j.llm_usage or {},
        "credits_estimated": float(j.credits_estimated) if j.credits_estimated is not None else None,
        "credits_charged": float(j.credits_charged) if j.credits_charged is not None else None,
        "report_paid": bool(j.report_paid),
        "user_id": j.user_id,
        # Preprocessing gate
        "preprocessing_mode": j.preprocessing_mode,
        "manual_choices": j.manual_choices or {},
    }


async def _assert_job_access(job: AnalysisJob, user: User, db: AsyncSession) -> None:
    if job.user_id and job.user_id == user.id:
        return
    if job.survey_id:
        result = await db.execute(
            select(Survey).where(Survey.id == job.survey_id, Survey.user_id == user.id)
        )
        if result.scalar_one_or_none():
            return
    if not job.user_id and not job.survey_id:
        raise HTTPException(403, "Access denied")
    raise HTTPException(403, "Access denied")

# ─── Start from survey ────────────────────────────────────────────────
class StartFromSurveyRequest(BaseModel):
    survey_id: str
    project_brief: Optional[dict] = {}
    formatting_options: Optional[dict] = {}
    academic_tradition: Optional[str] = "standard"

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
        user_id=user.id,
        survey_id=data.survey_id,
        status=JobStatus.pending,
        source_type="survey_db",
        project_brief=brief,
        formatting_options=data.formatting_options or {},
        academic_tradition=data.academic_tradition or "standard",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Fire pipeline via process-pool queue so event loop stays free
    from workers.queue import enqueue_job
    from api.routers.analysis_worker import run_pipeline_sync
    await enqueue_job(job.id, run_pipeline_sync, job.id)
    return job_out(job)

# ─── Inspect uploaded file (Lightweight sync for Wizard) ──────────────
@router.post("/inspect-file")
@limiter.limit("15/minute")
async def inspect_file(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    import pandas as pd
    import numpy as np
    import tempfile
    from analysis.cleaner import clean_and_inspect

    # ── 10 MB upload gate (server-side defence-in-depth) ───────────────────
    _MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
    file_content = await file.read()
    if len(file_content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File exceeds the 10 MB upload limit "
                f"({len(file_content) / 1024 / 1024:.1f} MB uploaded). "
                "Please reduce your dataset size before uploading."
            )
        )

    # Save to temp file
    import io as _io
    ext = os.path.splitext(file.filename or "data.csv")[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name

    try:
        raw_df = None
        if ext in (".xlsx", ".xls"):
            raw_df = pd.read_excel(tmp_path)
        elif ext == ".csv":
            raw_df = pd.read_csv(tmp_path)
        elif ext == ".sav":
            try:
                import pyreadstat
                raw_df, _ = pyreadstat.read_sav(tmp_path)
            except Exception:
                pass

        if raw_df is None:
            raise HTTPException(400, "Could not parse file. Ensure it is a valid CSV, Excel, or SAV file.")

        df_clean, _inspection, _cleaning = clean_and_inspect(raw_df)

        # Build a per-column data dictionary with measurement level inference
        def infer_level(series: pd.Series, n_unique: int) -> str:
            if series.dtype == object or series.dtype.name == "category":
                return "nominal"
            if series.dtype in ("bool",):
                return "nominal"
            if pd.api.types.is_numeric_dtype(series):
                # ≤6 unique values → grouping/categorical variable (gender, condition, etc.)
                # 7–10 unique → ordinal (Likert scale)
                # >10 unique  → ratio (continuous numeric)
                if n_unique <= 6:
                    return "nominal"
                if n_unique <= 10:
                    return "ordinal"
                return "ratio"
            return "nominal"

        data_dictionary: dict = {}
        for col in df_clean.columns:
            series = df_clean[col]
            n_unique = int(series.nunique(dropna=True))
            n_missing = int(series.isna().sum())
            dtype_str = str(series.dtype)
            level = infer_level(series, n_unique)
            data_dictionary[col] = {
                "dtype": dtype_str,
                "level": level,            # "ratio" | "ordinal" | "nominal"
                "n_unique": n_unique,
                "n_missing": n_missing,
                "n_rows": int(len(series)),
            }

        return {
            "data_dictionary": data_dictionary,
            "filename": file.filename,
            "n_rows": int(len(df_clean)),
            "n_cols": int(len(df_clean.columns)),
            "inspection_report": _inspection,
            "cleaning_summary": _cleaning,
        }
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ─── Lightweight column parser (no cleaning) — for wizard Step 5 compatibility ─
@router.post("/parse-columns")
@limiter.limit("20/minute")
async def parse_columns(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Fast column name + type extraction with NO cleaning. Used by wizard Step 5
    to power Technique Selector compatibility warnings without running the full
    inspection pipeline. Returns only the simplified data_dictionary."""
    import pandas as pd
    import tempfile

    ext = os.path.splitext(file.filename or "data.csv")[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        raw_df = None
        if ext in (".xlsx", ".xls"):
            raw_df = pd.read_excel(tmp_path)
        elif ext == ".csv":
            raw_df = pd.read_csv(tmp_path)
        elif ext == ".sav":
            try:
                import pyreadstat
                raw_df, _ = pyreadstat.read_sav(tmp_path)
            except Exception:
                pass

        if raw_df is None:
            raise HTTPException(400, "Could not parse file.")

        def infer_level(series: pd.Series, n_unique: int) -> str:
            if series.dtype == object or series.dtype.name == "category":
                return "nominal"
            if series.dtype in ("bool",):
                return "nominal"
            if pd.api.types.is_numeric_dtype(series):
                # ≤6 unique values → almost certainly a grouping/categorical variable
                # (e.g. gender=0/1, condition=1/2/3, region=1-5)
                # 7–10 unique → likely a Likert-scale ordinal item
                # >10 unique → ratio (continuous numeric)
                if n_unique <= 6:
                    return "nominal"
                if n_unique <= 10:
                    return "ordinal"
                return "ratio"
            return "nominal"

        data_dictionary: dict = {}
        for col in raw_df.columns:
            series = raw_df[col]
            n_unique = int(series.nunique(dropna=True))
            n_missing = int(series.isna().sum())
            data_dictionary[col] = {
                "dtype": str(series.dtype),
                "level": infer_level(series, n_unique),
                "n_unique": n_unique,
                "n_missing": n_missing,
                "n_rows": int(len(series)),
            }

        return {
            "data_dictionary": data_dictionary,
            "filename": file.filename,
            "n_rows": int(len(raw_df)),
            "n_cols": int(len(raw_df.columns)),
        }
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ─── Preprocessing choice endpoint ────────────────────────────────────────────
class PreprocessingChoiceRequest(BaseModel):
    mode: str                          # 'auto' | 'manual'
    manual_choices: Optional[dict] = {}

@router.post("/jobs/{job_id}/preprocessing-choice")
async def submit_preprocessing_choice(
    job_id: str,
    data: PreprocessingChoiceRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """User submits their preprocessing mode choice. The background pipeline is
    polling for this and will resume once it sees preprocessing_mode is set."""
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    await _assert_job_access(job, user, db)
    if job.status != "awaiting_preprocessing_choice":
        raise HTTPException(400, f"Job is not awaiting a preprocessing choice (current status: {job.status})")
    if data.mode not in ("auto", "manual"):
        raise HTTPException(400, "mode must be 'auto' or 'manual'")

    job.preprocessing_mode = data.mode
    job.manual_choices = data.manual_choices or {}
    await db.commit()
    return {"status": "ok", "mode": data.mode}


# ─── Start from uploaded file ─────────────────────────────────────────
@router.post("/upload")
async def start_from_file(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    survey_id: Optional[str] = Form(None),
    project_brief: str = Form("{}"),
    report_type: str = Form("chapter4"),
    academic_tradition: str = Form("standard"),
    formatting_options: str = Form("{}"),
    auto_select_techniques: str = Form("true"),
    selected_techniques: str = Form("[]"),
    chapters_doc: Optional[UploadFile] = File(None),
    # ── New multi-strand fields ─────────────────────────────────
    study_types: str = Form('["quantitative"]'),
    sample_size: Optional[str] = Form(None),
    qual_coding_approach: str = Form("inductive"),
    qual_min_themes: str = Form("3"),
    has_pretest_posttest: str = Form("false"),
    has_control_group: str = Form("false"),
    n_cases: str = Form("1"),
    case_analysis_approach: str = Form("within"),
    auto_viz: str = Form("true"),
    selected_viz: str = Form("[]"),
    auto_tables: str = Form("true"),
    selected_tables: str = Form("[]"),
    qualitative_files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import json
    from analysis.extractor import extract_chapters_from_single_doc

    # parse JSON fields
    try:
        brief = json.loads(project_brief)
    except:
        brief = {}
    try:
        techniques_list = json.loads(selected_techniques)
    except:
        techniques_list = []
    try:
        format_opts = json.loads(formatting_options)
    except:
        format_opts = {}
    auto_select = auto_select_techniques.lower() not in ("false", "0", "no")

    # Parse new multi-strand fields
    try:
        study_types_list = json.loads(study_types)
    except Exception:
        study_types_list = ["quantitative"]
    if not study_types_list:
        study_types_list = ["quantitative"]

    sample_size_int = None
    if sample_size and sample_size.strip().isdigit():
        sample_size_int = int(sample_size)

    try:
        selected_viz_list = json.loads(selected_viz)
    except Exception:
        selected_viz_list = []

    auto_viz_bool = auto_viz.lower() not in ("false", "0", "no")
    auto_tables_bool = auto_tables.lower() not in ("false", "0", "no")
    try:
        selected_tables_list = json.loads(selected_tables)
    except Exception:
        selected_tables_list = []
    has_pretest = has_pretest_posttest.lower() in ("true", "1", "yes")
    has_ctrl    = has_control_group.lower() in ("true", "1", "yes")
    n_cases_int = int(n_cases) if n_cases.isdigit() else 1
    min_themes_int = int(qual_min_themes) if qual_min_themes.isdigit() else 3

    # Save main data file
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    job_id = str(uuid.uuid4())
    upload_path = None
    source_type = "csv"
    
    if survey_id:
        source_type = "survey_db"
    elif file:
        _MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
        _file_content = await file.read()
        if len(_file_content) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File exceeds the 10 MB upload limit "
                    f"({len(_file_content) / 1024 / 1024:.1f} MB uploaded). "
                    "Please reduce your dataset size before uploading."
                )
            )
        ext = os.path.splitext(file.filename or "data.csv")[1].lower()
        upload_path = os.path.join(settings.STORAGE_DIR, f"{job_id}{ext}")
        with open(upload_path, "wb") as f:
            f.write(_file_content)
        source_type = {"xlsx": "excel", "xls": "excel", "csv": "csv", "sav": "spss"}.get(ext.lstrip("."), "csv")
    else:
        raise HTTPException(400, "Must provide either file or survey_id")

    # Save and extract single chapters document (optional)
    chapter_texts = {}
    if chapters_doc and chapters_doc.filename:
        chapters_dir = os.path.join(settings.STORAGE_DIR, "chapters", job_id)
        os.makedirs(chapters_dir, exist_ok=True)
        ch_ext = os.path.splitext(chapters_doc.filename)[1].lower()
        ch_path = os.path.join(chapters_dir, f"chapters{ch_ext}")
        with open(ch_path, "wb") as f:
            shutil.copyfileobj(chapters_doc.file, f)
        chapter_texts = extract_chapters_from_single_doc(ch_path)

    # Save qualitative transcript files
    qual_file_infos = []
    if qualitative_files:
        qual_dir = os.path.join(settings.STORAGE_DIR, "transcripts", job_id)
        os.makedirs(qual_dir, exist_ok=True)
        for qf in qualitative_files:
            if qf and qf.filename:
                qf_ext = os.path.splitext(qf.filename)[1].lower()
                qf_path = os.path.join(qual_dir, f"{uuid.uuid4()}{qf_ext}")
                with open(qf_path, "wb") as fout:
                    shutil.copyfileobj(qf.file, fout)
                qual_file_infos.append({"name": qf.filename, "path": qf_path})

    job = AnalysisJob(
        id=job_id,
        user_id=user.id,
        survey_id=survey_id if survey_id else None,
        status=JobStatus.pending,
        source_type=source_type,
        source_filename=file.filename if file else f"Survey {survey_id}",
        project_brief=brief,
        chapter_texts=chapter_texts if chapter_texts else {},
        report_type=report_type or "chapter4",
        academic_tradition=academic_tradition or "standard",
        formatting_options=format_opts,
        auto_select_techniques=auto_select,
        selected_techniques=techniques_list if not auto_select else [],
        # Multi-strand fields
        study_types=study_types_list,
        sample_size=sample_size_int,
        qual_coding_approach=qual_coding_approach or "inductive",
        qual_min_themes=min_themes_int,
        has_pretest_posttest=has_pretest,
        has_control_group=has_ctrl,
        n_cases=n_cases_int,
        case_analysis_approach=case_analysis_approach or "within",
        qualitative_files=qual_file_infos,
        auto_viz=auto_viz_bool,
        selected_viz=selected_viz_list if not auto_viz_bool else [],
        auto_tables=auto_tables_bool,
        selected_tables=selected_tables_list if not auto_tables_bool else [],
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    from workers.queue import enqueue_job
    from api.routers.analysis_worker import run_pipeline_sync
    await enqueue_job(job.id, run_pipeline_sync, job.id, upload_path)
    return job_out(job)


# ─── Job management ───────────────────────────────────────────────────
@router.get("/jobs")
async def list_jobs(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Return only jobs that belong to the current user (strict user isolation)."""
    result = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.user_id == user.id)
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
    await _assert_job_access(job, user, db)
    return job_out(job)


@router.get("/jobs/{job_id}/preview")
async def get_job_preview(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    import os
    import docx
    
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    await _assert_job_access(job, user, db)
    
    # Try report_text first
    if job.report_text and isinstance(job.report_text, dict):
        parts = []
        if "chapter_title" in job.report_text:
            parts.append(job.report_text.get("chapter_title", ""))
        if "sections" in job.report_text and isinstance(job.report_text["sections"], list):
            for sec in job.report_text["sections"]:
                parts.append(sec.get("heading", ""))
                parts.append(sec.get("text", ""))
        else:
            # Fallback if it's a flat dict of strings
            for v in job.report_text.values():
                if isinstance(v, str): parts.append(v)
                
        text = "\n\n".join(filter(None, parts))
        if text.strip():
            return {"text": text}
            
    # Try chapter_texts fallback
    if job.chapter_texts and isinstance(job.chapter_texts, dict):
        text = job.chapter_texts.get("full_text", "")
        if text.strip():
            return {"text": text}
            
    # Extract from DOCX directly
    if job.report_path and os.path.exists(job.report_path):
        try:
            doc = docx.Document(job.report_path)
            text = "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            return {"text": text}
        except Exception:
            pass
            
    raise HTTPException(404, "Preview not available yet")


@router.get("/jobs/{job_id}/billing")
async def get_job_billing(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from services.credits import get_or_create_wallet_async
    from api.models.database import SystemSettings

    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    await _assert_job_access(job, user, db)

    wallet = await get_or_create_wallet_async(db, user.id)
    settings_result = await db.execute(select(SystemSettings).where(SystemSettings.key.in_(["base_operations_cost", "credit_markup_multiplier"])))
    sys_settings = settings_result.scalars().all()
    sys_dict = {s.key: s.value for s in sys_settings}
    
    base_operations_cost = Decimal(sys_dict.get("base_operations_cost", "5.00"))
    markup_multiplier = float(sys_dict.get("credit_markup_multiplier", settings.CREDIT_MARKUP_MULTIPLIER))

    breakdown = billing_breakdown(job.llm_usage, markup_multiplier=markup_multiplier)
    
    ai_cost = Decimal(str(breakdown["credits_required"]))
    required = ai_cost + base_operations_cost
    balance = Decimal(str(wallet.balance))

    presentation_credits_required = Decimal("0.00")
    if job.presentation_llm_usage:
        presentation_breakdown = billing_breakdown(job.presentation_llm_usage, markup_multiplier=markup_multiplier)
        presentation_credits_required = Decimal(str(presentation_breakdown["credits_required"]))

    return {
        **breakdown,
        "ai_credits_required": float(ai_cost),
        "base_operations_cost": float(base_operations_cost),
        "credits_required": float(required),
        "presentation_credits_required": float(presentation_credits_required),
        "report_ready": bool(job.report_path and job.status == JobStatus.complete),
        "report_paid": bool(job.report_paid),
        "presentation_paid": bool(job.presentation_paid),
        "presentation_generated": bool(job.presentation_path and os.path.exists(job.presentation_path)),
        "credits_charged": float(job.credits_charged) if job.credits_charged is not None else None,
        "wallet_balance": float(balance),
        "can_download": bool(job.report_paid) or balance >= required,
        "job_status": job.status.value if hasattr(job.status, "value") else job.status,
    }

# ─── Decode review approval ───────────────────────────────────────────
class ApproveDecodeRequest(BaseModel):
    variable_overrides:  dict = {}
    # 'preprocessed' = Stage 1 already handled missing values; skip re-imputation here
    missing_strategy:    str  = "preprocessed"
    # Optional survey case-weighting column (must exist in the dataset)
    weight_column:       str | None = None
    # Optional imputation: 'mice' | 'knn' | None (None = listwise deletion)
    imputation_method:   str | None = None

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
    await _assert_job_access(job, user, db)
    if job.status != JobStatus.decode_review:
        raise HTTPException(400, f"Job is in {job.status} status, not decode_review")

    job.researcher_overrides = data.variable_overrides
    job.missing_strategy     = data.missing_strategy
    job.weight_column        = data.weight_column or None
    job.imputation_method    = data.imputation_method or None
    job.status               = JobStatus.parsing
    job.analysis_started_at  = datetime.utcnow()
    await db.commit()

    background_tasks.add_task(_continue_pipeline, job.id)
    return job_out(job)

@router.post("/jobs/{job_id}/reject-decode")
async def reject_decode(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404)
    await _assert_job_access(job, user, db)
    job.status = JobStatus.failed
    job.error_message = "The analysis was cancelled during data decoding review."
    await db.commit()
    return job_out(job)


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reset a failed job and re-run pipeline."""
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    await _assert_job_access(job, user, db)

    job.error_message = None
    if job.data_dictionary and job.researcher_overrides is not None:
        # Restart from analysis stage 3
        job.status = JobStatus.parsing
        job.analysis_started_at = datetime.utcnow()
        await db.commit()
        background_tasks.add_task(_continue_pipeline, job.id)
    else:
        # Restart from stage 1
        job.status = JobStatus.assembling
        await db.commit()
        upload_path = None
        for ext in [".csv", ".xlsx", ".xls", ".sav"]:
            candidate = os.path.join(settings.STORAGE_DIR, f"{job.id}{ext}")
            if os.path.exists(candidate):
                upload_path = candidate
                break
        background_tasks.add_task(_run_pipeline, job.id, upload_path)

    return job_out(job)

# ─── Data Transform endpoints ────────────────────────────────────────────────

@router.get("/jobs/{job_id}/columns")
async def get_job_columns(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return column metadata for the job's uploaded data file."""
    import pandas as pd
    import numpy as np

    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    await _assert_job_access(job, user, db)

    # Try to load from stored file
    df = _load_job_df(job)
    if df is None:
        # Fallback: build from inspection_report
        report = job.inspection_report or {}
        cols = []
        for col_name, info in report.get("column_profiles", {}).items():
            cols.append({
                "name": col_name,
                "dtype": info.get("dtype", "object"),
                "is_numeric": info.get("is_numeric", False),
                "missing_n": int(info.get("missing_n", 0)),
                "unique_n": int(info.get("unique_n", 0)),
                "sample": info.get("sample", []),
            })
        if not cols:
            raise HTTPException(404, "Could not load column info — data file not found")
        return {"columns": cols}

    columns = []
    for col in df.columns:
        series = df[col]
        is_num = pd.api.types.is_numeric_dtype(series)
        sample_vals = series.dropna().unique()[:5].tolist()
        sample_strs = [str(v) for v in sample_vals]
        columns.append({
            "name": col,
            "dtype": str(series.dtype),
            "is_numeric": bool(is_num),
            "missing_n": int(series.isna().sum()),
            "unique_n": int(series.nunique()),
            "sample": sample_strs,
        })
    return {"columns": columns}


@router.post("/jobs/{job_id}/transform")
async def transform_job_data(
    job_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Apply data transformations (recode, compute, reverse_score, bin, standardize, dummy)."""
    import pandas as pd
    import numpy as np

    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    await _assert_job_access(job, user, db)

    df = _load_job_df(job)
    if df is None:
        raise HTTPException(400, "Data file not available for transformation")

    operations = payload.get("operations", [])
    preview_only = payload.get("preview_only", False)
    applied = []
    errors = []

    for op in operations:
        op_type = op.get("type")
        col = op.get("column", "")
        new_col = op.get("new_column") or f"{col}_{op_type}"

        if col not in df.columns:
            errors.append(f"Column '{col}' not found"); continue

        try:
            if op_type == "recode":
                mapping = {str(k): v for k, v in (op.get("map") or {}).items()}
                df[new_col] = df[col].astype(str).map(mapping).fillna(df[col].astype(str))
                try:
                    df[new_col] = pd.to_numeric(df[new_col])
                except Exception:
                    pass
                applied.append(new_col)

            elif op_type == "compute":
                items = [i for i in (op.get("items") or []) if i in df.columns]
                if not items:
                    errors.append(f"compute: no valid items selected"); continue
                agg = op.get("agg", "mean")
                sub = df[items].apply(pd.to_numeric, errors="coerce")
                if agg == "mean":   df[new_col] = sub.mean(axis=1)
                elif agg == "sum":  df[new_col] = sub.sum(axis=1)
                elif agg == "min":  df[new_col] = sub.min(axis=1)
                elif agg == "max":  df[new_col] = sub.max(axis=1)
                applied.append(new_col)

            elif op_type == "reverse_score":
                scale_max = int(op.get("scale_max", 5))
                df[new_col] = scale_max + 1 - pd.to_numeric(df[col], errors="coerce")
                applied.append(new_col)

            elif op_type == "bin":
                breaks = op.get("breaks", [])
                if isinstance(breaks, list):
                    breaks = [float(b) for b in breaks if str(b).strip()]
                labels = op.get("labels") or None
                if labels and isinstance(labels, list):
                    labels = [str(l) for l in labels] or None
                df[new_col] = pd.cut(
                    pd.to_numeric(df[col], errors="coerce"),
                    bins=breaks, labels=labels, include_lowest=True
                ).astype(str)
                applied.append(new_col)

            elif op_type == "standardize":
                method = op.get("method", "zscore")
                num = pd.to_numeric(df[col], errors="coerce")
                if method == "zscore":
                    df[new_col] = (num - num.mean()) / num.std()
                else:
                    df[new_col] = (num - num.min()) / (num.max() - num.min())
                applied.append(new_col)

            elif op_type == "dummy":
                ref = op.get("reference")
                dummies = pd.get_dummies(df[col].astype(str), prefix=col, drop_first=False)
                if ref and f"{col}_{ref}" in dummies.columns:
                    dummies = dummies.drop(columns=[f"{col}_{ref}"])
                for d_col in dummies.columns:
                    df[d_col] = dummies[d_col].astype(int)
                    applied.append(d_col)
        except Exception as e:
            errors.append(f"{op_type} on '{col}': {str(e)}")

    if preview_only:
        preview = df[list(dict.fromkeys(
            [c for c in df.columns if any(a == c or c in df.columns for a in applied)]
        ))].head(5)
        return {"preview_rows": preview.fillna("").to_dict(orient="records"), "applied": applied, "errors": errors}

    # Save back
    if applied and not errors:
        _save_job_df(job, df)
        # Update column count
        job.n_columns = len(df.columns)
        await db.commit()

    return {"applied": applied, "errors": errors}


def _load_job_df(job):
    """Load the job's data file as a DataFrame. Returns None if not found."""
    import pandas as pd
    try:
        # Try stored file path first (original upload)
        file_path = _find_job_file(job)
        if not file_path:
            return None
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            return pd.read_csv(file_path, low_memory=False)
        elif ext in (".xlsx", ".xls"):
            return pd.read_excel(file_path)
        elif ext == ".sav":
            import pyreadstat
            df, _ = pyreadstat.read_sav(file_path)
            return df
    except Exception:
        pass
    return None


def _save_job_df(job, df):
    """Save transformed DataFrame back to the job's file."""
    import pandas as pd
    file_path = _find_job_file(job)
    if not file_path:
        # Save as new CSV alongside original
        new_path = os.path.join(settings.STORAGE_DIR, f"{job.id}_transformed.csv")
        df.to_csv(new_path, index=False)
        return
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        df.to_excel(file_path, index=False)
    else:
        df.to_csv(file_path, index=False)


def _find_job_file(job):
    """Find the data file for a job. Checks transformed file first, then original."""
    # Transformed file takes precedence
    transformed = os.path.join(settings.STORAGE_DIR, f"{job.id}_transformed.csv")
    if os.path.exists(transformed):
        return transformed
    # Try original upload paths
    for ext in (".csv", ".xlsx", ".xls", ".sav"):
        p = os.path.join(settings.STORAGE_DIR, f"{job.id}{ext}")
        if os.path.exists(p):
            return p
    return None


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Delete an analysis job and its associated files. Owner can always delete, even stuck/running jobs."""
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.user_id == user.id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found or access denied")
    # Clean up files on disk
    for path in [job.report_path, job.presentation_path]:
        if path and os.path.exists(path):
            try: os.remove(path)
            except Exception: pass
    if job.chart_paths:
        for p in (job.chart_paths or []):
            if p and os.path.exists(p):
                try: os.remove(p)
                except Exception: pass
    await db.delete(job)
    await db.commit()
    return {"deleted": True}

# ─── Report and PDF download / Unlock ─────────────────────────────────

@router.post("/jobs/{job_id}/unlock")
async def unlock_analysis(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from api.models.database import SystemSettings
    
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    await _assert_job_access(job, user, db)
    
    if job.report_paid:
        return {"unlocked": True, "already_paid": True}

    settings_result = await db.execute(select(SystemSettings).where(SystemSettings.key.in_(["base_operations_cost", "credit_markup_multiplier"])))
    sys_settings = settings_result.scalars().all()
    sys_dict = {s.key: s.value for s in sys_settings}
    
    base_operations_cost = Decimal(sys_dict.get("base_operations_cost", "5.00"))
    markup_multiplier = float(sys_dict.get("credit_markup_multiplier", settings.CREDIT_MARKUP_MULTIPLIER))
    
    ai_cost = credits_from_llm_usage(job.llm_usage, markup_multiplier=markup_multiplier)
    required = ai_cost + base_operations_cost
    
    engine = create_engine(settings.SYNC_DATABASE_URL)
    with Session(engine) as sync_db:
        sync_job = sync_db.get(AnalysisJob, job_id)
        if not sync_job.report_paid:
            try:
                deduct_credits_sync(
                    sync_db,
                    user.id,
                    required,
                    job_id,
                    f"Unlock Analysis — job {job_id[:8]}",
                )
            except InsufficientCreditsError as exc:
                raise HTTPException(
                    status_code=402,
                    detail={
                        "message": "Insufficient analysis credits",
                        "balance": exc.balance,
                        "required": exc.required,
                    },
                ) from exc
            sync_job.report_paid = True
            sync_job.credits_charged = required
            if not sync_job.credits_estimated:
                sync_job.credits_estimated = required
            sync_db.commit()
    job.report_paid = True
    job.credits_charged = required
    await db.commit()
    return {"unlocked": True}

@router.get("/jobs/{job_id}/report/pdf")
async def download_report_pdf(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    import tempfile
    import docx
    
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(404, "Report not ready")
        
    await _assert_job_access(job, user, db)

    if not job.report_paid:
        raise HTTPException(402, "Please unlock the analysis first")

    text = ""
    if job.chapter_texts and job.chapter_texts.get('full_text'):
        text = job.chapter_texts.get('full_text', '')
    elif job.report_path and os.path.exists(job.report_path):
        # Extract text from the docx
        doc = docx.Document(job.report_path)
        text = "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    else:
        raise HTTPException(404, "Report not ready")

    try:
        temp_dir = tempfile.mkdtemp()
        pdf_path = os.path.join(temp_dir, f"report_{job_id}.pdf")
        
        doc = SimpleDocTemplate(pdf_path, pagesize=letter)
        styles = getSampleStyleSheet()
        normal_style = styles["Normal"]
        story = []
        for p in text.split('\n\n'):
            p_strip = p.strip()
            if p_strip:
                p_clean = p_strip.replace('**', '').replace('##', '').replace('#', '')
                # Escape XML-unsafe characters that cause ReportLab ExpatError
                p_safe = p_clean.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(p_safe, normal_style))
                story.append(Spacer(1, 12))
        
        doc.build(story)
        
        import re
        brief_data = job.project_brief or {}
        topic_raw = brief_data.get("topic") or brief_data.get("research_goal") or "Report"
        topic_slug = re.sub(r'[^a-zA-Z0-9]+', '_', topic_raw)[:40].strip('_')
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"{topic_slug}_Report.pdf"
        )
    except Exception as e:
        raise HTTPException(500, f"Error generating PDF: {e}")

# ─── Presentation generation & download ───────────────────────────────
@router.post("/jobs/{job_id}/presentation/generate")
async def generate_presentation(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from pptx import Presentation
    from pptx.util import Inches
    import tempfile
    import os
    import json
    import re
    from fastapi.concurrency import run_in_threadpool
    import anthropic
    from config import settings

    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    await _assert_job_access(job, user, db)

    if job.presentation_path and os.path.exists(job.presentation_path):
        return {"status": "already_generated"}

    # Get report text
    report_text = ""
    if job.report_text and isinstance(job.report_text, dict):
        parts = []
        if "chapter_title" in job.report_text:
            parts.append(job.report_text.get("chapter_title", ""))
        if "sections" in job.report_text and isinstance(job.report_text["sections"], list):
            for sec in job.report_text["sections"]:
                parts.append(sec.get("heading", ""))
                parts.append(sec.get("text", ""))
        else:
            for v in job.report_text.values():
                if isinstance(v, str): parts.append(v)
        report_text = "\n\n".join(filter(None, parts))
        
    if not report_text and job.chapter_texts and isinstance(job.chapter_texts, dict):
        report_text = job.chapter_texts.get("full_text", "")
    
    if not report_text:
        raise HTTPException(400, "Analysis report text is missing. Cannot generate presentation.")

    def build_slides_with_ai():
        if not getattr(settings, "ANTHROPIC_API_KEY", None):
            # Fallback to a mock presentation for testing if no API key is provided
            return [
                {
                    "title": "Introduction",
                    "bullets": ["This is a mock slide", "AI key is not configured", "Testing presentation generation"],
                    "speaker_notes": "Welcome to the mock presentation."
                },
                {
                    "title": "Analysis Results",
                    "bullets": ["Mock data point 1", "Mock data point 2"],
                    "speaker_notes": "These are the mock results."
                }
            ], {
                "total_input_tokens": 100,
                "total_output_tokens": 50,
                "total_tokens": 150,
                "call_count": 1
            }

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        prompt = f"Convert the following analysis report into a presentation slide deck.\n"
        prompt += f"Output ONLY valid JSON containing an array of slide objects.\n"
        prompt += f"Each object MUST have: 'title' (string), 'bullets' (array of short strings), and 'speaker_notes' (string).\n\n"
        prompt += f"Report:\n{report_text[:15000]}\n"

        model = "claude-3-5-sonnet-20240620"
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            
            # Extract JSON
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                slides_data = json.loads(match.group(0))
            else:
                slides_data = json.loads(text)
                
            usage = getattr(response, "usage", None)
            inp = getattr(usage, "input_tokens", 0) if usage else 0
            out = getattr(usage, "output_tokens", 0) if usage else 0
        except Exception as e:
            print(f"Anthropic API Error: {e}. Falling back to mock presentation.")
            slides_data = [
                {
                    "title": "Introduction",
                    "bullets": ["This is a mock slide (AI Generation Failed)", f"Error: {e}", "Testing presentation generation"],
                    "speaker_notes": "Welcome to the mock presentation."
                },
                {
                    "title": "Analysis Results",
                    "bullets": ["Mock data point 1", "Mock data point 2"],
                    "speaker_notes": "These are the mock results."
                }
            ]
            inp, out = 100, 50
        
        return slides_data, {
            "total_input_tokens": inp,
            "total_output_tokens": out,
            "total_tokens": inp + out,
            "call_count": 1
        }

    try:
        slides_data, llm_usage = await run_in_threadpool(build_slides_with_ai)

        prs = Presentation()
        
        # Title Slide
        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        title_topic = "Analysis Presentation"
        if job.project_brief and isinstance(job.project_brief, dict):
            title_topic = job.project_brief.get("topic") or "Analysis Presentation"
        title.text = title_topic
        subtitle.text = f"Generated by DataNest AI\nJob ID: {job.id[:8]}"

        # Generated Slides
        bullet_slide_layout = prs.slide_layouts[1]
        for slide_data in slides_data:
            slide = prs.slides.add_slide(bullet_slide_layout)
            shapes = slide.shapes
            title_shape = shapes.title
            body_shape = shapes.placeholders[1]
            
            title_shape.text = slide_data.get('title', 'Slide')
            tf = body_shape.text_frame
            for bullet in slide_data.get('bullets', []):
                p = tf.add_paragraph()
                p.text = str(bullet)
                p.level = 0
            
            # Add speaker notes
            notes_slide = slide.notes_slide
            text_frame = notes_slide.notes_text_frame
            text_frame.text = slide_data.get('speaker_notes', '')
                
        # Charts
        if job.chart_paths:
            for path in job.chart_paths:
                if os.path.exists(path):
                    blank_slide_layout = prs.slide_layouts[6]
                    slide = prs.slides.add_slide(blank_slide_layout)
                    try:
                        slide.shapes.add_picture(path, Inches(1), Inches(1), width=Inches(8))
                    except Exception:
                        pass # Ignore invalid images

        temp_dir = tempfile.mkdtemp()
        pptx_path = os.path.join(temp_dir, f"presentation_{job_id}.pptx")
        prs.save(pptx_path)
        
        job.presentation_path = pptx_path
        job.presentation_llm_usage = llm_usage
        await db.commit()
        return {"status": "generated"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Error generating presentation: {str(e)}")

@router.post("/jobs/{job_id}/presentation/unlock")
async def unlock_presentation(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from services.credits import deduct_credits_sync, InsufficientCreditsError

    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    await _assert_job_access(job, user, db)

    if job.presentation_paid:
        return {"unlocked": True}

    from services.credits import billing_breakdown
    from api.models.database import SystemSettings
    required = Decimal("0.00")
    if job.presentation_llm_usage:
        settings_result = await db.execute(select(SystemSettings).where(SystemSettings.key == "credit_markup_multiplier"))
        markup_setting = settings_result.scalar_one_or_none()
        markup_multiplier = float(markup_setting.value) if markup_setting else settings.CREDIT_MARKUP_MULTIPLIER
        required = Decimal(str(billing_breakdown(job.presentation_llm_usage, markup_multiplier=markup_multiplier)["credits_required"]))
        
    engine = create_engine(settings.SYNC_DATABASE_URL)
    with Session(engine) as sync_db:
        sync_job = sync_db.get(AnalysisJob, job_id)
        try:
            deduct_credits_sync(sync_db, user.id, required, job_id, f"Presentation Unlock — {job_id[:8]}")
        except InsufficientCreditsError as exc:
            raise HTTPException(402, detail={"message": "Insufficient credits", "balance": exc.balance, "required": exc.required})
        sync_job.presentation_paid = True
        sync_db.commit()

    job.presentation_paid = True
    await db.commit()
    return {"unlocked": True}

@router.get("/jobs/{job_id}/presentation/download")
async def download_presentation(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job or not job.presentation_path or not os.path.exists(job.presentation_path):
        raise HTTPException(404, "Presentation not found or not generated")
    await _assert_job_access(job, user, db)

    if not job.presentation_paid:
        raise HTTPException(402, "Please unlock the presentation first")

    return FileResponse(
        job.presentation_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"Presentation_{job_id[:8]}.pptx"
    )

# ─── Report download ──────────────────────────────────────────────────
@router.get("/jobs/{job_id}/report")
async def download_report(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from api.models.database import SystemSettings

    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job or not job.report_path:
        raise HTTPException(404, "Report not ready")
    await _assert_job_access(job, user, db)
    if job.status != JobStatus.complete:
        raise HTTPException(400, "Analysis is not complete yet")
    if not os.path.exists(job.report_path):
        raise HTTPException(404, "Report file not found on disk")

    if not job.report_paid:
        settings_result = await db.execute(select(SystemSettings).where(SystemSettings.key == "base_operations_cost"))
        op_cost_setting = settings_result.scalar_one_or_none()
        base_operations_cost = Decimal(op_cost_setting.value) if op_cost_setting else Decimal("5.00")
        
        ai_cost = credits_from_llm_usage(job.llm_usage)
        required = ai_cost + base_operations_cost
        
        engine = create_engine(settings.SYNC_DATABASE_URL)
        with Session(engine) as sync_db:
            sync_job = sync_db.get(AnalysisJob, job_id)
            if not sync_job.report_paid:
                try:
                    deduct_credits_sync(
                        sync_db,
                        user.id,
                        required,
                        job_id,
                        f"Chapter 4 report — job {job_id[:8]}",
                    )
                except InsufficientCreditsError as exc:
                    raise HTTPException(
                        status_code=402,
                        detail={
                            "message": "Insufficient analysis credits",
                            "balance": exc.balance,
                            "required": exc.required,
                        },
                    ) from exc
                sync_job.report_paid = True
                sync_job.credits_charged = required
                if not sync_job.credits_estimated:
                    sync_job.credits_estimated = required
                sync_db.commit()
        job.report_paid = True
        job.credits_charged = required

    import re
    brief_data = job.project_brief or {}
    topic_raw = brief_data.get("topic") or brief_data.get("research_goal") or "Report"
    topic_slug = re.sub(r'[^a-zA-Z0-9]+', '_', topic_raw)[:40].strip('_')

    return FileResponse(
        job.report_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{topic_slug}_Chapter4.docx",
    )

@router.get("/jobs/{job_id}/report/raw")
async def download_raw_report(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from analysis.pipeline import _build_raw_document
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Report not ready")
    await _assert_job_access(job, user, db)
    if job.status != JobStatus.complete:
        raise HTTPException(400, "Analysis is not complete yet")
    if not job.report_paid:
        raise HTTPException(402, "Please unlock the analysis first")

    import re
    brief_data = job.project_brief or {}
    topic_raw = brief_data.get("topic") or brief_data.get("research_goal") or "Report"
    topic_slug = re.sub(r'[^a-zA-Z0-9]+', '_', topic_raw)[:40].strip('_')
    raw_path = _build_raw_document(job.results or {}, job.chart_paths or [], str(job.id), brief_data)
    return FileResponse(
        raw_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{topic_slug}_RawOutput.docx",
    )

@router.get("/jobs/{job_id}/report/raw/pdf")
async def download_raw_report_pdf(job_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from analysis.pipeline import _build_raw_pdf
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Report not ready")
    await _assert_job_access(job, user, db)
    if job.status != JobStatus.complete:
        raise HTTPException(400, "Analysis is not complete yet")
    if not job.report_paid:
        raise HTTPException(402, "Please unlock the analysis first")

    import re
    brief_data = job.project_brief or {}
    topic_raw = brief_data.get("topic") or brief_data.get("research_goal") or "Report"
    topic_slug = re.sub(r'[^a-zA-Z0-9]+', '_', topic_raw)[:40].strip('_')
    pdf_path = _build_raw_pdf(job.results or {}, job.chart_paths or [], str(job.id), brief_data)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{topic_slug}_RawOutput.pdf",
    )



@router.get("/jobs/{job_id}/charts/{index}")
async def get_chart(job_id: str, index: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job or not job.chart_paths or index >= len(job.chart_paths):
        print("GET CHART 404 reason: invalid index or empty chart_paths", job.chart_paths if job else "no job")
        raise HTTPException(404)
    raw_path = job.chart_paths[index]
    resolved_path = None
    if raw_path and os.path.exists(raw_path):
        resolved_path = raw_path
    else:
        fname = os.path.basename(raw_path) if raw_path else ""
        candidates = [
            os.path.join(settings.CHARTS_DIR, str(job_id), fname),
            os.path.join("storage", "charts", str(job_id), fname),
            os.path.abspath(os.path.join("storage", "charts", str(job_id), fname)),
            os.path.join(settings.CHARTS_DIR, fname),
            os.path.join("storage", "charts", fname),
        ]
        for c in candidates:
            if os.path.exists(c):
                resolved_path = c
                break

    if not resolved_path or not os.path.exists(resolved_path):
        print(f"GET CHART 404 for job {job_id} index {index}, tried: {raw_path}")
        raise HTTPException(404)
    return FileResponse(resolved_path, media_type="image/png")

# ─── Background pipeline runner ───────────────────────────────────────
def _run_pipeline(job_id: str, file_path: str = None):
    """Runs stages 1-2 (assembly + clean + inspect + decode), then pauses for review."""
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine

    engine = create_engine(settings.SYNC_DATABASE_URL)
    with Session(engine) as db:
        job = db.get(AnalysisJob, job_id)
        if not job:
            return

        try:
            # ── Stage 1a: Assemble ────────────────────────────────────
            job.status = "assembling"
            db.commit()

            # Load raw dataframe for cleaning
            raw_df = None
            if job.source_type == "survey_db" and job.survey_id:
                import pandas as pd
                survey = db.get(Survey, job.survey_id)
                from api.models.database import Question, Response
                questions = db.query(Question).filter(Question.survey_id == job.survey_id).order_by(Question.position).all()
                responses = db.query(Response).filter(Response.survey_id == job.survey_id).all()
                qs_non_header = [q for q in questions if q.type != "section_header"]
                
                rows = []
                for resp in responses:
                    row = {"response_id": resp.id, "submitted_at": str(resp.submitted_at)}
                    answers = resp.answers
                    from analysis.decode.parsers.db_parser import answer_value
                    for q in qs_non_header:
                        val = answer_value(answers, q.id)
                        if val is None:
                            val = ""
                        elif isinstance(val, dict):
                            val = "; ".join(f"{k}: {v}" for k, v in val.items())
                        elif isinstance(val, list):
                            val = "; ".join(str(v) for v in val)
                        row[q.variable_name or f"q{questions.index(q)+1}"] = val
                    rows.append(row)
                raw_df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["response_id", "submitted_at"] + [q.variable_name or f"q{questions.index(q)+1}" for q in qs_non_header])
            elif file_path and os.path.exists(file_path):
                try:
                    import pandas as pd
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in (".xlsx", ".xls"):
                        raw_df = pd.read_excel(file_path)
                    elif ext == ".csv":
                        raw_df = pd.read_csv(file_path)
                    elif ext == ".sav":
                        try:
                            import pyreadstat
                            raw_df, _ = pyreadstat.read_sav(file_path)
                        except Exception:
                            raw_df = None
                except Exception:
                    raw_df = None

            # ── Stage 1b: Profile (read-only inspect, no changes yet) ──────
            job.status = "inspecting"
            db.commit()

            cleaned_df = raw_df  # default: use raw if no cleaning occurs
            if raw_df is not None:
                try:
                    from analysis.cleaner import profile_only, auto_clean, manual_clean
                    inspection_report = profile_only(raw_df)
                    job.inspection_report = inspection_report
                    db.commit()
                except Exception as profile_err:
                    job.inspection_report = {"error": str(profile_err)}
                    db.commit()

                # ── Stage 1c: Pause — wait for user preprocessing choice ────
                job.status = "awaiting_preprocessing_choice"
                db.commit()

                import time
                from sqlalchemy import text as sa_text
                timeout_seconds = 86400  # 24-hour timeout
                elapsed = 0
                poll_interval = 5
                preprocessing_mode = None
                manual_choices_val = {}

                while elapsed < timeout_seconds:
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                    # Commit any open transaction so the next read starts fresh
                    # and can see writes made by other connections (fixes SQLite isolation)
                    db.commit()
                    # Bypass ORM identity map — read directly from DB
                    row = db.execute(
                        sa_text("SELECT preprocessing_mode, manual_choices FROM analysis_jobs WHERE id = :id"),
                        {"id": job_id}
                    ).fetchone()
                    if row and row[0] is not None and str(row[0]).strip() != "":
                        preprocessing_mode = str(row[0])
                        import json
                        try:
                            manual_choices_val = json.loads(row[1]) if row[1] else {}
                        except Exception:
                            manual_choices_val = {}
                        break

                if preprocessing_mode is None:
                    raise ValueError("Preprocessing choice timed out after 24 hours")

                # Sync the values back onto the job object
                job.preprocessing_mode = preprocessing_mode
                job.manual_choices = manual_choices_val


                # ── Stage 1d: Apply chosen cleaning strategy ────────────────
                job.status = "cleaning"
                db.commit()

                try:
                    choices = job.manual_choices or {}
                    if job.preprocessing_mode == "auto":
                        inspection_report = job.inspection_report or {}
                        cleaned_df, cleaning_summary = auto_clean(raw_df, inspection_report)
                    else:
                        cleaned_df, cleaning_summary = manual_clean(raw_df, choices)

                    job.cleaning_summary = cleaning_summary
                    db.commit()

                    # Overwrite uploaded file with cleaned version for decode stage
                    if file_path:
                        ext = os.path.splitext(file_path)[1].lower()
                        try:
                            if ext in (".xlsx", ".xls"):
                                cleaned_df.to_excel(file_path, index=False)
                            elif ext == ".csv":
                                cleaned_df.to_csv(file_path, index=False)
                        except Exception:
                            pass
                except Exception as clean_err:
                    job.cleaning_summary = {"error": str(clean_err), "cleaned": False, "actions_taken": []}
                    db.commit()
            else:
                job.inspection_report = {}
                job.cleaning_summary = {"cleaned": False, "actions_taken": []}
                db.commit()

            # ── Stage 2: Decode ───────────────────────────────────────
            job.status = "decoding"
            db.commit()

            from analysis.decode import decode_file, decode_from_db
            from analysis.decode.dictionary.builder import to_json_serializable
            from analysis.llm_usage import start_job_tracking, end_job_tracking
            from services.credits import credits_from_llm_usage, deduct_credits_sync

            # Track LLM usage specifically for decoding
            start_job_tracking(job.id)

            if file_path and os.path.exists(file_path):
                result = decode_file(file_path, job_id=job.id, user_id=job.user_id)
            elif job.survey_id:
                result = decode_from_db(job.survey_id, db, job_id=job.id, user_id=job.user_id)
            else:
                raise ValueError("No data source available")

            job.data_dictionary = to_json_serializable(result["data_dictionary"])
            job.decode_warnings = to_json_serializable(result["warnings"])
            job.n_rows = result["n_rows"]
            job.n_columns = result["n_columns"]
            job.n_complete_rows = result["n_complete_rows"]
            job.decode_completed_at = datetime.utcnow()
            job.status = "decode_review"
            db.commit()

            # Save LLM usage from decoding so it can be combined with analysis phase
            usage = end_job_tracking(job.id)
            if usage and usage.total_tokens > 0:
                job.llm_usage = to_json_serializable(usage.to_dict())
                db.commit()

        except Exception as e:
            import traceback
            traceback.print_exc()
            from analysis.error_manager import format_user_friendly_error
            try:
                db.rollback()
            except Exception:
                pass
            try:
                job = db.get(AnalysisJob, job_id)
                if job:
                    job.status = "failed"
                    job.error_message = format_user_friendly_error(e)
                    db.commit()
            except Exception:
                pass

def _continue_pipeline(job_id: str):
    """Continues from stage 3 after researcher approves decode."""
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine

    engine = create_engine(settings.SYNC_DATABASE_URL)
    with Session(engine) as db:
        job = db.get(AnalysisJob, job_id)
        if not job:
            return

        try:
            from analysis.llm_usage import start_job_tracking
            from analysis.pipeline import run_stages_3_to_9
            start_job_tracking(job_id, previous_usage_dict=job.llm_usage)
            run_stages_3_to_9(job, db)
        except Exception as e:
            import traceback
            traceback.print_exc()
            from analysis.error_manager import format_user_friendly_error
            try:
                db.rollback()
            except Exception:
                pass
            try:
                job = db.get(AnalysisJob, job_id)
                if job:
                    job.status = "failed"
                    job.error_message = format_user_friendly_error(e)
                    db.commit()
            except Exception:
                pass


# ─── Lightweight status endpoint (Phase 3C) ───────────────────────────────────────
@router.get("/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Tiny fast endpoint for frontend polling.
    Returns only status + error_message — no big data_dictionary / results payload.
    Used by the global analysisStore poller that runs across all pages.
    """
    result = await db.execute(
        select(AnalysisJob.id, AnalysisJob.status, AnalysisJob.error_message)
        .where(AnalysisJob.id == job_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Job not found")
    return {"id": row[0], "status": row[1], "error": row[2]}


# ─── Queue stats endpoint (observability) ──────────────────────────────────────
@router.get("/queue/stats")
async def queue_stats(user: User = Depends(get_current_user)):
    """Returns current process-pool queue depth and worker counts."""
    from workers.queue import queue_stats as _stats
    return _stats()


# ── AI Variable Advisor ──────────────────────────────────────────────────────
@router.post("/variable-advisor")
async def variable_advisor(request: Request, current_user=Depends(get_current_user)):
    """
    Reads the full research brief (RQs, hypotheses, objectives, topic, population)
    and returns AI-suggested dependent/independent/control variables with reasoning.
    Falls back to heuristic extraction if Claude is unavailable.
    """
    import re as _re
    body = await request.json()
    brief = body.get("brief", {})

    topic       = brief.get("topic", "").strip()
    population  = brief.get("population", "").strip()
    rqs         = [q for q in brief.get("research_questions", []) if q.strip()]
    hypotheses  = [h for h in brief.get("hypotheses", [])          if h.strip()]
    objectives  = [o for o in brief.get("objectives", [])          if o.strip()]

    # ── Heuristic extraction (always runs as base) ───────────────────────────
    def extract_heuristic():
        dv_candidates, iv_candidates = [], []

        patterns_dv = [
            r"difference in ([\w\s]+?) between",
            r"effect (?:of .+? )?on ([\w\s]+)",
            r"impact (?:of .+? )?on ([\w\s]+)",
            r"predict ([\w\s]+)",
            r"relationship between .+? and ([\w\s]+)",
            r"association between .+? and ([\w\s]+)",
        ]
        patterns_iv = [
            r"difference in .+? between ([\w\s]+?) and ([\w\s]+?)(?:\?|$|\s)",
            r"effect of ([\w\s]+?) on",
            r"impact of ([\w\s]+?) on",
            r"relationship between ([\w\s]+?) and",
            r"association between ([\w\s]+?) and",
            r"influence of ([\w\s]+?) on",
        ]

        all_text = " ".join(rqs + hypotheses + objectives).lower()

        for pat in patterns_dv:
            m = _re.search(pat, all_text)
            if m:
                candidate = m.group(1).strip().title()
                if candidate and len(candidate) > 2:
                    dv_candidates.append(candidate)
                    break

        for pat in patterns_iv:
            m = _re.search(pat, all_text)
            if m:
                candidate = m.group(1).strip().title()
                if candidate and len(candidate) > 2:
                    iv_candidates.append(candidate)
                    break

        return dv_candidates, iv_candidates

    heuristic_dv, heuristic_iv = extract_heuristic()

    # ── Try Claude AI for rich contextual suggestions ────────────────────────
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("No API key")

        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""You are an expert research statistician helping a student identify their variables.

RESEARCH BRIEF:
Topic: {topic}
Target Population: {population}
Research Questions:
{chr(10).join(f"  RQ{i+1}: {q}" for i,q in enumerate(rqs)) if rqs else "  Not specified"}

Hypotheses:
{chr(10).join(f"  H{i+1}: {h}" for i,h in enumerate(hypotheses)) if hypotheses else "  Not specified"}

Objectives:
{chr(10).join(f"  {i+1}. {o}" for i,o in enumerate(objectives)) if objectives else "  Not specified"}

TASK: Identify the research variables and explain WHY each one was chosen.
Return a JSON object with exactly this structure:
{{
  "dependent_variable": {{
    "name": "variable name as it appears in data",
    "why": "1-2 sentence clear explanation of why this is the outcome variable",
    "scale": "continuous|ordinal|nominal|binary",
    "example_column_names": ["GPA", "Score", "AcademicPerformance"]
  }},
  "independent_variable": {{
    "name": "variable name",
    "why": "1-2 sentence explanation",
    "scale": "continuous|ordinal|nominal|binary",
    "n_groups": 2,
    "example_column_names": ["Gender", "Sex"]
  }},
  "control_variables": [
    {{"name": "...", "why": "..."}}
  ],
  "implied_test": "Independent-samples t-test",
  "implied_test_reason": "Because we have a continuous DV (GPA) and a categorical IV with 2 groups (Gender), the appropriate test is an independent-samples t-test.",
  "confidence": "high|medium|low",
  "advice": "One encouraging sentence of advice for the student"
}}

Return ONLY valid JSON. No markdown, no explanation outside JSON.
"""

        msg = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        import json as _json
        raw = msg.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = _re.sub(r"^```[a-zA-Z]*\s*", "", raw)
            raw = _re.sub(r"\s*```$", "", raw)
        result = _json.loads(raw)
        result["source"] = "ai"
        return result

    except Exception as e:
        # Graceful fallback — return heuristic result
        pass

    # ── Fallback: heuristic result + decision engine ────────────────────────
    dv_name = heuristic_dv[0] if heuristic_dv else ""
    iv_name = heuristic_iv[0] if heuristic_iv else ""

    # Normalize common gender/demographic grouping terms
    if iv_name.lower() in ("male", "female", "men", "women", "boys", "girls", "gender", "sex"):
        iv_name = "Gender"

    implied_test = "To be determined — add your variables above to get a test suggestion."
    implied_reason = ""
    
    if dv_name and iv_name:
        try:
            from analysis.test_decision_engine import decide_test, GroupingVariable
            first_rq = rqs[0] if rqs else f"Comparing {dv_name} across {iv_name}"
            dt_res = decide_test(
                research_question=first_rq,
                outcome_type="continuous",
                predictor_type="categorical",
                grouping_variables=[GroupingVariable(iv_name, 2)]
            )
            implied_test = dt_res.recommended_test
            implied_reason = f"Continuous outcome ({dv_name}) evaluated across groups ({iv_name}) leads to {dt_res.recommended_test} ({dt_res.effect_size_metric})."
        except Exception as dt_err:
            implied_test = "Independent-samples t-test"
            implied_reason = f"Comparing continuous outcome '{dv_name}' between categories of '{iv_name}'."

    return {
        "dependent_variable": {
            "name": dv_name,
            "why": (
                f"Based on your research question, '{dv_name}' is the outcome "
                "you are measuring or comparing across groups."
                if dv_name else
                "Could not automatically detect — please enter your outcome variable manually."
            ),
            "scale": "continuous",
            "example_column_names": [dv_name] if dv_name else [],
        },
        "independent_variable": {
            "name": iv_name,
            "why": (
                f"'{iv_name}' appears to be the grouping or predictor variable "
                "that explains or influences your outcome."
                if iv_name else
                "Could not automatically detect — please enter your predictor variable manually."
            ),
            "scale": "nominal",
            "n_groups": 2,
            "example_column_names": [iv_name] if iv_name else [],
        },
        "control_variables": [],
        "implied_test": implied_test,
        "implied_test_reason": implied_reason,
        "confidence": "low" if not (dv_name and iv_name) else "medium",
        "advice": (
            "Fill in your research questions and hypotheses in Step 3 for better suggestions."
            if not rqs else
            "Review these suggestions and adjust if needed — you know your study best!"
        ),
        "source": "heuristic",
    }

