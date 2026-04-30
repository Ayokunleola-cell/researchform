# backend/api/routers/surveys.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
import uuid, random, string

from api.deps import get_db, get_current_user
from api.models.database import Survey, Question, Response, SurveyStatus
from api.models.database import User

router = APIRouter()

def make_slug(n=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def q_type_level(t):
    return {"short_text":"nominal","long_text":"nominal","single_choice":"nominal","multi_choice":"nominal",
            "likert":"ordinal","rating":"ordinal","matrix":"ordinal","number":"ratio","date":"interval"}.get(t,"nominal")

def survey_out(s, rc=0, qc=0):
    return {"id":s.id,"title":s.title,"description":s.description,"project_brief":s.project_brief,
            "slug":s.slug,"status":s.status,"response_count":rc,"question_count":qc,
            "response_limit":s.response_limit,"closes_at":str(s.closes_at) if s.closes_at else None,
            "created_at":str(s.created_at),"updated_at":str(s.updated_at),"user_id":s.user_id}

def q_out(q):
    return {"id":q.id,"survey_id":q.survey_id,"position":q.position,"type":q.type,"text":q.text,
            "required":q.required,"options":q.options,"scale_min":q.scale_min,"scale_max":q.scale_max,
            "variable_name":q.variable_name,"measurement_level":q.measurement_level,
            "rows":q.rows,"columns":q.columns}

async def check_owner(sid, user, db):
    r = await db.execute(select(Survey).where(Survey.id==sid, Survey.user_id==user.id))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404,"Survey not found")
    return s

class SurveyCreate(BaseModel):
    title:str; description:str=""; project_brief:dict={}; status:str="draft"
    response_limit:Optional[int]=None; closes_at:Optional[str]=None

class SurveyPatch(BaseModel):
    title:Optional[str]=None; description:Optional[str]=None; project_brief:Optional[dict]=None
    status:Optional[str]=None; response_limit:Optional[int]=None; closes_at:Optional[str]=None

class QuestionCreate(BaseModel):
    type:str; text:str=""; required:bool=True; options:List[Any]=[]; scale_min:int=1; scale_max:int=5
    variable_name:Optional[str]=None; measurement_level:Optional[str]=None; position:int=0
    rows:List[str]=[]; columns:List[str]=[]

class QuestionPatch(BaseModel):
    text:Optional[str]=None; required:Optional[bool]=None; options:Optional[List[Any]]=None
    scale_min:Optional[int]=None; scale_max:Optional[int]=None; variable_name:Optional[str]=None
    measurement_level:Optional[str]=None; position:Optional[int]=None
    rows:Optional[List[str]]=None; columns:Optional[List[str]]=None

@router.get("") 
async def list_surveys(db=Depends(get_db), user=Depends(get_current_user)):
    r = await db.execute(select(Survey).where(Survey.user_id==user.id).order_by(Survey.created_at.desc()))
    out=[]
    for s in r.scalars().all():
        rc=(await db.execute(select(func.count(Response.id)).where(Response.survey_id==s.id))).scalar()
        qc=(await db.execute(select(func.count(Question.id)).where(Question.survey_id==s.id))).scalar()
        out.append(survey_out(s,rc,qc))
    return out

@router.post("")
async def create_survey(data:SurveyCreate, db=Depends(get_db), user=Depends(get_current_user)):
    slug=make_slug()
    while (await db.execute(select(Survey).where(Survey.slug==slug))).scalar_one_or_none(): slug=make_slug()
    s=Survey(id=str(uuid.uuid4()),user_id=user.id,title=data.title,description=data.description,
             project_brief=data.project_brief,slug=slug,status=data.status,response_limit=data.response_limit)
    db.add(s); await db.commit(); await db.refresh(s)
    return survey_out(s)

@router.get("/{sid}")
async def get_survey(sid:str, db=Depends(get_db), user=Depends(get_current_user)):
    s=await check_owner(sid,user,db)
    rc=(await db.execute(select(func.count(Response.id)).where(Response.survey_id==sid))).scalar()
    qc=(await db.execute(select(func.count(Question.id)).where(Question.survey_id==sid))).scalar()
    return survey_out(s,rc,qc)

@router.patch("/{sid}")
async def update_survey(sid:str, data:SurveyPatch, db=Depends(get_db), user=Depends(get_current_user)):
    s=await check_owner(sid,user,db)
    for f,v in data.dict(exclude_none=True).items(): setattr(s,f,v)
    s.updated_at=datetime.utcnow(); await db.commit(); await db.refresh(s)
    return survey_out(s)

@router.delete("/{sid}")
async def delete_survey(sid:str, db=Depends(get_db), user=Depends(get_current_user)):
    s=await check_owner(sid,user,db); await db.delete(s); await db.commit(); return {"deleted":True}

@router.post("/{sid}/publish")
async def publish(sid:str, db=Depends(get_db), user=Depends(get_current_user)):
    s=await check_owner(sid,user,db); s.status=SurveyStatus.active; s.updated_at=datetime.utcnow()
    await db.commit(); return survey_out(s)

@router.post("/{sid}/close")
async def close_survey(sid:str, db=Depends(get_db), user=Depends(get_current_user)):
    s=await check_owner(sid,user,db); s.status=SurveyStatus.closed; s.updated_at=datetime.utcnow()
    await db.commit(); return survey_out(s)

@router.get("/{sid}/stats")
async def stats(sid:str, db=Depends(get_db), user=Depends(get_current_user)):
    await check_owner(sid,user,db)
    rc=(await db.execute(select(func.count(Response.id)).where(Response.survey_id==sid))).scalar()
    qc=(await db.execute(select(func.count(Question.id)).where(Question.survey_id==sid))).scalar()
    return {"response_count":rc,"question_count":qc,"completion_rate":100,"avg_duration":"—"}

@router.get("/{sid}/responses")
async def responses(sid:str, db=Depends(get_db), user=Depends(get_current_user)):
    await check_owner(sid,user,db)
    r=await db.execute(select(Response).where(Response.survey_id==sid).order_by(Response.submitted_at.desc()))
    return [{"id":x.id,"answers":x.answers,"submitted_at":str(x.submitted_at)} for x in r.scalars().all()]

@router.get("/{sid}/questions")
async def list_questions(sid:str, db=Depends(get_db), user=Depends(get_current_user)):
    await check_owner(sid,user,db)
    r=await db.execute(select(Question).where(Question.survey_id==sid).order_by(Question.position))
    return [q_out(q) for q in r.scalars().all()]

@router.post("/{sid}/questions")
async def create_question(sid:str, data:QuestionCreate, db=Depends(get_db), user=Depends(get_current_user)):
    await check_owner(sid,user,db)
    ml=data.measurement_level or q_type_level(data.type)
    vn=data.variable_name or f"q{data.position+1}_{data.type[:5]}"
    q=Question(id=str(uuid.uuid4()),survey_id=sid,type=data.type,text=data.text,required=data.required,
               options=data.options,scale_min=data.scale_min,scale_max=data.scale_max,
               variable_name=vn,measurement_level=ml,position=data.position,rows=data.rows,columns=data.columns)
    db.add(q); await db.commit(); await db.refresh(q); return q_out(q)

@router.patch("/{sid}/questions/{qid}")
async def update_question(sid:str, qid:str, data:QuestionPatch, db=Depends(get_db), user=Depends(get_current_user)):
    await check_owner(sid,user,db)
    r=await db.execute(select(Question).where(Question.id==qid,Question.survey_id==sid))
    q=r.scalar_one_or_none()
    if not q: raise HTTPException(404,"Question not found")
    for f,v in data.dict(exclude_none=True).items(): setattr(q,f,v)
    await db.commit(); await db.refresh(q); return q_out(q)

@router.delete("/{sid}/questions/{qid}")
async def delete_question(sid:str, qid:str, db=Depends(get_db), user=Depends(get_current_user)):
    await check_owner(sid,user,db)
    r=await db.execute(select(Question).where(Question.id==qid,Question.survey_id==sid))
    q=r.scalar_one_or_none()
    if not q: raise HTTPException(404)
    await db.delete(q); await db.commit(); return {"deleted":True}

@router.post("/{sid}/questions/reorder")
async def reorder(sid:str, body:dict, db=Depends(get_db), user=Depends(get_current_user)):
    await check_owner(sid,user,db)
    for i,qid in enumerate(body.get("ids",[])):
        await db.execute(update(Question).where(Question.id==qid).values(position=i))
    await db.commit(); return {"reordered":True}
