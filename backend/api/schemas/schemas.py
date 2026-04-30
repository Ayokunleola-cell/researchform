# researchform/api/schemas/schemas.py
# ================================================================
# All Pydantic schemas for API validation
# ================================================================
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Any, List, Dict
from enum import Enum
from datetime import datetime
import uuid

# ── ENUMS ────────────────────────────────────────────────────────
class UserRole(str, Enum):
    student = "student"
    researcher = "researcher"
    lecturer = "lecturer"
    admin = "admin"

class SurveyStatus(str, Enum):
    draft = "draft"
    active = "active"
    closed = "closed"
    analysed = "analysed"

class QuestionType(str, Enum):
    short_text = "short_text"
    long_text = "long_text"
    single_choice = "single_choice"
    multi_choice = "multi_choice"
    likert = "likert"
    rating = "rating"
    matrix = "matrix"
    number = "number"
    date = "date"
    section_header = "section_header"

class MeasurementLevel(str, Enum):
    nominal = "nominal"
    ordinal = "ordinal"
    interval = "interval"
    ratio = "ratio"

class JobStatus(str, Enum):
    pending = "pending"
    decoding = "decoding"
    decode_review = "decode_review"
    analysing = "analysing"
    complete = "complete"
    failed = "failed"

# ── AUTH ─────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    institution: Optional[str] = None
    role: UserRole = UserRole.student
    password: str = Field(min_length=8)

class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    institution: Optional[str]
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# ── PROJECT BRIEF ────────────────────────────────────────────────
class ProjectBrief(BaseModel):
    title: str
    study_type: str  # quantitative | qualitative | mixed
    objectives: List[str]
    null_hypothesis: Optional[str] = None
    alternative_hypothesis: Optional[str] = None
    significance_level: float = 0.05
    dependent_variable: Optional[str] = None
    independent_variable: Optional[str] = None
    control_variables: Optional[List[str]] = []

# ── QUESTIONS ────────────────────────────────────────────────────
class QuestionCreate(BaseModel):
    position: int = 0
    type: QuestionType
    text: str = Field(min_length=1, max_length=2000)
    required: bool = False
    options: Optional[Any] = None     # List[str] or matrix dict
    scale_min: int = 1
    scale_max: int = 5
    variable_name: Optional[str] = None
    measurement_level: Optional[MeasurementLevel] = None
    helper_text: Optional[str] = None

class QuestionOut(QuestionCreate):
    id: uuid.UUID
    survey_id: uuid.UUID

    class Config:
        from_attributes = True

# ── SURVEYS ──────────────────────────────────────────────────────
class SurveyCreate(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    description: Optional[str] = None
    project_brief: Optional[ProjectBrief] = None
    response_limit: Optional[int] = None
    closes_at: Optional[datetime] = None
    allow_multiple: bool = False
    require_email: bool = False
    show_progress: bool = True
    shuffle_q: bool = False

class SurveyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    project_brief: Optional[ProjectBrief] = None
    status: Optional[SurveyStatus] = None
    response_limit: Optional[int] = None
    closes_at: Optional[datetime] = None
    allow_multiple: Optional[bool] = None
    require_email: Optional[bool] = None
    show_progress: Optional[bool] = None
    shuffle_q: Optional[bool] = None

class SurveyOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: Optional[str]
    project_brief: Optional[Dict]
    slug: str
    status: SurveyStatus
    response_limit: Optional[int]
    closes_at: Optional[datetime]
    allow_multiple: bool
    require_email: bool
    created_at: datetime
    response_count: int = 0
    questions: List[QuestionOut] = []

    class Config:
        from_attributes = True

# ── RESPONSES ────────────────────────────────────────────────────
class AnswerCreate(BaseModel):
    question_id: uuid.UUID
    value: Any  # str | int | float | list | dict

class ResponseCreate(BaseModel):
    answers: List[AnswerCreate]
    respondent_token: Optional[str] = None
    email: Optional[str] = None

class ResponseOut(BaseModel):
    id: uuid.UUID
    survey_id: uuid.UUID
    is_complete: bool
    started_at: datetime
    submitted_at: Optional[datetime]

    class Config:
        from_attributes = True

# ── ANALYSIS ─────────────────────────────────────────────────────
class AnalysisStart(BaseModel):
    survey_id: Optional[uuid.UUID] = None   # use survey DB data
    source_type: str = "survey_db"          # spss | excel | csv | survey_db
    project_brief: Optional[ProjectBrief] = None

class DecodeOverride(BaseModel):
    variable_name: str
    measurement_level: Optional[MeasurementLevel] = None
    role: Optional[str] = None      # DV | IV | Control | ID | None

class DecodeReviewSubmit(BaseModel):
    job_id: uuid.UUID
    overrides: List[DecodeOverride] = []
    missing_strategy: str = "flag_only"  # flag_only | drop_rows | mean_impute | median_impute | mode_impute

class AnalysisJobOut(BaseModel):
    id: uuid.UUID
    survey_id: uuid.UUID
    status: JobStatus
    source_type: Optional[str]
    data_dictionary: Optional[Dict]
    decode_warnings: Optional[List]
    n_rows: Optional[int]
    n_columns: Optional[int]
    selected_tests: Optional[List]
    results: Optional[Dict]
    chart_paths: Optional[List]
    report_path: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

# ── EXPORT ───────────────────────────────────────────────────────
class ExportRequest(BaseModel):
    survey_id: uuid.UUID
    format: str  # csv | xlsx | sav | json | codebook

# ── DECODE SCHEMAS (for analysis/decode module) ──────────────────
class DecodeWarning(BaseModel):
    severity: str       # info | warning | error
    variable: Optional[str]
    message: str
    suggestion: str

class VariableMeta(BaseModel):
    # Identity
    original_name: str
    clean_name: str
    label: str
    question_text: Optional[str] = None
    # Type
    dtype: str
    measurement_level: MeasurementLevel
    inferred_by: str    # spss_metadata | question_type | nunique | range | manual
    # Completeness
    n_total: int
    n_valid: int
    n_missing: int
    pct_missing: float
    # Value summary
    value_labels: Optional[Dict[str, str]] = None
    unique_values: Optional[List[Any]] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_mean: Optional[float] = None
    value_std: Optional[float] = None
    sample_values: List[Any] = []
    # Flags
    high_missing: bool = False
    level_uncertain: bool = False
    has_value_labels: bool = False
    # Role (set by researcher in review UI)
    role: Optional[str] = None   # DV | IV | Control | ID | None

class DataDictionary(BaseModel):
    source_type: str
    source_filename: Optional[str]
    survey_id: Optional[str]
    decoded_at: str
    n_rows: int
    n_columns: int
    n_complete_rows: int
    variables: List[VariableMeta]
    nominal_vars: List[str]
    ordinal_vars: List[str]
    interval_vars: List[str]
    ratio_vars: List[str]
    warnings: List[DecodeWarning]
    llm_context: str   # Pre-formatted string injected into LLM prompts
