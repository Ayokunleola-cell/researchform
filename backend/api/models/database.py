# backend/api/models/database.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()

def gen_uuid():
    return str(uuid.uuid4())

class UserRole(str, enum.Enum):
    student="student"; researcher="researcher"; lecturer="lecturer"; admin="admin"

class SurveyStatus(str, enum.Enum):
    draft="draft"; active="active"; closed="closed"; analysed="analysed"

class QuestionType(str, enum.Enum):
    short_text="short_text"; long_text="long_text"; single_choice="single_choice"
    multi_choice="multi_choice"; likert="likert"; rating="rating"; matrix="matrix"
    number="number"; date="date"; section_header="section_header"

class MeasurementLevel(str, enum.Enum):
    nominal="nominal"; ordinal="ordinal"; interval="interval"; ratio="ratio"

class JobStatus(str, enum.Enum):
    pending="pending"; assembling="assembling"; decoding="decoding"
    decode_review="decode_review"; parsing="parsing"; selecting="selecting"
    generating="generating"; executing="executing"; visualising="visualising"
    writing="writing"; building="building"; complete="complete"; failed="failed"

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    institution = Column(String)
    role = Column(SAEnum(UserRole), default=UserRole.student)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    surveys = relationship("Survey", back_populates="owner")

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner = relationship("User", back_populates="surveys")
    questions = relationship("Question", back_populates="survey", order_by="Question.position", cascade="all, delete-orphan")
    responses = relationship("Response", back_populates="survey", cascade="all, delete-orphan")
    jobs = relationship("AnalysisJob", back_populates="survey")

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
    survey = relationship("Survey", back_populates="questions")

class Response(Base):
    __tablename__ = "responses"
    id = Column(String, primary_key=True, default=gen_uuid)
    survey_id = Column(String, ForeignKey("surveys.id"), nullable=False)
    answers = Column(JSON, nullable=False, default={})
    submitted_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String)
    duration_seconds = Column(Integer)
    survey = relationship("Survey", back_populates="responses")

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id = Column(String, primary_key=True, default=gen_uuid)
    survey_id = Column(String, ForeignKey("surveys.id"))
    status = Column(SAEnum(JobStatus), default=JobStatus.pending)
    source_type = Column(String)
    source_filename = Column(String)
    data_dictionary = Column(JSON)
    decode_warnings = Column(JSON, default=[])
    n_rows = Column(Integer)
    n_columns = Column(Integer)
    n_complete_rows = Column(Integer)
    researcher_overrides = Column(JSON, default={})
    missing_strategy = Column(String, default="flag_only")
    project_brief = Column(JSON, default={})
    selected_tests = Column(JSON, default=[])
    generated_code = Column(Text)
    results = Column(JSON)
    chart_paths = Column(JSON, default=[])
    report_path = Column(String)
    error_message = Column(Text)
    decode_completed_at = Column(DateTime)
    analysis_started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    survey = relationship("Survey", back_populates="jobs")
