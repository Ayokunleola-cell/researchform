# researchform/api/schemas/schemas.py
# ================================================================
# All Pydantic schemas for API validation
# ================================================================
from pydantic import BaseModel, EmailStr, Field, validator
from pydantic import ConfigDict
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
    rank_order = "rank_order"
    constant_sum = "constant_sum"
    slider = "slider"
    nps = "nps"
    dropdown = "dropdown"
    semantic_differential = "semantic_differential"
    file_upload = "file_upload"

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

    model_config = ConfigDict(from_attributes=True)

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
    randomize_options: bool = False
    validation_rules: Optional[Dict] = None
    logic_rules: Optional[List] = None
    is_attention_check: bool = False
    correct_answer: Optional[Any] = None

class QuestionOut(QuestionCreate):
    id: uuid.UUID
    survey_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)

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
    theme: Optional[dict] = None

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
    theme: Optional[dict] = None

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

    model_config = ConfigDict(from_attributes=True)

# ── RESPONSES ────────────────────────────────────────────────────
class AnswerCreate(BaseModel):
    question_id: uuid.UUID
    value: Any  # str | int | float | list | dict
    theme: Optional[dict] = None

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

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

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

# ── CHAT (Analysis Interaction) ──────────────────────────────────
class ChatMessageRequest(BaseModel):
    message: str

class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    tokens_used: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- DataNest Marketplace Schemas ----------------------------------------------
"""
DataNest — Pydantic request/response schemas
UUID fields use str for SQLite compatibility (Pydantic handles coercion)
"""
from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import Optional, List, Any
from datetime import datetime
from decimal import Decimal
import uuid


# ─── Auth ────────────────────────────────────────────────────────────────────
class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    institution: Optional[str] = None
    role: str = "student"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    role: str

class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    institution: Optional[str]
    role: str
    username: Optional[str]
    bio: Optional[str]
    avatar_path: Optional[str]
    created_at: Optional[datetime]
    model_config = {"from_attributes": True}


# ─── Dataset ─────────────────────────────────────────────────────────────────
class DatasetCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=50)
    domain: str
    sub_domain: Optional[str] = None
    country: str
    collection_method: str
    year_collected: int = Field(ge=1900, le=2100)
    sample_size: Optional[int] = None
    price_naira: Decimal = Field(default=Decimal("0.00"), ge=0)
    license: str = "CC-BY"
    tags: List[str] = []
    visibility: str = "public"

class DatasetUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    sub_domain: Optional[str] = None
    country: Optional[str] = None
    collection_method: Optional[str] = None
    year_collected: Optional[int] = None
    sample_size: Optional[int] = None
    price_naira: Optional[Decimal] = None
    license: Optional[str] = None
    tags: Optional[List[str]] = None
    visibility: Optional[str] = None

class DatasetFileOut(BaseModel):
    id: str
    format: str
    file_size_bytes: Optional[int]
    row_count: Optional[int]
    column_count: Optional[int]
    is_primary: bool
    download_count: int
    model_config = {"from_attributes": True}

class SellerOut(BaseModel):
    id: str
    full_name: Optional[str]
    username: Optional[str]
    institution: Optional[str]
    avatar_path: Optional[str]
    model_config = {"from_attributes": True}

class DatasetOut(BaseModel):
    id: str
    title: str
    slug: str
    description: Optional[str]
    domain: Optional[str]
    sub_domain: Optional[str]
    country: Optional[str]
    collection_method: Optional[str]
    year_collected: Optional[int]
    sample_size: Optional[int]
    price_naira: Optional[Decimal]
    price_usd: Optional[Decimal]
    license: Optional[str]
    status: str
    rejection_reason: Optional[str]
    visibility: Optional[str]
    verification_score: Optional[int]
    tags: Optional[List[Any]]
    has_pii_flag: Optional[bool]
    download_count: Optional[int]
    purchase_count: Optional[int]
    view_count: Optional[int]
    average_rating: Optional[Decimal]
    featured: Optional[bool]
    doi: Optional[str]
    created_at: Optional[datetime]
    verified_at: Optional[datetime]
    published_at: Optional[datetime]
    seller: Optional[SellerOut]
    files: List[DatasetFileOut] = []
    model_config = {"from_attributes": True}

class DatasetListItem(BaseModel):
    id: str
    title: str
    slug: str
    description: Optional[str]
    domain: Optional[str]
    country: Optional[str]
    price_naira: Optional[Decimal]
    license: Optional[str]
    status: Optional[str]
    rejection_reason: Optional[str]
    sample_size: Optional[int]
    download_count: Optional[int]
    average_rating: Optional[Decimal]
    thumbnail_path: Optional[str]
    tags: Optional[List[Any]]
    seller: Optional[SellerOut]
    files: List[DatasetFileOut] = []
    created_at: Optional[datetime]
    model_config = {"from_attributes": True}

class DatasetListResponse(BaseModel):
    items: List[DatasetListItem]
    total: int
    page: int
    per_page: int
    pages: int


# ─── Review ──────────────────────────────────────────────────────────────────
class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: Optional[str] = None
    body: Optional[str] = None
    used_for: Optional[str] = None

class ReviewOut(BaseModel):
    id: str
    rating: int
    title: Optional[str]
    body: Optional[str]
    used_for: Optional[str]
    verified_purchase: Optional[bool]
    helpful_count: Optional[int]
    seller_reply: Optional[str]
    created_at: Optional[datetime]
    reviewer: Optional[SellerOut]
    model_config = {"from_attributes": True}


# ─── Purchase ────────────────────────────────────────────────────────────────
class PurchaseOut(BaseModel):
    id: str
    dataset_id: str
    price_paid_naira: Optional[Decimal]
    status: str
    download_token: Optional[str]
    downloaded_at: Optional[datetime]
    pushed_to_pipeline: Optional[bool]
    pipeline_job_id: Optional[str]
    created_at: Optional[datetime]
    dataset: Optional[DatasetListItem]
    model_config = {"from_attributes": True}

class PaystackInitResponse(BaseModel):
    authorization_url: str
    access_code: str
    reference: str


# ─── Wallet ──────────────────────────────────────────────────────────────────
class WalletOut(BaseModel):
    id: str
    balance_naira: Optional[Decimal]
    pending_naira: Optional[Decimal]
    total_earned_naira: Optional[Decimal]
    total_withdrawn_naira: Optional[Decimal]
    bank_name: Optional[str]
    account_name: Optional[str]
    verified_bank: Optional[bool]
    last_payout_at: Optional[datetime]
    model_config = {"from_attributes": True}

class WalletTransactionOut(BaseModel):
    id: str
    type: str
    amount_naira: Optional[Decimal]
    description: Optional[str]
    balance_after: Optional[Decimal]
    created_at: Optional[datetime]
    model_config = {"from_attributes": True}

class BankDetailsUpdate(BaseModel):
    bank_name: str
    account_number: str
    account_name: str

class WithdrawalRequest(BaseModel):
    amount_naira: Decimal = Field(gt=0)


# ─── Verification ────────────────────────────────────────────────────────────
class VerificationJobOut(BaseModel):
    id: str
    status: str
    auto_score: Optional[int]
    format_check: Optional[bool]
    duplicate_check: Optional[bool]
    pii_score: Optional[int]
    metadata_completeness: Optional[int]
    manual_review_notes: Optional[str]
    rejection_reason: Optional[str]
    created_at: Optional[datetime]
    completed_at: Optional[datetime]
    model_config = {"from_attributes": True}

class SellerVerifSubmit(BaseModel):
    verification_type: str
    institution_name: str
    matric_number: Optional[str] = None

class AdminVerifyAction(BaseModel):
    action: str  # "approve" | "reject"
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None


# ─── Collections ─────────────────────────────────────────────────────────────
class CollectionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    dataset_ids: List[str] = []
    price_bundle_naira: Decimal = Decimal("0.00")

class CollectionOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    cover_image_path: Optional[str]
    is_curated: Optional[bool]
    dataset_ids: Optional[List[Any]]
    price_bundle_naira: Optional[Decimal]
    created_at: Optional[datetime]
    model_config = {"from_attributes": True}


# ─── Search ──────────────────────────────────────────────────────────────────
class SearchParams(BaseModel):
    q: Optional[str] = None
    domain: Optional[str] = None
    format: Optional[str] = None
    price_type: Optional[str] = None  # "free" | "paid"
    country: Optional[str] = None
    sort: str = "newest"
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    license: Optional[str] = None


# ─── Data Request ─────────────────────────────────────────────────────────────
class DataRequestCreate(BaseModel):
    title: str = Field(min_length=10, max_length=200)
    description: Optional[str] = None
    domain: Optional[str] = None
    budget_naira: Optional[Decimal] = None

class DataRequestOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    domain: Optional[str]
    budget_naira: Optional[Decimal]
    status: str
    created_at: Optional[datetime]
    model_config = {"from_attributes": True}


# ─── Pipeline push ────────────────────────────────────────────────────────────
class PipelinePushRequest(BaseModel):
    survey_id: Optional[str] = None
    project_title: Optional[str] = None

class PipelinePushResponse(BaseModel):
    job_id: str
    redirect_url: str
    message: str


# ─── From-survey listing ──────────────────────────────────────────────────────
class FromSurveyListingRequest(BaseModel):
    survey_id: str
    price_naira: Decimal = Decimal("0.00")
    license: str = "CC-BY"
    visibility: str = "public"
    additional_description: Optional[str] = None
    tags: List[str] = []

