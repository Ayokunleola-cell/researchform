# backend/api/routers/responses.py — public respondent endpoints
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Any, Dict
import uuid
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
        "survey": {"id":s.id,"title":s.title,"description":s.description,"slug":s.slug},
        "questions": [{"id":q.id,"type":q.type,"text":q.text,"required":q.required,
                       "options":q.options,"scale_min":q.scale_min,"scale_max":q.scale_max,
                       "rows":q.rows,"columns":q.columns} for q in qs]
    }

class SubmitRequest(BaseModel):
    answers: Dict[str, Any]

@router.post("/surveys/{slug}/respond")
async def submit_response(slug: str, data: SubmitRequest, request: Request, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Survey).where(Survey.slug == slug))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404, "Survey not found")
    if s.status != SurveyStatus.active: raise HTTPException(410, "Survey closed")
    resp = Response(
        id=str(uuid.uuid4()), survey_id=s.id, answers=data.answers,
        submitted_at=datetime.utcnow(), ip_address=request.client.host if request.client else None
    )
    db.add(resp); await db.commit()
    return {"submitted": True, "response_id": resp.id}
