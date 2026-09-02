import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models.database import Survey, Question, Response, User, SurveyStatus

DB_PATH = os.path.join(os.path.dirname(__file__), "researchform_dev.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
db = Session()

user = db.query(User).filter(User.email == "demo@researchform.app").first()
print(f"User: {user.email} | ID: {user.id}")

surveys = db.query(Survey).filter(Survey.user_id == user.id).all()
print(f"Total surveys for demo user: {len(surveys)}")
for s in surveys:
    q_count = db.query(Question).filter(Question.survey_id == s.id).count()
    r_count = db.query(Response).filter(Response.survey_id == s.id).count()
    print(f"  [{s.status.value}] title='{s.title[:60]}' | slug={s.slug} | Q={q_count} | R={r_count}")

# Make sure the wellbeing survey is active
wellbeing = db.query(Survey).filter(
    Survey.user_id == user.id,
    Survey.title.like("%Wellbeing%")
).first()

if wellbeing:
    wellbeing.status = SurveyStatus.active
    db.commit()
    print(f"\nSurvey confirmed ACTIVE:")
    print(f"  ID   : {wellbeing.id}")
    print(f"  Slug : {wellbeing.slug}")
    print(f"  Link : http://localhost:3000/s/{wellbeing.slug}")
    print(f"  Admin: http://localhost:3000/surveys/{wellbeing.id}")
else:
    print("WARNING: Wellbeing survey not found!")
