# backend/api/routers/surveys.py
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
import uuid, random, string, time

from api.deps import get_db, get_current_user
from api.models.database import Survey, Question, Response, SurveyStatus
from api.models.database import User
from config import settings

router = APIRouter()

# ── In-memory TTL cache for expensive health checks ───────────────────────────
# Key: (user_id, survey_id, check_type) → (timestamp, result_dict)
# Avoids recomputing Cronbach's α, VIF, Shapiro-Wilk on every button click.
_health_cache: dict = {}

def _cache_get(user_id: str, survey_id: str, check: str):
    key = (user_id, survey_id, check)
    entry = _health_cache.get(key)
    if entry and (time.time() - entry[0]) < settings.HEALTH_CACHE_TTL_SECONDS:
        return entry[1]
    return None

def _cache_set(user_id: str, survey_id: str, check: str, result: dict):
    _health_cache[(user_id, survey_id, check)] = (time.time(), result)

def _cache_invalidate(survey_id: str):
    """Call when survey responses change — clears all checks for that survey."""
    keys = [k for k in _health_cache if k[1] == survey_id]
    for k in keys:
        del _health_cache[k]



def make_slug(n=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def q_type_level(t):
    return {"short_text":"nominal","long_text":"nominal","single_choice":"nominal","multi_choice":"nominal",
            "dropdown":"nominal","likert":"ordinal","rating":"ordinal","matrix":"ordinal",
            "rank_order":"ordinal","nps":"ordinal","slider":"ratio","constant_sum":"ratio",
            "number":"ratio","date":"interval"}.get(t,"nominal")

# ── Measurement Level Coercion ────────────────────────────────────────────────
# Maps any user-supplied string to one of the 4 valid DB enum values.
# This is the single source of truth — called before every DB write.
_ML_ALIASES: dict = {
    # continuous / numeric variants
    "continuous": "ratio",    "numeric": "ratio",      "quantitative": "ratio",
    "scale": "ratio",         "continuous_scale": "ratio",
    # categorical / qualitative
    "categorical": "nominal", "qualitative": "nominal", "binary": "nominal",
    "dichotomous": "nominal", "dummy": "nominal",      "discrete": "nominal",
    # ranked / ordered
    "ranked": "ordinal",      "rank": "ordinal",        "likert": "ordinal",
    "ordered": "ordinal",     "ordinal_scale": "ordinal",
    # already valid (identity)
    "nominal": "nominal",     "ordinal": "ordinal",
    "interval": "interval",   "ratio": "ratio",
}
_VALID_ML = frozenset({"nominal", "ordinal", "interval", "ratio"})

def _coerce_ml(value: str | None, fallback: str = "nominal") -> str:
    """Normalize any measurement level string to a valid DB enum value.
    Never raises — always returns one of: nominal, ordinal, interval, ratio.
    """
    if not value:
        return fallback
    normalized = str(value).strip().lower()
    return _ML_ALIASES.get(normalized, normalized if normalized in _VALID_ML else fallback)

def survey_out(s, rc=0, qc=0):
    return {"id":s.id,"title":s.title,"description":s.description,"project_brief":s.project_brief,
            "slug":s.slug,"status":s.status,"response_count":rc,"question_count":qc,
            "response_limit":s.response_limit,"closes_at":str(s.closes_at) if s.closes_at else None,
            "theme":s.theme,"allow_multiple":s.allow_multiple,"require_email":s.require_email,
            "created_at":str(s.created_at),"updated_at":str(s.updated_at)}

def q_out(q):
    return {"id":q.id,"survey_id":q.survey_id,"position":q.position,"type":q.type,"text":q.text,
            "required":q.required,"options":q.options,"scale_min":q.scale_min,"scale_max":q.scale_max,
            "variable_name":q.variable_name,"measurement_level":q.measurement_level,
            "rows":q.rows,"columns":q.columns,
            "helper_text":q.helper_text,"randomize_options":q.randomize_options or False,
            "validation_rules":q.validation_rules or {},"logic_rules":q.logic_rules or [],
            "is_attention_check":q.is_attention_check or False,"correct_answer":q.correct_answer}

# ── Health Check Shared Helpers ───────────────────────────────────────────
def _is_likert(opts):
    if not opts: return False
    try:
        import json
        opts_list = json.loads(opts) if isinstance(opts, str) else opts
        opts_str = " ".join(str(o) for o in opts_list).lower()
        return any(k in opts_str for k in ["agree", "satisf", "likely", "important", "often"])
    except Exception:
        return False

def _is_numeric_scale(opts):
    if not opts: return False
    try:
        import json
        opts_list = json.loads(opts) if isinstance(opts, str) else opts
        if len(opts_list) < 2: return False
        for o in opts_list:
            float(str(o).strip())
        return True
    except Exception:
        return False

def _get_scale_columns(questions):
    from analysis.decode.parsers.db_parser import _sanitize
    meta_levels = {_sanitize(q[1] or q[0]): q[4] for q in questions}
    meta_types  = {_sanitize(q[1] or q[0]): q[2] for q in questions}
    meta_opts   = {_sanitize(q[1] or q[0]): q[5] for q in questions}
    valid_cols = []
    for col, lvl in meta_levels.items():
        qtype = meta_types.get(col)
        opts = meta_opts.get(col)
        if lvl in ("ordinal", "ratio", "interval") or qtype in ("number", "rating", "likert", "slider"):
            valid_cols.append(col)
        elif _is_likert(opts) or _is_numeric_scale(opts):
            valid_cols.append(col)
    return valid_cols

def _encode_likert_dataframe(df, questions, scale_columns):
    import json
    import pandas as pd
    from analysis.decode.parsers.db_parser import _sanitize
    df_mapped = df.copy()
    meta_opts = {_sanitize(q[1] or q[0]): q[5] for q in questions}
    for col in scale_columns:
        if col not in df_mapped.columns: continue
        opts = meta_opts.get(col)
        if opts:
            try:
                opts_list = json.loads(opts) if isinstance(opts, str) else opts
                mapping = {str(o).strip().lower(): i+1 for i, o in enumerate(opts_list)}
                if df_mapped[col].dtype == object:
                    df_mapped[col] = df_mapped[col].apply(
                        lambda x: mapping.get(str(x).strip().lower(), x) if pd.notnull(x) else x
                    )
            except Exception:
                pass
    return df_mapped

async def check_owner(sid, user, db):
    r = await db.execute(select(Survey).where(Survey.id==sid, Survey.user_id==user.id))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404,"Survey not found")
    return s

class SurveyCreate(BaseModel):
    title:str; description:str=""; project_brief:dict={}; status:str="draft"
    response_limit:Optional[int]=None; closes_at:Optional[str]=None
    theme:Optional[dict]=None; allow_multiple:Optional[bool]=None; require_email:Optional[bool]=None

class SurveyPatch(BaseModel):
    title:Optional[str]=None; description:Optional[str]=None; project_brief:Optional[dict]=None
    status:Optional[str]=None; response_limit:Optional[int]=None; closes_at:Optional[str]=None
    theme:Optional[dict]=None; allow_multiple:Optional[bool]=None; require_email:Optional[bool]=None

class QuestionCreate(BaseModel):
    type:str; text:str=""; required:bool=True; options:List[Any]=[]; scale_min:int=1; scale_max:int=5
    variable_name:Optional[str]=None; measurement_level:Optional[str]=None; position:int=0
    rows:List[str]=[]; columns:List[str]=[]
    helper_text:Optional[str]=None; randomize_options:bool=False
    validation_rules:Optional[dict]=None; logic_rules:Optional[list]=None
    is_attention_check:bool=False; correct_answer:Optional[Any]=None

class QuestionPatch(BaseModel):
    text:Optional[str]=None; required:Optional[bool]=None; options:Optional[List[Any]]=None
    scale_min:Optional[int]=None; scale_max:Optional[int]=None; variable_name:Optional[str]=None
    measurement_level:Optional[str]=None; position:Optional[int]=None
    rows:Optional[List[str]]=None; columns:Optional[List[str]]=None
    helper_text:Optional[str]=None; randomize_options:Optional[bool]=None
    validation_rules:Optional[dict]=None; logic_rules:Optional[list]=None
    is_attention_check:Optional[bool]=None; correct_answer:Optional[Any]=None

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
             project_brief=data.project_brief,slug=slug,status=data.status,response_limit=data.response_limit,
             theme=data.theme or {}, allow_multiple=data.allow_multiple or False, require_email=data.require_email if data.require_email is not None else True)
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

class SettingsPatch(BaseModel):
    """Appearance & submission settings only — never touches status."""
    theme: Optional[dict] = None
    allow_multiple: Optional[bool] = None
    require_email: Optional[bool] = None

@router.patch("/{sid}/settings")
async def update_survey_settings(sid:str, data:SettingsPatch, db=Depends(get_db), user=Depends(get_current_user)):
    """Update theme/settings ONLY. Status is never changed by this endpoint."""
    s = await check_owner(sid, user, db)
    if data.theme is not None:
        s.theme = data.theme
    if data.allow_multiple is not None:
        s.allow_multiple = data.allow_multiple
    if data.require_email is not None:
        s.require_email = data.require_email
    s.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(s)
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
    s = await check_owner(sid,user,db)
    rc=(await db.execute(select(func.count(Response.id)).where(Response.survey_id==sid))).scalar()
    qc=(await db.execute(select(func.count(Question.id)).where(Question.survey_id==sid))).scalar()
    
    # Calculate running time
    if s.status.value == "active":
        delta = datetime.utcnow() - s.created_at
    else:
        delta = s.updated_at - s.created_at
        
    days = delta.days
    hours = delta.seconds // 3600
    mins = (delta.seconds % 3600) // 60
    
    if days > 0:
        time_str = f"{days}d {hours}h"
    elif hours > 0:
        time_str = f"{hours}h {mins}m"
    elif mins > 0:
        time_str = f"{mins}m"
    else:
        time_str = "< 1m"
        
    return {"response_count":rc,"question_count":qc,"completion_rate":100,"avg_duration":time_str}

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
    ml = _coerce_ml(data.measurement_level) if data.measurement_level else q_type_level(data.type)
    vn=data.variable_name or f"q{data.position+1}_{data.type[:5]}"
    q=Question(id=str(uuid.uuid4()),survey_id=sid,type=data.type,text=data.text,required=data.required,
               options=data.options,scale_min=data.scale_min,scale_max=data.scale_max,
               variable_name=vn,measurement_level=ml,position=data.position,rows=data.rows,columns=data.columns,
               helper_text=data.helper_text,randomize_options=data.randomize_options,
               validation_rules=data.validation_rules or {},logic_rules=data.logic_rules or [],
               is_attention_check=data.is_attention_check,correct_answer=data.correct_answer)
    db.add(q); await db.commit(); await db.refresh(q); return q_out(q)

@router.patch("/{sid}/questions/{qid}")
async def update_question(sid:str, qid:str, data:QuestionPatch, db=Depends(get_db), user=Depends(get_current_user)):
    await check_owner(sid,user,db)
    r=await db.execute(select(Question).where(Question.id==qid,Question.survey_id==sid))
    q=r.scalar_one_or_none()
    if not q: raise HTTPException(404,"Question not found")
    for f,v in data.dict(exclude_none=True).items():
        if f == "measurement_level":
            v = _coerce_ml(v)
        setattr(q,f,v)
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

@router.post("/{sid}/upload-media")
async def upload_media(sid: str, file: UploadFile = File(...), db=Depends(get_db), user=Depends(get_current_user)):
    """Upload a header or background image for a survey. Returns the public URL."""
    import shutil, os
    await check_owner(sid, user, db)

    # Validate file type
    allowed = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    content_type = file.content_type or ''
    if content_type not in allowed:
        raise HTTPException(400, f"Invalid file type '{content_type}'. Only JPEG, PNG, GIF, WebP allowed.")

    # Save to storage/uploads/
    upload_dir = os.path.join('storage', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    ext = (file.filename or 'image.png').rsplit('.', 1)[-1].lower() or 'png'
    filename = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join(upload_dir, filename)

    try:
        with open(file_path, 'wb') as buf:
            shutil.copyfileobj(file.file, buf)
    except Exception as e:
        raise HTTPException(500, f"Failed to save file: {e}")

    # Return the path served by StaticFiles at /storage
    return {"url": f"/storage/uploads/{filename}"}


@router.get("/{sid}/reliability")
async def check_reliability(sid: str, db=Depends(get_db), user=Depends(get_current_user)):
    """
    Comprehensive per-construct reliability analysis.
    Metrics: Cronbach's Alpha, McDonald's Omega, Split-Half (Spearman-Brown),
             Average Inter-Item Correlation (AIIC), KR-20/KR-21 for binary items.
    Groups items automatically by variable name prefix (e.g. DW1-DW5 → Digital Workload).
    Also reports item-total correlations and alpha-if-deleted per construct.
    """
    await check_owner(sid, user, db)

    # ── Cache hit ────────────────────────────────────────────────────────────
    cached = _cache_get(user.id, sid, "reliability")
    if cached:
        return {**cached, "cached": True}

    import pandas as pd
    import numpy as np
    from scipy import stats as scipy_stats
    from sqlalchemy import text
    from analysis.decode.parsers.db_parser import _coerce_answers, answer_value, _sanitize
    from analysis.engine.tests.missing_data import _little_mcar_test


    # ── 1. Fetch questions ──────────────────────────────────────────────────
    q_result = await db.execute(
        text("SELECT id, variable_name, type, text, measurement_level, options FROM questions WHERE survey_id = :sid ORDER BY position"),
        {"sid": sid}
    )
    questions = q_result.fetchall()
    if not questions:
        return {"error": "No questions found in this survey."}

    # ── 2. Fetch responses ──────────────────────────────────────────────────
    r_result = await db.execute(
        text("SELECT answers FROM responses WHERE survey_id = :sid"),
        {"sid": sid}
    )
    responses = r_result.fetchall()
    if not responses:
        return {"error": "No responses found. Collect responses before checking reliability."}

    # ── 3. Build DataFrame ─────────────────────────────────────────────────
    rows = []
    for resp in responses:
        answers = _coerce_answers(resp[0])
        row = {}
        for q in questions:
            qid, vname, qtype, qtext, mlevel, opts = q
            val = answer_value(answers, qid, vname)
            if val is None:
                val = ""
            elif isinstance(val, dict):
                val = "; ".join(f"{_sanitize(k)}: {_sanitize(v)}" for k, v in val.items())
            elif isinstance(val, list):
                val = "; ".join(_sanitize(v) for v in val)
            elif isinstance(val, str):
                val = _sanitize(val)
            col_key = _sanitize(vname or qid)
            row[col_key] = val
        rows.append(row)

    df = pd.DataFrame(rows)
    meta_labels = {_sanitize(q[1] or q[0]): _sanitize(q[3]) for q in questions}
    meta_types  = {_sanitize(q[1] or q[0]): q[2] for q in questions}

    # ── 4. Identify scale (Likert/Rating) items ─────────────────────────────
    valid_cols = []
    for q in questions:
        qid, vname, qtype, qtext, mlevel, opts = q
        col = _sanitize(vname or qid)
        if _is_likert(opts) or qtype in ("likert", "rating"):
            valid_cols.append(col)

    if len(valid_cols) < 2:
        return {"error": "Need at least 2 Likert or Rating scale items to calculate reliability."}

    df_encoded = _encode_likert_dataframe(df[valid_cols], questions, valid_cols)
    df_num_all = df_encoded.apply(pd.to_numeric, errors="coerce")

    # ── 5. Auto-detect constructs by variable name prefix ──────────────────
    # e.g. DW1, DW2, DW3 → prefix "DW"  |  PS1..PS5 → prefix "PS"
    import re
    def _extract_prefix(col: str) -> str:
        m = re.match(r'^([A-Za-z]+)', col)
        return m.group(1).upper() if m else col.upper()

    construct_map: dict[str, list[str]] = {}
    for col in valid_cols:
        pfx = _extract_prefix(col)
        construct_map.setdefault(pfx, []).append(col)

    # Only keep prefixes with ≥ 2 items (otherwise no reliability can be computed)
    construct_map = {k: v for k, v in construct_map.items() if len(v) >= 2}

    # If no multi-item constructs found, fall back to treating all items as one scale
    if not construct_map:
        construct_map = {"All Items": valid_cols}

    # ── 6. Helper: compute comprehensive reliability for one set of items ──
    def _interp(a: float) -> str:
        if a >= 0.90: return "Excellent"
        if a >= 0.80: return "Good"
        if a >= 0.70: return "Acceptable"
        if a >= 0.60: return "Questionable"
        if a >= 0.50: return "Poor"
        return "Unacceptable"

    def _cronbach(mat: pd.DataFrame) -> tuple[float, float | None, float | None]:
        k = mat.shape[1]
        if k < 2:
            return 0.0, None, None
        try:
            import pingouin as pg
            a, ci = pg.cronbach_alpha(mat)
            return float(a), (float(ci[0]) if ci is not None else None), (float(ci[1]) if ci is not None else None)
        except Exception:
            iv = mat.var(axis=0, ddof=1)
            tv = mat.sum(axis=1).var(ddof=1)
            a = float((k / (k - 1)) * (1 - iv.sum() / tv)) if tv > 0 else 0.0
            return a, None, None

    def _omega(mat: pd.DataFrame) -> float | None:
        """McDonald's Omega via one-factor CFA loadings (SEM-free approximation)."""
        try:
            k = mat.shape[1]
            if k < 3:
                return None
            corr = mat.corr().values
            # Estimate loadings via first principal component
            eigvals, eigvecs = np.linalg.eigh(corr)
            idx = np.argsort(eigvals)[::-1]
            loadings = eigvecs[:, idx[0]] * np.sqrt(max(eigvals[idx[0]], 0))
            # Omega = (sum of loadings)^2 / ((sum of loadings)^2 + sum of uniquenesses)
            sum_lam  = float(np.sum(loadings))
            uniq_sum = float(np.sum(1 - loadings**2))
            denom = sum_lam**2 + uniq_sum
            return round(sum_lam**2 / denom, 3) if denom > 0 else None
        except Exception:
            return None

    def _split_half(mat: pd.DataFrame) -> float | None:
        """Spearman-Brown corrected split-half reliability."""
        try:
            k = mat.shape[1]
            if k < 2:
                return None
            half1 = mat.iloc[:, :k // 2].sum(axis=1)
            half2 = mat.iloc[:, k // 2:].sum(axis=1)
            r, _ = scipy_stats.pearsonr(half1.dropna(), half2.dropna())
            sb = float(2 * r / (1 + r))  # Spearman-Brown correction
            return round(sb, 3)
        except Exception:
            return None

    def _aiic(mat: pd.DataFrame) -> float | None:
        """Average Inter-Item Correlation (ideal: 0.15–0.50)."""
        try:
            if mat.shape[1] < 2:
                return None
            corr = mat.corr()
            upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
            vals = upper.stack().dropna()
            return round(float(vals.mean()), 3) if len(vals) > 0 else None
        except Exception:
            return None

    def _item_diagnostics(mat: pd.DataFrame, alpha_val: float, labels: dict) -> list:
        diags = []
        n = len(mat)
        for col in mat.columns:
            label = labels.get(col, col)
            rest  = mat.drop(columns=[col]).sum(axis=1)
            try:
                r_itc, _ = scipy_stats.pearsonr(mat[col].dropna(), rest[mat[col].notna()])
                r_val = float(r_itc)
            except Exception:
                r_val = None

            # Alpha if deleted
            a_del = None
            df_drop = mat.drop(columns=[col])
            if df_drop.shape[1] >= 2:
                a_del, _, _ = _cronbach(df_drop.dropna(thresh=2))

            flag = "ok"
            rec  = "Contributing well to scale reliability."
            if r_val is not None:
                if r_val < 0:
                    flag, rec = "negative_corr", "Negatively correlated with scale — consider reversing or removing."
                elif r_val < 0.20:
                    flag, rec = "very_low_r", "Very weak correlation — strongly consider removing."
                elif r_val < 0.30:
                    flag, rec = "low_r", "Below 0.30 threshold — consider revising."
                elif a_del is not None and a_del > alpha_val + 0.02:
                    flag, rec = "drops_alpha", f"Removing would improve Alpha to {round(a_del, 3)}."

            diags.append({
                "item":             col,
                "label":            label,
                "mean":             round(float(mat[col].mean()), 3),
                "std":              round(float(mat[col].std()), 3),
                "item_total_corr":  round(r_val, 3) if r_val is not None else None,
                "alpha_if_deleted": round(a_del, 3)  if a_del is not None else None,
                "improves_alpha":   bool(a_del is not None and a_del > alpha_val + 0.005),
                "flag":             flag,
                "recommendation":   rec,
            })

        flag_order = {"negative_corr": 0, "very_low_r": 1, "drops_alpha": 2, "low_r": 3, "ok": 4}
        diags.sort(key=lambda x: flag_order.get(x["flag"], 4))
        return diags

    # ── 7. Compute per-construct reliability ────────────────────────────────
    CONSTRUCT_NAMES = {
        "DW": "Digital Workload Scale",
        "TS": "Technostress Scale",
        "PS": "Psychological Safety Scale",
        "LS": "Leadership Support Scale",
        "JS": "Job Satisfaction Scale",
        "OC": "Organisational Commitment Scale",
        "WL": "Work-Life Balance Scale",
    }

    construct_results = []
    overall_alphas   = []

    for prefix, cols in construct_map.items():
        mat_raw = df_num_all[cols].dropna(thresh=2)
        # Remove zero-variance columns within this construct
        good = [c for c in cols if c in mat_raw.columns and mat_raw[c].nunique() > 1]
        if len(good) < 2:
            construct_results.append({
                "construct": prefix,
                "name":      CONSTRUCT_NAMES.get(prefix, f"{prefix} Scale"),
                "items":     cols,
                "n_items":   len(cols),
                "error":     "Insufficient variance — all respondents gave the same answer.",
            })
            continue

        mat = mat_raw[good].dropna(thresh=2)
        n   = len(mat)
        k   = len(good)

        binary_cols = [c for c in good if set(mat[c].dropna().unique()).issubset({0,1,0.0,1.0})]
        all_binary  = len(binary_cols) == k

        if all_binary:
            p_vals   = mat.mean()
            q_vals   = 1 - p_vals
            pq_sum   = float((p_vals * q_vals).sum())
            tot_var  = float(mat.sum(axis=1).var(ddof=1))
            kr20     = float((k / (k-1)) * (1 - pq_sum / tot_var)) if tot_var > 0 else 0.0
            p_bar    = float(p_vals.mean())
            kr21     = float((k / (k-1)) * (1 - k * p_bar * (1 - p_bar) / tot_var)) if tot_var > 0 else 0.0
            alpha_val, ci_lo, ci_hi = kr20, None, None
            method   = "KR-20 (binary items)"
            kr20_out, kr21_out = round(kr20, 3), round(kr21, 3)
        else:
            alpha_val, ci_lo, ci_hi = _cronbach(mat)
            kr20_out, kr21_out      = None, None
            method = "Cronbach's Alpha"

        omega    = _omega(mat)
        sh       = _split_half(mat)
        aiic_val = _aiic(mat)

        aiic_interp = (
            "Too low — items may not share a common construct." if aiic_val is not None and aiic_val < 0.15
            else "Acceptable — items share a common construct." if aiic_val is not None and aiic_val <= 0.50
            else "Too high — possible item redundancy." if aiic_val is not None
            else "N/A"
        )

        diags      = _item_diagnostics(mat, alpha_val, meta_labels)
        n_prob     = sum(1 for d in diags if d["flag"] != "ok")
        interp     = _interp(alpha_val)

        if alpha_val >= 0.80 and n_prob == 0:
            verdict = f"Strong reliability (α = {round(alpha_val,3)}). No action needed."
        elif alpha_val >= 0.70:
            verdict = f"Acceptable reliability (α = {round(alpha_val,3)}). {n_prob} item(s) need attention."
        elif alpha_val >= 0.60:
            verdict = f"Questionable reliability (α = {round(alpha_val,3)}). Review flagged items."
        else:
            verdict = f"Poor reliability (α = {round(alpha_val,3)}). Scale needs revision."

        overall_alphas.append(alpha_val)

        construct_results.append({
            "construct":       prefix,
            "name":            CONSTRUCT_NAMES.get(prefix, f"{prefix} Scale"),
            "items":           good,
            "n_items":         k,
            "n_respondents":   n,
            "method":          method,
            "alpha":           round(alpha_val, 3),
            "alpha_ci_lower":  round(ci_lo,    3) if ci_lo  is not None else None,
            "alpha_ci_upper":  round(ci_hi,    3) if ci_hi  is not None else None,
            "interpretation":  interp,
            "omega":           omega,
            "split_half":      sh,
            "aiic":            aiic_val,
            "aiic_interp":     aiic_interp,
            "kr20":            kr20_out,
            "kr21":            kr21_out,
            "verdict":         verdict,
            "n_problematic":   n_prob,
            "diagnostics":     diags,
        })

    # ── 8. Overall summary ──────────────────────────────────────────────────
    avg_alpha = round(float(np.mean(overall_alphas)), 3) if overall_alphas else None
    n_constructs = len(construct_results)
    n_passing   = sum(1 for cr in construct_results if "alpha" in cr and cr["alpha"] >= 0.70)

    if avg_alpha is None:
        overall_verdict = "Could not compute reliability — check your data."
    elif avg_alpha >= 0.80:
        overall_verdict = f"Overall scale reliability is strong. {n_passing}/{n_constructs} constructs meet the ≥ 0.70 threshold."
    elif avg_alpha >= 0.70:
        overall_verdict = f"Overall reliability is acceptable. {n_passing}/{n_constructs} constructs meet the ≥ 0.70 threshold."
    else:
        overall_verdict = f"Reliability is below acceptable levels for {n_constructs - n_passing} construct(s). Review flagged items."

    result = {
        "mode":             "per_construct",
        "n_constructs":     n_constructs,
        "n_passing":        n_passing,
        "avg_alpha":        avg_alpha,
        "overall_verdict":  overall_verdict,
        "constructs":       construct_results,
        "note":             (
            "Each construct is analysed independently. Cronbach's Alpha (or KR-20 for binary items), "
            "McDonald's Omega (factor-analytic estimate), Spearman-Brown Split-Half, and Average "
            "Inter-Item Correlation are reported per scale. Items are auto-grouped by variable name prefix."
        ),
    }

    _cache_set(user.id, sid, "reliability", result)
    return result


# ─── Path Analysis Readiness Check (Comprehensive) ───────────────────────────
@router.get("/{sid}/path-analysis")
async def check_path_analysis(sid: str, db=Depends(get_db), user=Depends(get_current_user)):
    """
    Comprehensive path analysis readiness check covering all statistical prerequisites:
    1. Measurement scale (continuous/interval/ratio)
    2. Sample size adequacy (N ≥ 200 recommended; min 10-20 per path)
    3. Missing data assessment per variable
    4. Normality of each variable (Shapiro-Wilk, skewness, kurtosis)
    5. Multicollinearity among variables (r > 0.85 is problematic)
    6. Outlier detection (Mahalanobis distance)
    7. Linearity of relationships (Pearson r matrix)
    8. Full correlation matrix (to help identify causal paths)
    9. Model identification guidance
    10. Theoretical framework requirements
    """
    await check_owner(sid, user, db)

    import pandas as pd
    import numpy as np
    from scipy import stats as scipy_stats
    from sqlalchemy import text
    from analysis.decode.parsers.db_parser import _coerce_answers, answer_value, _sanitize

    q_result = await db.execute(
        text("SELECT id, variable_name, type, text, measurement_level, options FROM questions WHERE survey_id = :sid ORDER BY position"),
        {"sid": sid}
    )
    questions = q_result.fetchall()
    if not questions:
        return {"error": "No questions found in this survey."}

    r_result = await db.execute(
        text("SELECT answers FROM responses WHERE survey_id = :sid"),
        {"sid": sid}
    )
    responses = r_result.fetchall()
    if not responses:
        return {"error": "No responses found. Collect responses before running this check."}

    # ── Build DataFrame ────────────────────────────────────────────────────────
    rows = []
    for resp in responses:
        answers = _coerce_answers(resp[0])
        row = {}
        for q in questions:
            qid, vname, qtype, qtext, mlevel, opts = q
            val = answer_value(answers, qid, vname)
            if val is None or isinstance(val, (dict, list)):
                val = ""
            elif isinstance(val, str):
                val = _sanitize(val)
            row[_sanitize(vname or qid)] = val
        rows.append(row)

    df = pd.DataFrame(rows)
    meta_levels = {_sanitize(q[1] or q[0]): q[4] for q in questions}
    meta_labels = {_sanitize(q[1] or q[0]): _sanitize(q[3]) for q in questions}

    # ── 1. Classify variables by measurement level ─────────────────────────────
    usable_cols = _get_scale_columns(questions)
    nominal_cols = [c for c in df.columns if c not in usable_cols]
    
    if usable_cols:
        df_encoded = _encode_likert_dataframe(df[usable_cols], questions, usable_cols)
        df_num = df_encoded.apply(pd.to_numeric, errors="coerce")
    else:
        df_num = pd.DataFrame()

    n = len(responses)
    n_continuous = len(usable_cols)
    ordinal_cols = []
    n_usable = len(usable_cols)

    # ── 2. Sample size assessment ──────────────────────────────────────────────
    # Path analysis needs: (a) at least 10-20 per estimated path, (b) ideally N ≥ 200
    n_paths_estimated = max(1, n_usable * (n_usable - 1) // 2)
    min_per_path      = n_paths_estimated * 10
    recommended_n     = max(200, min_per_path)
    sample_ok         = n >= min_per_path
    sample_ideal      = n >= recommended_n

    # ── 3. Missing data per variable ───────────────────────────────────────────
    missing_pct = {}
    if not df_num.empty:
        for col in df_num.columns:
            missing_pct[col] = round(float(df_num[col].isna().mean() * 100), 1)
    vars_high_missing = [k for k, v in missing_pct.items() if v > 5]
    any_missing_issue = len(vars_high_missing) > 0

    # Work with listwise complete data for subsequent tests
    df_complete = df_num.dropna() if not df_num.empty else pd.DataFrame()
    n_complete = len(df_complete)

    # ── 4. Normality assessment per variable ───────────────────────────────────
    normality_results = []
    if not df_complete.empty:
        for col in usable_cols:
            if col not in df_complete.columns:
                continue
            series = df_complete[col]
            if len(series) < 3 or series.nunique() < 2:
                continue
            try:
                skew_val  = float(scipy_stats.skew(series))
                kurt_val  = float(scipy_stats.kurtosis(series))  # excess kurtosis
                sw_stat, sw_p = None, None
                if len(series) <= 2000:
                    sw_stat, sw_p = scipy_stats.shapiro(series)
                    sw_stat, sw_p = float(sw_stat), float(sw_p)

                skew_ok = abs(skew_val) < 2.0
                kurt_ok = abs(kurt_val) < 7.0
                sw_ok   = (sw_p > 0.05) if sw_p is not None else True
                is_normal = sw_ok and skew_ok and kurt_ok

                normality_results.append({
                    "variable":   col,
                    "label":      meta_labels.get(col, col),
                    "n":          len(series),
                    "skewness":   round(skew_val, 3),
                    "kurtosis":   round(kurt_val, 3),
                    "sw_stat":    round(sw_stat, 4) if sw_stat is not None else None,
                    "sw_p":       round(sw_p, 4)    if sw_p    is not None else None,
                    "is_normal":  is_normal,
                    "skew_ok":    skew_ok,
                    "kurt_ok":    kurt_ok,
                    "sw_ok":      sw_ok,
                    "note": (
                        "Normal" if is_normal
                        else ("High skewness — consider transformation" if not skew_ok
                              else ("High kurtosis" if not kurt_ok
                                    else "SW test significant — consider non-normality"))
                    ),
                })
            except Exception:
                pass

    n_normal_vars     = sum(1 for r in normality_results if r["is_normal"])
    n_non_normal_vars = sum(1 for r in normality_results if not r["is_normal"])
    normality_ok      = n_non_normal_vars == 0

    # ── 5. Multicollinearity screening (r > 0.85 = problematic for path analysis)
    correlation_matrix = {}
    high_correlations  = []   # r ≥ 0.85 — problematic
    if len(usable_cols) >= 2 and not df_complete.empty:
        try:
            df_corr   = df_complete[usable_cols]
            corr      = df_corr.corr()
            # Build matrix output
            for col in usable_cols:
                if col in corr.columns:
                    correlation_matrix[col] = {
                        other: round(float(corr.loc[col, other]), 3)
                        for other in usable_cols if other in corr.columns
                    }
            # Detect problematic pairs
            cols_in_corr = [c for c in usable_cols if c in corr.columns]
            for i in range(len(cols_in_corr)):
                for j in range(i + 1, len(cols_in_corr)):
                    r_val = corr.loc[cols_in_corr[i], cols_in_corr[j]]
                    if abs(r_val) >= 0.85:
                        high_correlations.append({
                            "var_a":   cols_in_corr[i],
                            "label_a": meta_labels.get(cols_in_corr[i], cols_in_corr[i]),
                            "var_b":   cols_in_corr[j],
                            "label_b": meta_labels.get(cols_in_corr[j], cols_in_corr[j]),
                            "r":       round(float(r_val), 3),
                            "severity": "perfect" if abs(r_val) >= 0.95 else "high",
                        })
        except Exception:
            pass
    multicollinearity_ok = len(high_correlations) == 0

    # ── 6. Outlier detection — Z-score method (|z| > 3.29 = extreme outlier) ──
    outlier_summary = {}
    n_cases_with_outliers = 0
    if not df_complete.empty:
        try:
            z_scores = np.abs(scipy_stats.zscore(df_complete[usable_cols].select_dtypes(include=[np.number]), ddof=1))
            extreme  = (z_scores > 3.29).any(axis=1)
            n_cases_with_outliers = int(extreme.sum())
            outlier_pct = round(n_cases_with_outliers / n_complete * 100, 1) if n_complete else 0
            outlier_summary = {
                "n_outlier_cases": n_cases_with_outliers,
                "outlier_pct": outlier_pct,
                "threshold": "Z > 3.29 (p < .001, two-tailed)",
                "severity": (
                    "high"     if outlier_pct > 10 else
                    "moderate" if outlier_pct > 5  else
                    "ok"
                ),
                "note": (
                    f"{n_cases_with_outliers} case(s) ({outlier_pct}%) have at least one variable with |Z| > 3.29. "
                    "These may distort path coefficients. Consider Winsorising or removing extreme cases."
                    if n_cases_with_outliers > 0
                    else "No extreme outliers detected (Z-score method)."
                ),
            }
        except Exception as e:
            outlier_summary = {"error": str(e)}
    outliers_ok = outlier_summary.get("severity", "ok") in ("ok", "moderate")

    # ── 7. Linearity check via Pearson r ──────────────────────────────────────
    linearity_checks = []
    if len(usable_cols) >= 2 and not df_complete.empty:
        pairs = [(usable_cols[i], usable_cols[j])
                 for i in range(len(usable_cols))
                 for j in range(i + 1, len(usable_cols))]
        for va, vb in pairs[:20]:
            try:
                if va not in df_complete.columns or vb not in df_complete.columns:
                    continue
                r_val, p_val = scipy_stats.pearsonr(df_complete[va], df_complete[vb])
                linearity_checks.append({
                    "var_a":   va, "label_a": meta_labels.get(va, va),
                    "var_b":   vb, "label_b": meta_labels.get(vb, vb),
                    "r":       round(float(r_val), 3),
                    "p":       round(float(p_val), 4),
                    "sig":     bool(p_val < 0.05),
                    "strength": (
                        "negligible" if abs(r_val) < 0.1 else
                        "weak"       if abs(r_val) < 0.3 else
                        "moderate"   if abs(r_val) < 0.5 else
                        "strong"     if abs(r_val) < 0.7 else
                        "very_strong"
                    ),
                    "problematic_mc": bool(abs(r_val) >= 0.85),
                })
            except Exception:
                pass

    linearity_ok = len(linearity_checks) > 0 or len(usable_cols) >= 2

    # ── 8. Model identification (just-identified, over-identified, under-identified)
    # For a path model with p variables:
    # Known values (unique correlations/variances) = p(p+1)/2
    # Free parameters in a saturated (just-identified) model = p(p-1)/2 + p (paths + disturbances)
    # User's model degrees of freedom = known - free parameters estimated
    p = n_usable
    known_values = p * (p + 1) // 2 if p >= 2 else 0
    saturated_params = p * (p - 1) // 2 + p if p >= 2 else 0  # all paths + disturbances
    model_df_note = (
        f"With {p} variable(s), a saturated (just-identified) model has 0 df. "
        "Your theoretical model (which omits some paths) will have positive df, "
        "allowing goodness-of-fit testing. Aim for df ≥ 1 (over-identified model)."
        if p >= 2 else "Need at least 2 variables to assess model identification."
    )

    # ── 9. Build comprehensive requirements checklist ─────────────────────────
    requirements = [
        {
            "id": "scale",
            "name": "Measurement Scale (Continuous / Scale Variables)",
            "description": "Path analysis requires interval or ratio variables as the main path nodes. Ordinal Likert scales (≥5 categories) can be treated as quasi-continuous with caution.",
            "passed": n_usable >= 2,
            "detail": (
                f"{n_continuous} interval/ratio variable(s) + {len(ordinal_cols)} ordinal (Likert) = {n_usable} usable. "
                f"{len(nominal_cols)} nominal variable(s) excluded (cannot be path nodes without dummy coding)."
            ),
            "recommendation": "You need at least 2 continuous or ordinal-scale variables to form a path model." if n_usable < 2 else None,
            "severity": "critical" if n_usable < 2 else "ok",
        },
        {
            "id": "sample_size",
            "name": "Adequate Sample Size",
            "description": (
                "Two rules apply: (a) minimum 10–20 cases per estimated path; "
                "(b) the broader recommendation is N ≥ 200 for stable path coefficients."
            ),
            "passed": sample_ok,
            "detail": (
                f"{n} respondents. "
                f"Minimum for {n_paths_estimated} paths: {min_per_path}. "
                f"Recommended minimum: {recommended_n}. "
                + ("✓ Meets recommended N ≥ 200." if sample_ideal else
                   f"⚠ Meets minimum but below ideal N ≥ 200 — results may be unstable." if sample_ok else
                   f"✗ Below minimum — collect at least {min_per_path - n} more responses.")
            ),
            "recommendation": f"Collect at least {max(0, recommended_n - n)} more responses to reach the recommended N ≥ 200." if not sample_ideal else None,
            "severity": "critical" if not sample_ok else ("moderate" if not sample_ideal else "ok"),
        },
        {
            "id": "missing_data",
            "name": "Minimal Missing Data (< 5% per variable)",
            "description": (
                "Path analysis (and especially SEM-based path analysis) requires complete data or properly imputed data. "
                "Variables with > 5% missingness should be handled via Multiple Imputation or Full Information Maximum Likelihood (FIML)."
            ),
            "passed": not any_missing_issue,
            "detail": (
                "All variables have < 5% missing data. ✓" if not any_missing_issue
                else f"Variables with ≥ 5% missing: {', '.join(f'{v} ({missing_pct[v]}%)' for v in vars_high_missing)}."
            ),
            "recommendation": "Apply Multiple Imputation or Full Information Maximum Likelihood (FIML) to handle missing data before running path analysis." if any_missing_issue else None,
            "severity": "high" if any_missing_issue else "ok",
        },
        {
            "id": "normality",
            "name": "Multivariate Normality",
            "description": (
                "Path analysis (especially via SEM/ML estimation) assumes multivariate normality. "
                "Each variable should be approximately normally distributed (|skewness| < 2, |excess kurtosis| < 7, SW p > .05). "
                "Robust estimation (e.g., Satorra-Bentler) can be used when normality is violated."
            ),
            "passed": normality_ok if normality_results else None,
            "detail": (
                f"{n_normal_vars} of {len(normality_results)} variable(s) are approximately normal. "
                + (f"{n_non_normal_vars} variable(s) violate normality." if n_non_normal_vars > 0 else "")
                if normality_results else "Insufficient data to test normality."
            ),
            "recommendation": (
                "For non-normal data: apply log/sqrt transformation, use bootstrapped confidence intervals, "
                "or use WLS/asymptotic distribution-free (ADF) estimation." if n_non_normal_vars > 0 else None
            ),
            "severity": "high" if n_non_normal_vars > 0 else "ok",
        },
        {
            "id": "multicollinearity",
            "name": "No Severe Multicollinearity (r < 0.85)",
            "description": (
                "Path variables must not be too highly intercorrelated (r ≥ 0.85). "
                "Severe multicollinearity inflates standard errors and makes path coefficients unstable and uninterpretable."
            ),
            "passed": multicollinearity_ok,
            "detail": (
                "No variable pairs have r ≥ 0.85. ✓" if multicollinearity_ok
                else f"{len(high_correlations)} pair(s) with r ≥ 0.85: " +
                     "; ".join(f"{hc['label_a']} & {hc['label_b']} (r={hc['r']})" for hc in high_correlations[:3])
            ),
            "recommendation": "Consider removing one of the highly correlated variables, or combining them into a composite score." if not multicollinearity_ok else None,
            "severity": "high" if not multicollinearity_ok else "ok",
        },
        {
            "id": "outliers",
            "name": "No Extreme Outliers",
            "description": (
                "Extreme univariate outliers (|Z| > 3.29, p < .001) can severely distort path coefficients. "
                "For multivariate outliers, Mahalanobis distance is the gold standard."
            ),
            "passed": outliers_ok,
            "detail": outlier_summary.get("note", "Outlier check not completed."),
            "recommendation": (
                "Consider: (1) verify data entry errors, (2) Winsorize extreme values, "
                "(3) remove cases if justified theoretically." if not outliers_ok else None
            ),
            "severity": "moderate" if not outliers_ok else "ok",
        },
        {
            "id": "linearity",
            "name": "Linear Relationships Between Path Variables",
            "description": (
                "Path analysis assumes that all causal relationships are LINEAR. "
                "Non-linear relationships require polynomial terms or non-linear SEM. "
                "Pearson r assesses linearity — non-significant pairs may not form meaningful paths."
            ),
            "passed": linearity_ok,
            "detail": (
                f"{sum(1 for lc in linearity_checks if lc['sig'])} of {len(linearity_checks)} variable pair(s) show a statistically significant linear relationship (p < .05)."
                if linearity_checks else "Linearity check could not be performed — need ≥ 2 numeric variables."
            ),
            "recommendation": "Plot scatter plots for each hypothesised path to visually verify linearity before analysis." if not linearity_checks else None,
            "severity": "ok" if linearity_ok else "moderate",
        },
        {
            "id": "independence",
            "name": "Independence of Observations",
            "description": (
                "Each respondent's data must be independent of others. "
                "Clustered data (e.g., students in classrooms) requires multilevel path models."
            ),
            "passed": None,
            "detail": "Cannot be verified automatically. Confirm that responses are from independent individuals with no nesting structure.",
            "recommendation": "If data are clustered (e.g., school students, hospital patients), use multilevel SEM instead of standard path analysis.",
            "severity": "info",
        },
        {
            "id": "model_identification",
            "name": "Model Identification",
            "description": (
                "A path model is identified when the number of known values (variances + covariances) "
                "is ≥ the number of free parameters to estimate. "
                "Under-identified models cannot be uniquely solved."
            ),
            "passed": None,
            "detail": model_df_note,
            "recommendation": (
                "Rule: your model must not estimate more free parameters than p(p+1)/2 known data points. "
                f"With {p} variable(s) you have {known_values} known values. "
                "Omitting paths (fixing coefficients to 0) gives your model positive df and makes it testable."
            ),
            "severity": "info",
        },
    ]

    n_failed   = sum(1 for r in requirements if r["passed"] is False)
    n_passed   = sum(1 for r in requirements if r["passed"] is True)
    n_critical = sum(1 for r in requirements if r.get("severity") in ("critical", "high") and r["passed"] is False)

    if n_critical > 0:
        readiness = "not_ready"
        verdict   = f"{n_critical} critical requirement(s) not met. Fix these before running path analysis."
    elif n_failed > 0:
        readiness = "caution"
        verdict   = f"{n_failed} requirement(s) need attention. Proceed with caution and address recommendations."
    elif n_failed == 0 and n_usable >= 2:
        readiness = "ready"
        verdict   = "Your data meets the statistical requirements for path analysis. Proceed to define your causal model."
    else:
        readiness = "not_ready"
        verdict   = "Insufficient scale variables for path analysis."

    return {
        # Summary
        "n_respondents":         n,
        "n_complete_cases":      n_complete,
        "n_continuous_variables": n_continuous,
        "n_ordinal_variables":   len(ordinal_cols),
        "n_nominal_variables":   len(nominal_cols),
        "n_usable_variables":    n_usable,
        "n_paths_estimated":     n_paths_estimated,
        "min_sample_per_path":   min_per_path,
        "recommended_n":         recommended_n,

        # Test results
        "missing_pct_per_variable": missing_pct,
        "normality_per_variable":   normality_results,
        "correlation_matrix":       correlation_matrix,
        "linearity_checks":         linearity_checks,
        "high_correlations":        high_correlations,
        "outlier_summary":          outlier_summary,

        # Requirement checklist
        "requirements": requirements,
        "n_passed":     n_passed,
        "n_failed":     n_failed,
        "n_critical":   n_critical,
        "readiness":    readiness,
        "verdict":      verdict,

        # Guidance
        "guidance": {
            "next_steps": ["Define your causal diagram", "Identify exogenous and endogenous variables", "Run path analysis from the Analysis section"],
            "effect_size_benchmarks": {
                "direct_path": "β < 0.10 = negligible, 0.10–0.29 = small, 0.30–0.49 = medium, ≥ 0.50 = large",
                "r2": "R² < 0.13 = weak, 0.13–0.26 = moderate, > 0.26 = substantial",
                "fit_indices": "CFI/TLI ≥ 0.95, RMSEA < 0.06, SRMR < 0.08 = good fit",
            },
            "key_outputs_to_report": [
                "Direct, indirect, and total path coefficients (β)",
                "Standard errors and 95% confidence intervals (bootstrap)",
                "Model fit indices (if over-identified: CFI, RMSEA, SRMR)",
                "R² for each endogenous variable",
                "Mediation effects (if applicable)",
            ],
        },
    }



# ─── Multicollinearity Check (VIF) ───────────────────────────────────────────
@router.get("/{sid}/multicollinearity")
async def check_multicollinearity(sid: str, db=Depends(get_db), user=Depends(get_current_user)):
    """Check for multicollinearity using VIF and correlation matrix."""
    await check_owner(sid, user, db)

    # ── Cache hit ────────────────────────────────────────────────────────────
    cached = _cache_get(user.id, sid, "multicollinearity")
    if cached:
        return {**cached, "cached": True}

    import pandas as pd
    import numpy as np
    from sqlalchemy import text
    from analysis.decode.parsers.db_parser import _coerce_answers, answer_value, _sanitize

    q_result = await db.execute(
        text("SELECT id, variable_name, type, text, measurement_level, options FROM questions WHERE survey_id = :sid ORDER BY position"),
        {"sid": sid}
    )
    questions = q_result.fetchall()
    if not questions:
        return {"error": "No questions found in this survey."}

    r_result = await db.execute(
        text("SELECT answers FROM responses WHERE survey_id = :sid"),
        {"sid": sid}
    )
    responses = r_result.fetchall()
    if not responses:
        return {"error": "No responses found. Collect responses before checking multicollinearity."}

    rows = []
    for resp in responses:
        answers = _coerce_answers(resp[0])
        row = {}
        for q in questions:
            qid, vname, qtype, qtext, mlevel, opts = q
            val = answer_value(answers, qid, vname)
            row[_sanitize(vname or qid)] = val
        rows.append(row)

    df = pd.DataFrame(rows)
    meta_levels = {_sanitize(q[1] or q[0]): q[4] for q in questions}
    meta_labels = {_sanitize(q[1] or q[0]): _sanitize(q[3]) for q in questions}

    scale_cols = _get_scale_columns(questions)
    if len(scale_cols) < 2:
        return {"error": "Need at least 2 Likert, Rating, or Numeric questions to check multicollinearity."}

    df_encoded = _encode_likert_dataframe(df[scale_cols], questions, scale_cols)
    df_num = df_encoded.apply(pd.to_numeric, errors="coerce").dropna()
    if len(df_num) < 5:
        return {"error": f"Only {len(df_num)} complete rows. Need at least 5 to compute VIF."}

    good_cols = [c for c in df_num.columns if df_num[c].nunique() > 1]
    if len(good_cols) < 2:
        return {"error": "Too many zero-variance variables."}
    df_num = df_num[good_cols]

    corr = df_num.corr()
    high_correlations = []
    for i in range(len(good_cols)):
        for j in range(i + 1, len(good_cols)):
            r_val = corr.iloc[i, j]
            if abs(r_val) >= 0.70:
                high_correlations.append({
                    "var_a": good_cols[i], "label_a": meta_labels.get(good_cols[i], good_cols[i]),
                    "var_b": good_cols[j], "label_b": meta_labels.get(good_cols[j], good_cols[j]),
                    "r": round(float(r_val), 3),
                    "severity": "high" if abs(r_val) >= 0.90 else "moderate",
                })

    vif_results = []
    try:
        X_std = (df_num.values - df_num.values.mean(axis=0)) / (df_num.values.std(axis=0) + 1e-12)
        corr_matrix = np.corrcoef(X_std.T)
        corr_inv = np.linalg.inv(corr_matrix)
        for idx, col in enumerate(good_cols):
            vif = max(1.0, round(float(corr_inv[idx, idx]), 2))
            if vif >= 10:
                severity, flag = "high", "Serious multicollinearity — consider removing or combining this variable."
            elif vif >= 5:
                severity, flag = "moderate", "Moderate multicollinearity — monitor carefully."
            else:
                severity, flag = "ok", "Acceptable VIF."
            vif_results.append({
                "variable": col, "label": meta_labels.get(col, col),
                "vif": vif, "tolerance": round(1.0 / vif, 3),
                "severity": severity, "flag": flag,
            })
    except np.linalg.LinAlgError:
        vif_results = [{"error": "Singular matrix — perfect multicollinearity detected."}]
    except Exception as e:
        vif_results = [{"error": f"VIF calculation failed: {e}"}]

    vif_ok = [v for v in vif_results if "vif" in v]
    vif_ok.sort(key=lambda x: x["vif"], reverse=True)

    n_high_vif = sum(1 for v in vif_ok if v["severity"] == "high")
    n_mod_vif  = sum(1 for v in vif_ok if v["severity"] == "moderate")

    # Condition Number — CN > 30 indicates severe multicollinearity
    condition_number = None
    condition_number_severity = "ok"
    condition_number_note = None
    try:
        eigenvalues = np.linalg.eigvalsh(np.corrcoef(df_num.values.T))
        eigenvalues = np.abs(eigenvalues)
        condition_number = round(float(np.sqrt(eigenvalues.max() / max(eigenvalues.min(), 1e-12))), 2)
        if condition_number > 30:
            condition_number_severity = "high"
            condition_number_note = f"Condition Number = {condition_number} (> 30): severe multicollinearity confirmed."
        elif condition_number > 15:
            condition_number_severity = "moderate"
            condition_number_note = f"Condition Number = {condition_number} (15–30): moderate multicollinearity."
        else:
            condition_number_note = f"Condition Number = {condition_number} (< 15): acceptable."
    except Exception:
        pass

    if n_high_vif > 0 or condition_number_severity == "high":
        verdict = f"Serious multicollinearity in {n_high_vif} variable(s) (VIF ≥ 10). Consider removing, combining, or using Ridge Regression."
        severity_overall = "high"
    elif n_mod_vif > 0 or len(high_correlations) > 0 or condition_number_severity == "moderate":
        verdict = f"Moderate multicollinearity ({n_mod_vif} variable(s) VIF 5–10; {len(high_correlations)} high-r pair(s)). Proceed with caution."
        severity_overall = "moderate"
    else:
        verdict = "No problematic multicollinearity detected. All VIF values are < 5."
        severity_overall = "ok"

    result = {
        "n_respondents": len(df_num), "n_variables": len(good_cols), "variables": good_cols,
        "variable_labels": {col: meta_labels.get(col, col) for col in good_cols},
        "vif_results": vif_ok, "high_correlations": high_correlations,
        "correlation_matrix": {col: {other: round(float(corr.loc[col, other]), 3) for other in good_cols} for col in good_cols},
        "n_high_vif": n_high_vif, "n_moderate_vif": n_mod_vif,
        "n_high_correlations": len(high_correlations),
        "condition_number": condition_number,
        "condition_number_severity": condition_number_severity,
        "condition_number_note": condition_number_note,
        "severity_overall": severity_overall, "verdict": verdict,
        "thresholds": {"vif_moderate": 5, "vif_high": 10, "r_high": 0.70, "cn_moderate": 15, "cn_high": 30},
    }
    _cache_set(user.id, sid, "multicollinearity", result)
    return result


# ─── Normality Check ─────────────────────────────────────────────────────────
@router.get("/{sid}/normality")
async def check_normality(sid: str, db=Depends(get_db), user=Depends(get_current_user)):
    """Check normality using Shapiro-Wilk, skewness, and kurtosis."""
    await check_owner(sid, user, db)

    # ── Cache hit ────────────────────────────────────────────────────────────
    cached = _cache_get(user.id, sid, "normality")
    if cached:
        return {**cached, "cached": True}

    import pandas as pd
    import numpy as np
    from scipy import stats as scipy_stats
    from sqlalchemy import text
    from analysis.decode.parsers.db_parser import _coerce_answers, answer_value, _sanitize

    q_result = await db.execute(
        text("SELECT id, variable_name, type, text, measurement_level, options FROM questions WHERE survey_id = :sid ORDER BY position"),
        {"sid": sid}
    )
    questions = q_result.fetchall()
    if not questions:
        return {"error": "No questions found in this survey."}

    r_result = await db.execute(
        text("SELECT answers FROM responses WHERE survey_id = :sid"),
        {"sid": sid}
    )
    responses = r_result.fetchall()
    if not responses:
        return {"error": "No responses found. Collect responses before checking normality."}

    rows = []
    for resp in responses:
        answers = _coerce_answers(resp[0])
        row = {}
        for q in questions:
            qid, vname, qtype, qtext, mlevel, opts = q
            val = answer_value(answers, qid, vname)
            row[_sanitize(vname or qid)] = val
        rows.append(row)

    df = pd.DataFrame(rows)
    meta_levels = {_sanitize(q[1] or q[0]): q[4] for q in questions}
    meta_labels = {_sanitize(q[1] or q[0]): _sanitize(q[3]) for q in questions}

    scale_cols = _get_scale_columns(questions)
    if not scale_cols:
        return {"error": "No scale/numeric questions found. Normality check requires ordinal, interval or ratio variables."}

    df_encoded = _encode_likert_dataframe(df[scale_cols], questions, scale_cols)
    df_num = df_encoded.apply(pd.to_numeric, errors="coerce")
    results = []
    for col in scale_cols:
        series = df_num[col].dropna()
        n = len(series)
        if n < 3:
            results.append({"variable": col, "label": meta_labels.get(col, col), "n": n, "error": "Too few observations (need >= 3)."})
            continue

        mean_val = float(series.mean())
        std_val  = float(series.std())
        skew_val = float(scipy_stats.skew(series))
        kurt_val = float(scipy_stats.kurtosis(series))

        # ── Shapiro-Wilk (n ≤ 2000, most powerful for small/medium n) ──────────
        sw_stat, sw_p = None, None
        if n <= 2000:
            try:
                sw_stat, sw_p = scipy_stats.shapiro(series)
                sw_stat, sw_p = float(sw_stat), float(sw_p)
            except Exception:
                pass

        # ── Kolmogorov-Smirnov with Lilliefors correction (n > 50) ────────────
        ks_stat, ks_p = None, None
        ks_method = None
        if n > 50:
            try:
                from statsmodels.stats.diagnostic import lilliefors as _lilliefors
                ks_stat, ks_p = _lilliefors(series, dist="norm")
                ks_stat, ks_p = float(ks_stat), float(ks_p)
                ks_method = "Lilliefors"
            except Exception:
                try:
                    ks_stat, ks_p = scipy_stats.kstest(series, "norm", args=(mean_val, std_val))
                    ks_stat, ks_p = float(ks_stat), float(ks_p)
                    ks_method = "KS (estimated params)"
                except Exception:
                    pass

        # ── Anderson-Darling (n ≥ 8, sensitive to tail deviations) ───────────
        ad_stat, ad_normal = None, None
        if n >= 8:
            try:
                ad_result = scipy_stats.anderson(series, dist="norm")
                ad_stat = round(float(ad_result.statistic), 4)
                # Critical value at 5% significance level (index 2)
                ad_cv_5pct = float(ad_result.critical_values[2])
                ad_normal = bool(ad_result.statistic < ad_cv_5pct)
            except Exception:
                pass

        # ── Jarque-Bera (skewness + kurtosis combined test) ───────────────────
        jb_stat, jb_p = None, None
        if n >= 8:
            try:
                jb_stat, jb_p = scipy_stats.jarque_bera(series)
                jb_stat, jb_p = float(jb_stat), float(jb_p)
            except Exception:
                pass

        sw_normal = (sw_p is not None and sw_p > 0.05)
        ks_normal = (ks_p is not None and ks_p > 0.05)
        jb_normal = (jb_p is not None and jb_p > 0.05)
        skew_ok   = abs(skew_val) < 2.0
        kurt_ok   = abs(kurt_val) < 7.0

        # Composite verdict: majority-vote among available formal tests
        # For large samples (n ≥ 200) relax formal test, rely on skew/kurtosis
        # (SW is overly powerful at large N — statistically significant but trivially non-normal)
        formal_tests = [v for v in [sw_normal, ks_normal, jb_normal, ad_normal] if v is not None]
        if n >= 200:
            is_normal = skew_ok and kurt_ok
        elif formal_tests:
            majority = (sum(formal_tests) / len(formal_tests)) >= 0.5
            is_normal = majority and skew_ok and kurt_ok
        else:
            is_normal = skew_ok and kurt_ok

        if abs(skew_val) < 0.5:      skew_desc = "Approximately symmetric"
        elif skew_val > 1:            skew_desc = "Strongly positively skewed"
        elif skew_val > 0:            skew_desc = "Positively skewed (right tail)"
        elif skew_val < -1:           skew_desc = "Strongly negatively skewed"
        else:                         skew_desc = "Negatively skewed (left tail)"

        if abs(kurt_val) < 1:         kurt_desc = "Mesokurtic (normal-like)"
        elif kurt_val > 0:            kurt_desc = "Leptokurtic (heavy tails / peaked)"
        else:                         kurt_desc = "Platykurtic (thin tails / flat)"

        if not is_normal:
            if not skew_ok:
                recommendation = "Consider log or square-root transformation to reduce skewness before parametric analysis."
            elif not kurt_ok:
                recommendation = "High kurtosis detected. Consider robust statistical methods or non-parametric alternatives."
            elif formal_tests and not (sum(formal_tests) / len(formal_tests) >= 0.5):
                recommendation = "Majority of normality tests failed. Non-parametric tests (Mann-Whitney, Kruskal-Wallis, Spearman) are recommended."
            else:
                recommendation = "Minor non-normality detected. Check histogram/Q-Q plot; parametric tests may still be appropriate."
        else:
            recommendation = None

        results.append({
            "variable": col, "label": meta_labels.get(col, col), "n": n,
            "mean": round(mean_val, 3), "std": round(std_val, 3),
            "skewness": round(skew_val, 3), "skewness_desc": skew_desc,
            "kurtosis": round(kurt_val, 3), "kurtosis_desc": kurt_desc,
            # Shapiro-Wilk
            "shapiro_wilk_stat": round(sw_stat, 4) if sw_stat is not None else None,
            "shapiro_wilk_p": round(sw_p, 4) if sw_p is not None else None,
            "sw_normal": sw_normal,
            # Lilliefors / KS
            "ks_stat": round(ks_stat, 4) if ks_stat is not None else None,
            "ks_p": round(ks_p, 4) if ks_p is not None else None,
            "ks_method": ks_method,
            "ks_normal": ks_normal,
            # Anderson-Darling
            "anderson_darling_stat": ad_stat,
            "anderson_darling_normal": ad_normal,
            # Jarque-Bera
            "jarque_bera_stat": round(jb_stat, 4) if jb_stat is not None else None,
            "jarque_bera_p": round(jb_p, 4) if jb_p is not None else None,
            "jb_normal": jb_normal,
            # Composite verdict
            "is_normal": is_normal, "skew_ok": skew_ok, "kurt_ok": kurt_ok,
            "n_tests_passed": sum(1 for v in formal_tests if v),
            "n_tests_run": len(formal_tests),
            "recommendation": recommendation,
        })

    n_normal     = sum(1 for r in results if r.get("is_normal") is True)
    n_non_normal = sum(1 for r in results if r.get("is_normal") is False)
    n_vars       = len(results)

    if n_non_normal == 0:
        verdict  = f"All {n_vars} variable(s) appear normally distributed. Parametric tests are appropriate."
        severity = "ok"
    elif n_non_normal < n_vars / 2:
        verdict  = f"{n_non_normal} of {n_vars} variable(s) deviate from normality. Consider non-parametric alternatives or data transformation."
        severity = "moderate"
    else:
        verdict  = f"{n_non_normal} of {n_vars} variable(s) are non-normal. Non-parametric tests (Mann-Whitney, Kruskal-Wallis, Spearman) are recommended."
        severity = "high"

    result = {
        "n_respondents": len(df_num), "n_variables_checked": n_vars,
        "n_normal": n_normal, "n_non_normal": n_non_normal,
        "severity": severity, "verdict": verdict, "results": results,
        "note": (
            "Shapiro-Wilk is used for n <= 2000 (most accurate for small/medium samples). "
            "Kolmogorov-Smirnov additionally reported for n > 50. "
            "For large samples (n > 200), minor deviations are often statistically significant but practically irrelevant — check skewness and kurtosis too."
        ),
    }
    _cache_set(user.id, sid, "normality", result)
    return result
