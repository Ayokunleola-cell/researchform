# backend/api/models/database.py
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey, Enum as SAEnum, JSON, Numeric, func, SmallInteger, BigInteger, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()

def gen_uuid():
    return str(uuid.uuid4())

class UserRole(str, enum.Enum):
    student="student"; researcher="researcher"; lecturer="lecturer"; admin="admin"; seller="seller"
    analyst="analyst"; manager="manager"; hr="hr"; consultant="consultant"; other="other"

class SurveyStatus(str, enum.Enum):
    draft="draft"; active="active"; closed="closed"; analysed="analysed"

class QuestionType(str, enum.Enum):
    short_text="short_text"; long_text="long_text"; single_choice="single_choice"
    multi_choice="multi_choice"; likert="likert"; rating="rating"; matrix="matrix"
    number="number"; date="date"; section_header="section_header"
    rank_order="rank_order"; constant_sum="constant_sum"; slider="slider"
    nps="nps"; dropdown="dropdown"; semantic_differential="semantic_differential"
    file_upload="file_upload"

class MeasurementLevel(str, enum.Enum):
    nominal="nominal"; ordinal="ordinal"; interval="interval"; ratio="ratio"

class JobStatus(str, enum.Enum):
    pending="pending"; assembling="assembling"; cleaning="cleaning"; inspecting="inspecting"
    awaiting_preprocessing_choice="awaiting_preprocessing_choice"
    decoding="decoding"; decode_review="decode_review"; parsing="parsing"; selecting="selecting"
    generating="generating"; executing="executing"; visualising="visualising"
    thematic_analysis="thematic_analysis"  # qualitative strand
    writing="writing"; building="building"; complete="complete"; failed="failed"

class CreditTransactionType(str, enum.Enum):
    signup_bonus = "signup_bonus"
    purchase = "purchase"
    report_download = "report_download"
    adjustment = "adjustment"
    refund = "refund"
    chat_inference = "chat_inference"
    referral_commission = "referral_commission"

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    institution = Column(String)
    role = Column(SAEnum(UserRole), default=UserRole.student)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    username = Column(String(100), unique=True)
    bio = Column(Text)
    avatar_path = Column(Text)
    is_verified = Column(Boolean, default=False)
    mfa_secret = Column(String, nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    preferences = Column(JSON, default=dict)
    
    # KYC
    kyc_status = Column(String(20), default="unverified") # unverified, pending, verified, rejected

    # Referral fields
    referral_code = Column(String(12), unique=True, nullable=True, index=True)
    referred_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    referral_earnings = Column(Numeric(12, 4), default=Decimal("0"))  # total credits earned via referrals

    # Relationships
    surveys = relationship("Survey", back_populates="owner")
    credit_wallet = relationship("CreditWallet", back_populates="user", uselist=False)
    credit_transactions = relationship("CreditTransaction", back_populates="user")

    # Referral relationships
    referrals_made = relationship("ReferralEvent", foreign_keys="ReferralEvent.referrer_id", back_populates="referrer")
    referral_received = relationship("ReferralEvent", foreign_keys="ReferralEvent.referee_id", back_populates="referee", uselist=False)

    # Marketplace Relationships
    datasets = relationship("Dataset", back_populates="seller")
    seller_wallet = relationship("SellerWallet", back_populates="user", uselist=False)
    purchases = relationship("Purchase", foreign_keys="Purchase.buyer_id", back_populates="buyer")
    seller_verification = relationship("SellerVerification", primaryjoin="SellerVerification.user_id == User.id", back_populates="user", uselist=False, viewonly=False)

    # Integrations
    integrations = relationship("UserIntegration", back_populates="user")
    data_feed_tokens = relationship("DataFeedToken", back_populates="user")

class UserIntegration(Base):
    __tablename__ = "user_integrations"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    provider = Column(String, nullable=False) # e.g. "google"
    access_token = Column(String)
    refresh_token = Column(String)
    token_expiry = Column(DateTime)
    account_email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="integrations")

class DataFeedToken(Base):
    __tablename__ = "data_feed_tokens"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    resource_type = Column(String) # "survey" or "dataset"
    resource_id = Column(String)
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="data_feed_tokens")

class UserOTP(Base):
    __tablename__ = "user_otps"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    otp_code = Column(String(10), nullable=False)
    purpose = Column(String(50), nullable=False) # 'login' or 'register'
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")

class Survey(Base):
    __tablename__ = "surveys"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, default="")
    project_brief = Column(JSON, default={})
    slug = Column(String, unique=True, index=True)
    status = Column(SAEnum(SurveyStatus), default=SurveyStatus.draft)
    response_limit = Column(Integer)
    closes_at = Column(DateTime)
    allow_multiple = Column(Boolean, default=False)
    require_email = Column(Boolean, default=False)
    theme = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner = relationship("User", back_populates="surveys")
    questions = relationship("Question", back_populates="survey", order_by="Question.position", cascade="all, delete-orphan")
    responses = relationship("Response", back_populates="survey", cascade="all, delete-orphan")
    jobs = relationship("AnalysisJob", back_populates="survey")

class SystemSettings(Base):
    __tablename__ = "system_settings"
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    description = Column(String)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=func.now())

class Question(Base):
    __tablename__ = "questions"
    id = Column(String, primary_key=True, default=gen_uuid)
    survey_id = Column(String, ForeignKey("surveys.id"), nullable=False)
    position = Column(Integer, default=0)
    type = Column(SAEnum(QuestionType), nullable=False)
    text = Column(Text, default="")
    required = Column(Boolean, default=True)
    options = Column(JSON, default=[])
    scale_min = Column(Integer, default=1)
    scale_max = Column(Integer, default=5)
    variable_name = Column(String)
    measurement_level = Column(SAEnum(MeasurementLevel), default=MeasurementLevel.nominal)
    rows = Column(JSON, default=[])
    columns = Column(JSON, default=[])
    # ── Advanced quality controls ────────────────────────────────
    helper_text = Column(Text, nullable=True)                  # shown below question text
    randomize_options = Column(Boolean, default=False)         # shuffle choices on render
    validation_rules = Column(JSON, default={})                # {min_length,max_length,min_val,max_val,regex,preset}
    logic_rules = Column(JSON, default=[])                     # [{condition_q_id,operator,value,action}]
    is_attention_check = Column(Boolean, default=False)        # flag wrong answers
    correct_answer = Column(JSON, nullable=True)               # expected correct answer value
    survey = relationship("Survey", back_populates="questions")

class Response(Base):
    __tablename__ = "responses"
    id = Column(String, primary_key=True, default=gen_uuid)
    survey_id = Column(String, ForeignKey("surveys.id"), nullable=False)
    participant_email = Column(String, nullable=True)
    answers = Column(JSON, nullable=False, default={})
    submitted_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String)
    duration_seconds = Column(Integer)
    flags = Column(JSON, default={})  # {attention_check_failed: bool, failed_check_ids: [qid,...]}
    survey = relationship("Survey", back_populates="responses")

class CreditWallet(Base):
    """Analysis credits (separate from DataNest marketplace money)."""
    __tablename__ = "credit_wallets"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    balance = Column(Numeric(12, 4), nullable=False, default=Decimal("0"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="credit_wallet")
    user = relationship("User", back_populates="credit_wallet")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 4), nullable=False)  # positive = credit in, negative = debit
    type = Column(SAEnum(CreditTransactionType), nullable=False)
    description = Column(String(512), default="")
    reference_id = Column(String, index=True)  # e.g. analysis job id or purchase id
    balance_after = Column(Numeric(12, 4), nullable=False)
    extra = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    user = relationship("User", back_populates="credit_transactions")


class ReferralEvent(Base):
    """Tracks each commission earned when a referred user purchases credits."""
    __tablename__ = "referral_events"
    id              = Column(String, primary_key=True, default=gen_uuid)
    referrer_id     = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    referee_id      = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    purchase_ref    = Column(String(200), unique=True, nullable=False)  # idempotency key
    package_id      = Column(String(50))                                # e.g. 'starter', 'pro'
    credits_purchased = Column(Numeric(12, 4), nullable=False)          # credits the referee bought
    amount_naira    = Column(Numeric(10, 2))                            # what referee paid in naira
    commission_pct  = Column(Numeric(5, 2), nullable=False)             # rate snapshotted at time
    credits_earned  = Column(Numeric(12, 4), nullable=False)            # credits awarded to referrer
    created_at      = Column(DateTime, default=datetime.utcnow)

    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referrals_made")
    referee  = relationship("User", foreign_keys=[referee_id],  back_populates="referral_received")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    survey_id = Column(String, ForeignKey("surveys.id"))
    status = Column(SAEnum(JobStatus), default=JobStatus.pending)
    source_type = Column(String)
    source_filename = Column(String)
    data_dictionary = Column(JSON)
    decode_warnings = Column(JSON, default=[])
    inspection_report = Column(JSON, default={})   # Stage 1: data inspection summary
    cleaning_summary = Column(JSON, default={})    # Stage 1: cleaning actions taken
    n_rows = Column(Integer)
    n_columns = Column(Integer)
    n_complete_rows = Column(Integer)
    researcher_overrides = Column(JSON, default={})
    missing_strategy = Column(String, default="flag_only")
    weight_column    = Column(String, nullable=True)          # survey case weight column name
    imputation_method = Column(String, nullable=True)         # 'mice' | 'knn' | None
    project_brief = Column(JSON, default={})
    selected_tests = Column(JSON, default=[])
    generated_code = Column(Text)
    results = Column(JSON)
    chart_paths = Column(JSON, default=[])
    html_tables = Column(JSON, default={})   # APA-formatted HTML tables {section: html_string}

    report_path = Column(String)
    presentation_path = Column(String)
    presentation_paid = Column(Boolean, default=False)
    presentation_llm_usage = Column(JSON, default=dict)
    error_message = Column(Text)
    decode_completed_at = Column(DateTime)
    analysis_started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    survey = relationship("Survey", back_populates="jobs")
    # Chapter upload: extracted plain text from researcher's Ch1/2/3 documents
    chapter_texts = Column(JSON, default={})   # {"chapter1": "...", "chapter2": "...", "chapter3": "...", "full_text": "..."}
    # Report type: chapter4 | academic_report | research_paper | business_report | executive_summary | technical_report
    report_type = Column(String, default="chapter4")
    # Academic tradition: standard | nigerian | uk | apa (only applies when report_type=chapter4)
    academic_tradition = Column(String, default="standard")
    # Training data: raw JSON report before building .docx (used for fine-tuning logs)
    report_text = Column(JSON, default={})
    # Formatting options for the final docx
    formatting_options = Column(JSON, default=dict)
    # Technique selection: list of technique IDs chosen by researcher (empty = AI auto-select)
    selected_techniques = Column(JSON, default=[])   # e.g. ["pearson","cronbach_alpha","linear_regression"]
    auto_select_techniques = Column(Boolean, default=True)  # True = let AI decide

    # ── Multi-strand research design fields ─────────────────────────────
    # study_types: list of selected paradigms e.g. ["quantitative","qualitative","experimental"]
    study_types = Column(JSON, default=["quantitative"])
    # sample_size: declared sample size (n) from researcher
    sample_size = Column(Integer, nullable=True)
    # qualitative_files: paths of uploaded interview/transcript files
    qualitative_files = Column(JSON, default=[])     # [{"name": "interview1.txt", "path": "..."}]
    # thematic_results: structured output from qualitative thematic pipeline
    thematic_results = Column(JSON, default={})      # {"themes": [...], "table": [...], "narrative": "..."}
    # Qualitative analysis settings
    qual_coding_approach = Column(String, default="inductive")   # inductive | deductive
    qual_min_themes = Column(Integer, default=3)
    # Experimental design flags
    has_pretest_posttest = Column(Boolean, default=False)
    has_control_group = Column(Boolean, default=False)
    # Case study settings
    n_cases = Column(Integer, default=1)
    case_analysis_approach = Column(String, default="within")    # within | cross

    # ── Visualization settings ───────────────────────────────────────────
    auto_viz = Column(Boolean, default=True)         # True = AI picks chart types
    selected_viz = Column(JSON, default=[])          # e.g. ["bar","histogram","scatter"]

    # ── Table settings ──────────────────────────────────────────────────
    auto_tables = Column(Boolean, default=True)      # True = AI generates all relevant tables
    selected_tables = Column(JSON, default=[])       # e.g. ["descriptive","test_results","correlation"]

    # ── Usage-based analysis billing (Claude / LLM tokens → credits) ──
    llm_usage = Column(JSON, default=dict)           # token totals per pipeline run
    credits_estimated = Column(Numeric(12, 4))       # computed after analysis completes
    credits_charged = Column(Numeric(12, 4))         # deducted on report download
    report_paid = Column(Boolean, default=False)     # True once report download paid

    # ── Preprocessing mode (Stage 1 gate) ──────────────────────────────
    # Set by user via POST /analysis/{id}/preprocessing-choice
    preprocessing_mode = Column(String, nullable=True)  # 'auto' | 'manual'
    manual_choices = Column(JSON, default={})            # {"col": "strategy", ...}

class AnalysisChat(Base):
    __tablename__ = "analysis_chats"
    id = Column(String, primary_key=True, default=gen_uuid)
    job_id = Column(String, ForeignKey("analysis_jobs.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"))
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)



# --- DataNest Marketplace Models ----------------------------------------------

class DatasetStatus:
    DRAFT = "draft"; PENDING = "pending_verification"; VERIFIED = "verified"
    REJECTED = "rejected"; SUSPENDED = "suspended"; ARCHIVED = "archived"

class PurchaseStatus:
    PENDING = "pending"; COMPLETED = "completed"
    REFUNDED = "refunded"; DISPUTED = "disputed"

class SellerVerifStatus:
    UNVERIFIED = "unverified"; PENDING = "pending"
    VERIFIED = "verified"; SUSPENDED = "suspended"


# ─── Models ──────────────────────────────────────────────────────────────────
class Dataset(Base):
    __tablename__ = "datasets"
    id                  = Column(String(36), primary_key=True, default=gen_uuid)
    seller_id           = Column(String(36), ForeignKey("users.id"), nullable=True)
    title               = Column(String(200), nullable=False)
    slug                = Column(String(250), unique=True, nullable=False, index=True)
    description         = Column(Text)
    domain              = Column(String(100))
    sub_domain          = Column(String(100))
    country             = Column(String(100))
    collection_method   = Column(String(50))
    year_collected      = Column(SmallInteger)
    sample_size         = Column(Integer)
    primary_file_path   = Column(Text)
    thumbnail_path      = Column(Text)
    sample_file_path    = Column(Text)
    proof_document_path = Column(Text)
    price_naira         = Column(Numeric(10,2), default=0.00)
    price_usd           = Column(Numeric(10,2), default=0.00)
    license             = Column(String(50), default="CC-BY")
    status              = Column(String(50), default="pending_verification")
    rejection_reason    = Column(Text)
    content_fingerprint = Column(Text)    # JSON blob of col names + stat signatures
    visibility          = Column(String(50), default="public")
    verification_score  = Column(SmallInteger, default=0)
    tags                = Column(JSON, default=list)
    has_pii_flag        = Column(Boolean, default=False)
    pii_review_notes    = Column(Text)
    download_count      = Column(Integer, default=0)
    purchase_count      = Column(Integer, default=0)
    view_count          = Column(Integer, default=0)
    average_rating      = Column(Numeric(3,2), default=0.00)
    featured            = Column(Boolean, default=False)
    doi                 = Column(String(100))
    from_survey_id      = Column(String(36), nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    verified_at         = Column(DateTime(timezone=True))
    published_at        = Column(DateTime(timezone=True))

    seller            = relationship("User", back_populates="datasets")
    files             = relationship("DatasetFile", back_populates="dataset", cascade="all, delete-orphan")
    verification_jobs = relationship("VerificationJob", back_populates="dataset", cascade="all, delete-orphan")
    purchases         = relationship("Purchase", back_populates="dataset")
    reviews           = relationship("DatasetReview", back_populates="dataset", cascade="all, delete-orphan")
    questions         = relationship("DatasetQuestion", back_populates="dataset", cascade="all, delete-orphan")


class DatasetFile(Base):
    __tablename__ = "dataset_files"
    id               = Column(String(36), primary_key=True, default=gen_uuid)
    dataset_id       = Column(String(36), ForeignKey("datasets.id"), nullable=False)
    format           = Column(String(20), nullable=False)
    file_path        = Column(Text, nullable=False)
    file_size_bytes  = Column(BigInteger)
    file_hash_sha256 = Column(String(64))
    row_count        = Column(Integer)
    column_count     = Column(Integer)
    encoding         = Column(String(30))
    is_primary       = Column(Boolean, default=False)
    download_count   = Column(Integer, default=0)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    dataset = relationship("Dataset", back_populates="files")


class VerificationJob(Base):
    __tablename__ = "verification_jobs"
    id                    = Column(String(36), primary_key=True, default=gen_uuid)
    dataset_id            = Column(String(36), ForeignKey("datasets.id"), nullable=False)
    triggered_by          = Column(String(30), default="upload")
    status                = Column(String(30), default="queued")
    auto_score            = Column(SmallInteger, default=0)
    format_check          = Column(Boolean)
    completeness_score    = Column(SmallInteger)
    duplicate_check       = Column(Boolean)
    pii_scan_result       = Column(JSON)
    pii_score             = Column(SmallInteger, default=0)
    metadata_completeness = Column(SmallInteger, default=0)
    manual_reviewer_id    = Column(String(36), ForeignKey("users.id"), nullable=True)
    manual_review_notes   = Column(Text)
    rejection_reason      = Column(Text)
    created_at            = Column(DateTime(timezone=True), server_default=func.now())
    completed_at          = Column(DateTime(timezone=True))

    dataset = relationship("Dataset", back_populates="verification_jobs")


class Purchase(Base):
    __tablename__ = "purchases"
    id                    = Column(String(36), primary_key=True, default=gen_uuid)
    buyer_id              = Column(String(36), ForeignKey("users.id"), nullable=False)
    dataset_id            = Column(String(36), ForeignKey("datasets.id"), nullable=False)
    price_paid_naira      = Column(Numeric(10,2), default=0.00)
    platform_fee_naira    = Column(Numeric(10,2), default=0.00)
    seller_earnings_naira = Column(Numeric(10,2), default=0.00)
    payment_provider      = Column(String(30))
    payment_reference     = Column(String(200))
    status                = Column(String(20), default="pending")
    download_token        = Column(String(100), unique=True)
    downloaded_at         = Column(DateTime(timezone=True))
    pushed_to_pipeline    = Column(Boolean, default=False)
    pipeline_job_id       = Column(String(36), nullable=True)
    created_at            = Column(DateTime(timezone=True), server_default=func.now())

    buyer   = relationship("User", foreign_keys=[buyer_id], back_populates="purchases")
    dataset = relationship("Dataset", back_populates="purchases")


class SellerWallet(Base):
    __tablename__ = "seller_wallets"
    id                    = Column(String(36), primary_key=True, default=gen_uuid)
    user_id               = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    balance_naira         = Column(Numeric(12,2), default=0.00)
    pending_naira         = Column(Numeric(12,2), default=0.00)
    total_earned_naira    = Column(Numeric(12,2), default=0.00)
    total_withdrawn_naira = Column(Numeric(12,2), default=0.00)
    
    # Payout Configuration
    payout_method         = Column(String(50), default="bank_transfer") # bank_transfer, paypal, wise, swift
    bank_name             = Column(String(100))
    account_number        = Column(String(200)) # Used for account number or IBAN
    account_name          = Column(String(200))
    paypal_email          = Column(String(255))
    swift_code            = Column(String(50))
    routing_number        = Column(String(50))
    
    verified_bank         = Column(Boolean, default=False)
    last_payout_at        = Column(DateTime(timezone=True))

    user         = relationship("User", back_populates="seller_wallet")
    transactions = relationship("WalletTransaction", back_populates="wallet", cascade="all, delete-orphan")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    id            = Column(String(36), primary_key=True, default=gen_uuid)
    wallet_id     = Column(String(36), ForeignKey("seller_wallets.id"), nullable=False)
    type          = Column(String(30), nullable=False)
    amount_naira  = Column(Numeric(10,2), nullable=False)
    reference_id  = Column(String(36))
    description   = Column(Text)
    balance_after = Column(Numeric(12,2))
    cleared       = Column(Boolean, default=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    wallet = relationship("SellerWallet", back_populates="transactions")


class DatasetReview(Base):
    __tablename__ = "dataset_reviews"
    __table_args__ = (UniqueConstraint("dataset_id", "reviewer_id"),)
    id                = Column(String(36), primary_key=True, default=gen_uuid)
    dataset_id        = Column(String(36), ForeignKey("datasets.id"), nullable=False)
    reviewer_id       = Column(String(36), ForeignKey("users.id"), nullable=False)
    rating            = Column(SmallInteger, nullable=False)
    title             = Column(String(200))
    body              = Column(Text)
    used_for          = Column(String(50))
    verified_purchase = Column(Boolean, default=False)
    helpful_count     = Column(Integer, default=0)
    seller_reply      = Column(Text)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())

    dataset  = relationship("Dataset", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class DatasetCollection(Base):
    __tablename__ = "dataset_collections"
    id                 = Column(String(36), primary_key=True, default=gen_uuid)
    creator_id         = Column(String(36), ForeignKey("users.id"), nullable=False)
    title              = Column(String(200), nullable=False)
    description        = Column(Text)
    cover_image_path   = Column(Text)
    is_curated         = Column(Boolean, default=False)
    dataset_ids        = Column(JSON, default=list)
    price_bundle_naira = Column(Numeric(10,2), default=0.00)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())


class SellerVerification(Base):
    __tablename__ = "seller_verifications"
    id                = Column(String(36), primary_key=True, default=gen_uuid)
    user_id           = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    status            = Column(String(20), default="unverified")
    verification_type = Column(String(30))
    institution_name  = Column(String(200))
    matric_number     = Column(String(100))
    id_document_path  = Column(Text)
    id_document_type  = Column(String(50))
    bank_name         = Column(String(100))
    account_number    = Column(String(50))
    account_name      = Column(String(150))
    verified_by       = Column(String(36), ForeignKey("users.id"), nullable=True)
    verified_at       = Column(DateTime(timezone=True))
    rejection_reason  = Column(Text)

    user       = relationship(
        "User",
        primaryjoin="SellerVerification.user_id == User.id",
        back_populates="seller_verification",
    )
    verifier   = relationship(
        "User",
        primaryjoin="SellerVerification.verified_by == User.id",
        foreign_keys="[SellerVerification.verified_by]",
    )


class DatasetWishlist(Base):
    __tablename__ = "dataset_wishlists"
    __table_args__ = (UniqueConstraint("user_id", "dataset_id"),)
    id         = Column(String(36), primary_key=True, default=gen_uuid)
    user_id    = Column(String(36), ForeignKey("users.id"), nullable=False)
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DatasetQuestion(Base):
    __tablename__ = "dataset_questions"
    id          = Column(String(36), primary_key=True, default=gen_uuid)
    dataset_id  = Column(String(36), ForeignKey("datasets.id"), nullable=False)
    asker_id    = Column(String(36), ForeignKey("users.id"), nullable=False)
    question    = Column(Text, nullable=False)
    answer      = Column(Text)
    answered_at = Column(DateTime(timezone=True))
    is_public   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    dataset = relationship("Dataset", back_populates="questions")
    asker   = relationship("User", foreign_keys=[asker_id])


class DataRequest(Base):
    __tablename__ = "data_requests"
    id           = Column(String(36), primary_key=True, default=gen_uuid)
    requester_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title        = Column(String(200), nullable=False)
    description  = Column(Text)
    domain       = Column(String(100))
    budget_naira = Column(Numeric(10,2))
    status       = Column(String(20), default="open")
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"
    id              = Column(String(36), primary_key=True, default=gen_uuid)
    user_id         = Column(String(36), ForeignKey("users.id"), nullable=False)
    amount          = Column(Numeric(12,2), nullable=False)
    status          = Column(String(20), default="pending") # pending, paid, rejected
    
    # Snapshot of payout details at time of request
    payout_method   = Column(String(50), default="bank_transfer")
    bank_name       = Column(String(100))
    account_number  = Column(String(50))
    account_name    = Column(String(150))
    paypal_email    = Column(String(255))
    swift_code      = Column(String(50))
    routing_number  = Column(String(50))
    
    rejection_reason= Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    processed_at    = Column(DateTime(timezone=True))
    processed_by    = Column(String(36), ForeignKey("users.id"))
    
    user = relationship("User", foreign_keys=[user_id])
    processor = relationship("User", foreign_keys=[processed_by])
