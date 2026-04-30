-- SQL Migration: Create all ResearchForm tables
-- Run: psql -U postgres -d researchform -f init.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    email         TEXT UNIQUE NOT NULL,
    full_name     TEXT NOT NULL,
    institution   TEXT,
    role          TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student','researcher','lecturer','admin')),
    hashed_password TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- Surveys
CREATE TABLE IF NOT EXISTS surveys (
    id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title          TEXT NOT NULL,
    description    TEXT DEFAULT '',
    project_brief  JSONB DEFAULT '{}',
    slug           TEXT UNIQUE NOT NULL,
    status         TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','closed','analysed')),
    response_limit INTEGER,
    closes_at      TIMESTAMP,
    created_at     TIMESTAMP DEFAULT NOW(),
    updated_at     TIMESTAMP DEFAULT NOW()
);

-- Questions
CREATE TABLE IF NOT EXISTS questions (
    id                TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    survey_id         TEXT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    position          INTEGER DEFAULT 0,
    type              TEXT NOT NULL CHECK (type IN ('short_text','long_text','single_choice','multi_choice','likert','rating','matrix','number','date','section_header')),
    text              TEXT DEFAULT '',
    required          BOOLEAN DEFAULT TRUE,
    options           JSONB DEFAULT '[]',
    scale_min         INTEGER DEFAULT 1,
    scale_max         INTEGER DEFAULT 5,
    variable_name     TEXT,
    measurement_level TEXT DEFAULT 'nominal' CHECK (measurement_level IN ('nominal','ordinal','interval','ratio')),
    rows              JSONB DEFAULT '[]',
    columns           JSONB DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_questions_survey ON questions(survey_id, position);

-- Responses
CREATE TABLE IF NOT EXISTS responses (
    id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    survey_id        TEXT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    answers          JSONB NOT NULL DEFAULT '{}',
    submitted_at     TIMESTAMP DEFAULT NOW(),
    ip_address       TEXT,
    duration_seconds INTEGER
);
CREATE INDEX IF NOT EXISTS idx_responses_survey ON responses(survey_id);

-- Analysis Jobs
CREATE TABLE IF NOT EXISTS analysis_jobs (
    id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    survey_id             TEXT REFERENCES surveys(id),
    status                TEXT NOT NULL DEFAULT 'pending',
    source_type           TEXT,
    source_filename       TEXT,

    -- Decode output
    data_dictionary       JSONB,
    decode_warnings       JSONB DEFAULT '[]',
    n_rows                INTEGER,
    n_columns             INTEGER,
    n_complete_rows       INTEGER,

    -- Researcher review
    researcher_overrides  JSONB DEFAULT '{}',
    missing_strategy      TEXT DEFAULT 'flag_only',

    -- Pipeline stages
    project_brief         JSONB DEFAULT '{}',
    selected_tests        JSONB DEFAULT '[]',
    generated_code        TEXT,
    results               JSONB,
    chart_paths           JSONB DEFAULT '[]',
    report_path           TEXT,
    error_message         TEXT,

    -- Timestamps
    decode_completed_at   TIMESTAMP,
    analysis_started_at   TIMESTAMP,
    completed_at          TIMESTAMP,
    created_at            TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_jobs_survey ON analysis_jobs(survey_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON analysis_jobs(status);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS surveys_updated_at ON surveys;
CREATE TRIGGER surveys_updated_at BEFORE UPDATE ON surveys FOR EACH ROW EXECUTE PROCEDURE update_updated_at();

-- Seed demo user (password: demo1234)
INSERT INTO users (id, email, full_name, institution, role, hashed_password)
VALUES (
    'demo-user-0001',
    'demo@researchform.app',
    'Demo Researcher',
    'University of Lagos',
    'researcher',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TI4fHQlU7sIMh8kDi2s.YpIf0aDa'  -- bcrypt of 'demo1234'
) ON CONFLICT (email) DO NOTHING;
