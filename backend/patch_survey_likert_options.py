"""
patch_survey_likert_options.py
Adds Strongly Disagree → Strongly Agree options to all Likert questions
in the Digital Work Environment survey, and renders section header
newlines properly.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models.database import Survey, Question, QuestionType

DB_PATH = os.path.join(os.path.dirname(__file__), "researchform_dev.db")
engine  = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
db      = Session()

# ── find the survey ──────────────────────────────────────────────────────────
survey = db.query(Survey).filter(
    Survey.title == "Digital Work Environment & Employee Wellbeing Study"
).first()

if not survey:
    print("Survey not found!")
    sys.exit(1)

print(f"Found survey: {survey.title} ({survey.id})")

LIKERT_5 = [
    "Strongly Disagree",
    "Disagree",
    "Neutral",
    "Agree",
    "Strongly Agree",
]

LIKERT_10 = [str(i) for i in range(1, 11)]   # for rating/NPS (not used here)

questions = db.query(Question).filter(Question.survey_id == survey.id).all()

updated = 0
for q in questions:
    # Fix Likert questions: add 5-point labels
    if q.type == QuestionType.likert:
        if not q.options or len(q.options) < 5:
            q.options = LIKERT_5
            updated += 1

    # Fix section headers: strip the \n and store the legend in helper_text
    if q.type == QuestionType.section_header and q.text:
        if "\n" in q.text:
            parts = q.text.split("\n", 1)
            q.text        = parts[0].strip()
            q.helper_text = parts[1].strip() if len(parts) > 1 else None
            updated += 1

db.commit()
print(f"Patched {updated} questions.")

# Print summary
for q in sorted(questions, key=lambda x: x.position):
    if q.type == QuestionType.likert:
        print(f"  [{q.position:02d}] LIKERT  {q.variable_name:6s} options={q.options}")
    elif q.type == QuestionType.section_header:
        print(f"  [{q.position:02d}] SECTION '{q.text}' | helper='{q.helper_text}'")
