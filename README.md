# ResearchForm — Academic Research Platform

**Survey Builder + 9-Stage AI Analysis Pipeline + Chapter 4 Generator**

> Built for Nigerian and West African academic researchers: build surveys, collect data, decode SPSS/Excel/CSV, run AI-selected statistical tests, and generate a fully formatted Chapter 4 Word document.

---

## Architecture

```
Frontend (Next.js 14)          Backend (FastAPI)          Workers
─────────────────────          ──────────────────          ───────
Dashboard                      /auth      JWT login        Celery
Survey Builder (DnD)           /surveys   CRUD             9-stage pipeline
Respondent Form                /public    survey links     background tasks
Decode Review Gate             /analysis  pipeline API
Analysis Progress              /export    CSV/XLSX/SAV
Reports Download               /storage   charts + .docx

Database: PostgreSQL 15
Cache/Queue: Redis 7
LLM: Anthropic Claude Sonnet 4
```

---

## 9-Stage Pipeline

| Stage | Name | What happens |
|-------|------|-------------|
| **1** | Data Assembly | Pull survey DB responses or accept uploaded file |
| **2 ★** | **Data Decode** | Parse + clean + label resolve + level infer + data dictionary |
| **3** | Brief Parsing | Structure research objectives, hypotheses, DV/IV |
| **4** | Test Selection | Claude AI selects correct statistical tests |
| **5** | Code Generation | Claude AI generates full Python analysis script |
| **6** | Code Execution | Run script in subprocess sandbox, capture JSON results |
| **7** | Visualisation | matplotlib/seaborn charts (means, correlation, distribution) |
| **8** | Report Writing | Claude AI writes Chapter 4 narrative in Nigerian university format |
| **9** | Document Build | python-docx builds Times New Roman 12pt, double-spaced .docx |

★ Stage 2 pauses and shows the researcher the decode review — they correct variable levels, assign DV/IV roles, and choose missing value strategy before analysis proceeds.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15
- Redis 7
- Anthropic API key

### Option A: Docker Compose (recommended)

```bash
git clone <repo>
cd researchform

# Create .env
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=$(openssl rand -hex 32)
EOF

docker compose up -d
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Option B: Manual Setup

**Backend:**
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up database
psql -U postgres -c "CREATE DATABASE researchform;"
psql -U postgres -d researchform -f init.sql

# Configure environment
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY, DATABASE_URL, etc.

# Start API
uvicorn main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A workers.tasks worker --loglevel=info
```

**Frontend:**
```bash
cd frontend

npm install

# Configure API URL
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

npm run dev
# → http://localhost:3000
```

---

## Environment Variables

### Backend (.env)

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/researchform
SYNC_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/researchform

# Authentication
SECRET_KEY=your_32_char_secret_here

# AI Engine
ANTHROPIC_API_KEY=sk-ant-...

# Redis
REDIS_URL=redis://localhost:6379/0

# CORS (add your frontend URL)
ALLOWED_ORIGINS=["http://localhost:3000"]
```

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Project Structure

```
researchform/
├── frontend/                   # Next.js 14 app
│   ├── src/
│   │   ├── pages/
│   │   │   ├── dashboard.tsx       # Dashboard with stats
│   │   │   ├── surveys/
│   │   │   │   ├── index.tsx       # Survey list
│   │   │   │   ├── new.tsx         # Survey builder (drag & drop)
│   │   │   │   └── [id].tsx        # Survey detail, share, export
│   │   │   ├── analysis/
│   │   │   │   ├── index.tsx       # Job list + file upload
│   │   │   │   └── [id].tsx        # Pipeline progress + decode review
│   │   │   ├── reports/index.tsx   # Download completed reports
│   │   │   ├── s/[slug].tsx        # Public respondent form
│   │   │   ├── settings.tsx        # Theme + profile settings
│   │   │   ├── login.tsx
│   │   │   └── _app.tsx
│   │   ├── components/
│   │   │   └── layout/AppLayout.tsx  # Sidebar + header + theme
│   │   ├── lib/
│   │   │   ├── api.ts              # Axios API client
│   │   │   └── store.ts            # Zustand: theme + survey + job
│   │   └── styles/globals.css      # CSS variables + all component styles
│   ├── tailwind.config.js
│   └── next.config.js
│
├── backend/                    # FastAPI app
│   ├── main.py                 # App entry point
│   ├── config.py               # Settings (pydantic-settings)
│   ├── requirements.txt
│   ├── init.sql                # Database schema + seed
│   ├── api/
│   │   ├── deps.py             # DB session + auth dependency
│   │   ├── models/database.py  # SQLAlchemy ORM models
│   │   └── routers/
│   │       ├── auth.py         # Login, register, me
│   │       ├── surveys.py      # Survey CRUD + questions + stats
│   │       ├── responses.py    # Public respondent endpoints
│   │       ├── analysis.py     # Pipeline trigger + job management
│   │       ├── export.py       # CSV, Excel, SPSS, PDF codebook
│   │       └── users.py        # User profile
│   └── analysis/
│       ├── pipeline.py         # Stages 3-9 orchestrator
│       └── decode/             # Stage 2 — Data Decode Module
│           ├── orchestrator.py
│           ├── parsers/
│           │   ├── spss_parser.py     # pyreadstat .sav
│           │   ├── excel_parser.py    # openpyxl .xlsx
│           │   ├── csv_parser.py      # pandas + chardet
│           │   └── db_parser.py       # PostgreSQL responses
│           ├── transforms/
│           │   ├── column_cleaner.py  # Sanitise variable names
│           │   ├── label_resolver.py  # SPSS value labels
│           │   ├── level_inferrer.py  # nominal/ordinal/interval/ratio
│           │   └── missing_handler.py # NaN detection + warnings
│           └── dictionary/
│               └── builder.py        # DataDictionary + LLM context
│
└── docker-compose.yml
```

---

## Key Features

### Survey Builder
- 10 question types: Short text, Long text, Single choice, Multi choice, Likert scale, Rating, Matrix, Number, Date, Section header
- Drag-and-drop reordering
- Auto-inferred measurement levels (nominal/ordinal/interval/ratio)
- Custom variable names for SPSS compatibility

### Survey Sharing
- Unique URL + QR code for each survey
- WhatsApp / Email sharing links
- Real-time response counter

### Data Export
- **CSV** — standard comma-separated
- **Excel (.xlsx)** — with Codebook tab, branded header row
- **SPSS (.sav)** — with value labels preserved (pyreadstat)
- **Codebook PDF** — variable definitions (reportlab)

### Decode Review (Stage 2 ★)
- Inspect every variable: measurement level, missing %, data type
- Correct level misclassifications before analysis
- Assign DV/IV/group/exclude roles
- Choose missing value strategy: flag_only, drop_rows, mean_impute, mode_impute

### Analysis Engine
- Claude AI selects tests: t-test, ANOVA, chi-square, Pearson/Spearman, Mann-Whitney, Kruskal-Wallis, Regression, Cronbach's Alpha
- Complete Python script generated and executed in subprocess sandbox
- Nigerian university hypothesis language: "The t-test yielded t(58) = 3.21, p = 0.002 which is less than the 0.05 level of significance. Therefore, H0 is rejected."

### Chapter 4 Report
- Times New Roman 12pt
- Double-spaced
- APA-style table citations
- Sections: Introduction, Demographic Data, Research Questions, Test of Hypotheses, Discussion, Summary
- Embedded charts (PNG)
- Download as .docx

---

## Theme

The app supports **Light** (white) and **Dark** (#212121) themes:

- Toggle in sidebar (Moon/Sun icon)
- Saved to localStorage via Zustand persist
- Configurable in Settings → Appearance
- CSS variables system — every colour respects `var(--bg)`, `var(--text)`, etc.

---

## Demo Credentials

After running `init.sql`:
- **Email:** demo@researchform.app
- **Password:** demo1234

---

## Statistical Tests Decision Tree

```
Two groups + interval/ratio DV      → Independent Samples t-test
Two groups + ordinal DV             → Mann-Whitney U
Three+ groups + interval/ratio DV   → One-Way ANOVA → Tukey post-hoc
Three+ groups + ordinal DV          → Kruskal-Wallis → Dunn's test
Two continuous variables            → Pearson r (or Spearman if ordinal)
Two categorical variables           → Chi-square test of association
Predict DV from multiple IVs        → Multiple Linear Regression
Likert scale reliability            → Cronbach's Alpha → composite mean
Descriptive (always)                → Frequencies, means, SD, percentages
```

---

## License

MIT — free for academic and commercial use.
