# backend/api/routers/responses.py — public respondent endpoints
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Any, Dict, Optional
import uuid, shutil, os
from datetime import datetime

from api.deps import get_db
from api.models.database import Survey, Question, Response, SurveyStatus

router = APIRouter()

@router.get("/surveys/{slug}")
async def get_public_survey(slug: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Survey).where(Survey.slug == slug))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404, "Survey not found")
    if s.status != SurveyStatus.active: raise HTTPException(410, "Survey is no longer active")
    qr = await db.execute(select(Question).where(Question.survey_id == s.id).order_by(Question.position))
    qs = qr.scalars().all()
    return {
        "survey": {
            "id": s.id, "title": s.title, "description": s.description,
            "slug": s.slug, "require_email": s.require_email,
            "allow_multiple": s.allow_multiple,
            "theme": s.theme or {}
        },
        "questions": [
            {
                "id": q.id, "type": q.type, "text": q.text, "required": q.required,
                "options": q.options, "scale_min": q.scale_min, "scale_max": q.scale_max,
                "rows": q.rows, "columns": q.columns,
                # Advanced quality-control fields (safe to expose to respondent)
                "helper_text": q.helper_text,
                "randomize_options": q.randomize_options or False,
                "validation_rules": q.validation_rules or {},
                "logic_rules": q.logic_rules or [],
                # NOTE: is_attention_check is intentionally NOT exposed so respondents can't detect it
            }
            for q in qs
        ]
    }

class SubmitRequest(BaseModel):
    answers: Dict[str, Any]
    participant_email: Optional[str] = None

@router.post("/surveys/{slug}/respond")
async def submit_response(slug: str, data: SubmitRequest, request: Request, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Survey).where(Survey.slug == slug))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404, "Survey not found")
    if s.status != SurveyStatus.active: raise HTTPException(410, "Survey closed")

    # Check for duplicate submissions if email required
    if not s.allow_multiple and s.require_email:
        if not data.participant_email:
            raise HTTPException(400, "Participant email is required for this survey")
        dup_check = await db.execute(
            select(Response).where(
                Response.survey_id == s.id,
                Response.participant_email == data.participant_email
            )
        )
        if dup_check.scalar_one_or_none():
            raise HTTPException(409, "You have already submitted this survey.")

    # ── Evaluate attention checks ────────────────────────────────
    qr = await db.execute(
        select(Question).where(
            Question.survey_id == s.id,
            Question.is_attention_check == True
        )
    )
    attention_qs = qr.scalars().all()
    failed_check_ids = []
    for aq in attention_qs:
        respondent_answer = data.answers.get(str(aq.id))
        expected = aq.correct_answer
        if expected is not None and respondent_answer != expected:
            failed_check_ids.append(str(aq.id))

    flags = {
        "attention_check_failed": len(failed_check_ids) > 0,
        "failed_check_ids": failed_check_ids,
    }

    resp = Response(
        id=str(uuid.uuid4()), survey_id=s.id, answers=data.answers,
        participant_email=data.participant_email,
        submitted_at=datetime.utcnow(),
        ip_address=request.client.host if request.client else None,
        flags=flags,
    )
    db.add(resp)
    await db.commit()
    return {"submitted": True, "response_id": resp.id, "flagged": flags["attention_check_failed"]}


@router.post("/surveys/{slug}/upload-file")
async def upload_response_file(
    slug: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a file for a file_upload question response.
    Accepts images, PDFs, audio, and common document formats.
    Returns a public URL for storage in the answer payload.
    """
    r = await db.execute(select(Survey).where(Survey.slug == slug))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404, "Survey not found")
    if s.status != SurveyStatus.active: raise HTTPException(410, "Survey closed")

    allowed_mime = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml',
        'application/pdf',
        'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp4',
        'video/mp4', 'video/webm',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
    }
    content_type = file.content_type or ''
    if content_type not in allowed_mime:
        raise HTTPException(400, f"File type '{content_type}' is not allowed.")

    # 20 MB limit
    MAX_SIZE = 20 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(413, "File exceeds 20 MB limit.")

    upload_dir = os.path.join('storage', 'uploads', 'responses')
    os.makedirs(upload_dir, exist_ok=True)

    ext = (file.filename or 'upload').rsplit('.', 1)[-1].lower() or 'bin'
    filename = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, 'wb') as buf:
        buf.write(contents)

    return {
        "url": f"/storage/uploads/responses/{filename}",
        "filename": file.filename,
        "size": len(contents),
        "content_type": content_type,
    }
