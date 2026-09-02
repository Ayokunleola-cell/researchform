# backend/scratch_health_survey_auto_ai.py
import asyncio
import uuid
import random
from datetime import datetime, timedelta
from sqlalchemy import select
from api.deps import AsyncSessionLocal
from api.models.database import User, Survey, Question, QuestionType, Response, AnalysisJob, JobStatus
from api.routers.analysis import _run_pipeline

async def run():
    async with AsyncSessionLocal() as db:
        print("=== 1. Getting Test User ===")
        res = await db.execute(select(User).limit(1))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                email="dr.health@researchform.com",
                full_name="Dr. Sarah Jenkins",
                institution="Global Health Research Institute",
                role="Principal Investigator",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        print(f"User: {user.email} ({user.id})")

        print("=== 2. Creating Health & Clinical Survey ===")
        survey_id = str(uuid.uuid4())
        slug = f"health-sleep-study-{random.randint(1000, 9999)}"
        survey = Survey(
            id=survey_id,
            user_id=user.id,
            title="2026 Comprehensive Health, Sleep Quality & Lifestyle Study",
            description="An empirical clinical research study analyzing lifestyle factors, sleep architecture, stress levels, and cardiovascular indicators.",
            slug=slug,
            status="active",
            allow_multiple=False,
            require_email=True,
            project_brief={
                "research_goal": "Investigate correlations between sleep duration, exercise frequency, stress, and systolic blood pressure.",
                "target_audience": "Adult demographic participants across varying physical activity levels.",
                "dependent_variable": "systolic_bp",
                "independent_variable": "sleep_hours",
                "hypotheses": [
                    "Increased daily sleep hours correlates with lower systolic blood pressure.",
                    "Higher stress levels correlate with reduced physical energy.",
                    "Exercise frequency significantly impacts overall mental well-being."
                ]
            }
        )
        db.add(survey)

        print("=== 3. Adding Health Survey Questions ===")
        questions_data = [
            {
                "type": QuestionType.section_header,
                "text": "Part I: Participant Profile & Demographics",
                "position": 0,
            },
            {
                "type": QuestionType.number,
                "text": "What is your current age?",
                "helper_text": "Enter age in years (18-85)",
                "required": True,
                "variable_name": "age",
                "validation_rules": {"min": 18, "max": 85},
                "position": 1,
            },
            {
                "type": QuestionType.single_choice,
                "text": "What is your gender?",
                "options": ["Female", "Male", "Non-binary / Prefer not to say"],
                "required": True,
                "variable_name": "gender",
                "position": 2,
            },
            {
                "type": QuestionType.dropdown,
                "text": "What is your primary employment / activity status?",
                "options": ["Full-Time Corporate", "Self-Employed", "Student", "Healthcare Professional", "Retired"],
                "required": True,
                "variable_name": "activity_status",
                "position": 3,
            },
            {
                "type": QuestionType.section_header,
                "text": "Part II: Physical Health & Sleep Metrics",
                "position": 4,
            },
            {
                "type": QuestionType.number,
                "text": "Average daily sleep duration (in hours)",
                "helper_text": "e.g. 7.5",
                "required": True,
                "variable_name": "sleep_hours",
                "validation_rules": {"min": 3, "max": 12},
                "position": 5,
            },
            {
                "type": QuestionType.number,
                "text": "Most recent Systolic Blood Pressure reading (mmHg)",
                "helper_text": "e.g. 120",
                "required": True,
                "variable_name": "systolic_bp",
                "validation_rules": {"min": 85, "max": 190},
                "position": 6,
            },
            {
                "type": QuestionType.slider,
                "text": "Daily Water Intake (Liters: 1.0 to 5.0)",
                "options": ["1.0", "5.0"],
                "required": True,
                "variable_name": "water_intake_liters",
                "position": 7,
            },
            {
                "type": QuestionType.single_choice,
                "text": "Weekly Exercise Frequency",
                "options": ["Sedentary (0 days)", "Light (1-2 days/wk)", "Moderate (3-4 days/wk)", "Vigorous (5+ days/wk)"],
                "required": True,
                "variable_name": "exercise_freq",
                "position": 8,
            },
            {
                "type": QuestionType.single_choice,
                "text": "Primary Pre-existing Condition Category",
                "options": ["None / Healthy", "Cardiovascular", "Metabolic (e.g. Diabetes)", "Respiratory", "Musculoskeletal"],
                "required": True,
                "variable_name": "health_condition",
                "position": 9,
            },
            {
                "type": QuestionType.likert,
                "text": "How would you rate your average daily stress level?",
                "options": ["1 - Very Low", "2 - Low", "3 - Moderate", "4 - High", "5 - Extremely High"],
                "required": True,
                "variable_name": "stress_level",
                "position": 10,
            },
            {
                "type": QuestionType.rating,
                "text": "Overall Physical Energy Rating",
                "options": ["1", "2", "3", "4", "5"],
                "required": True,
                "variable_name": "energy_rating",
                "position": 11,
            },
            {
                "type": QuestionType.semantic_differential,
                "text": "Select where your general state of vitality falls between these poles:",
                "options": ["Chronically Exhausted", "Fully Energetic & Revitalized"],
                "required": True,
                "variable_name": "vitality_semantic",
                "position": 12,
            },
            {
                "type": QuestionType.nps,
                "text": "How likely are you to recommend digital health tracking devices to peers?",
                "options": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
                "required": True,
                "variable_name": "nps_health_tracker",
                "position": 13,
            },
            {
                "type": QuestionType.constant_sum,
                "text": "Allocate 100 points across your personal health focus areas:",
                "options": ["Sleep Hygiene", "Balanced Diet", "Physical Exercise", "Stress Management", "Hydration"],
                "required": True,
                "variable_name": "health_points_alloc",
                "position": 14,
            },
            {
                "type": QuestionType.matrix,
                "text": "Rate your satisfaction with the following health support services:",
                "options": ["Primary Care Access", "Mental Health Resources", "Preventive Screening Options"],
                "required": True,
                "variable_name": "health_services_satisfaction",
                "position": 15,
            },
            {
                "type": QuestionType.long_text,
                "text": "Describe any key lifestyle changes you have made in the past 12 months to improve your overall health.",
                "required": False,
                "variable_name": "qual_lifestyle_changes",
                "position": 16,
            }
        ]

        created_questions = []
        for q_data in questions_data:
            q_id = str(uuid.uuid4())
            q = Question(
                id=q_id,
                survey_id=survey_id,
                type=q_data["type"],
                text=q_data["text"],
                helper_text=q_data.get("helper_text"),
                options=q_data.get("options"),
                required=q_data.get("required", False),
                variable_name=q_data.get("variable_name"),
                position=q_data["position"],
                validation_rules=q_data.get("validation_rules")
            )
            db.add(q)
            created_questions.append(q)

        await db.commit()
        print(f"Created {len(created_questions)} questions.")

        print("=== 4. Generating 50 Realistic Synthetic Participant Responses ===")
        genders = ["Female", "Male", "Non-binary / Prefer not to say"]
        statuses = ["Full-Time Corporate", "Self-Employed", "Student", "Healthcare Professional", "Retired"]
        exercises = ["Sedentary (0 days)", "Light (1-2 days/wk)", "Moderate (3-4 days/wk)", "Vigorous (5+ days/wk)"]
        conditions = ["None / Healthy", "Cardiovascular", "Metabolic (e.g. Diabetes)", "Respiratory", "Musculoskeletal"]
        qual_comments = [
            "Started walking 10,000 steps daily and maintaining consistent bedtime routines.",
            "Cut out caffeine after 2 PM and increased daily water intake significantly.",
            "Incorporated morning mindfulness meditation and strength training thrice weekly.",
            "Switched to a whole-foods plant-based diet and reduced processed sugar intake.",
            "Prioritized 8 hours of sleep per night, resulting in substantially more workplace energy."
        ]

        for i in range(50):
            age_val = random.randint(22, 72)
            # Simulate correlation: higher sleep & exercise -> lower BP & lower stress
            exercise_idx = random.randint(0, 3)
            sleep = round(random.uniform(5.0, 9.0) + (exercise_idx * 0.4), 1)
            sleep = min(10.0, max(4.0, sleep))
            
            # Systolic BP inversely related to sleep & exercise
            bp = int(140 - (sleep * 2.5) - (exercise_idx * 3) + random.gauss(0, 5))
            bp = max(95, min(175, bp))
            
            water = round(random.uniform(1.5, 4.0), 1)
            stress = max(1, min(5, int(6 - (sleep * 0.5) + random.gauss(0, 0.8))))
            energy = max(1, min(5, int(sleep * 0.6 + random.gauss(0, 0.5))))
            vitality_sem = max(1, min(7, int(sleep * 0.8 + random.gauss(0, 0.7))))
            nps_val = min(10, max(0, int(energy * 2 + random.randint(0, 1))))

            # Point allocation
            p1 = random.randint(20, 35)
            p2 = random.randint(15, 30)
            p3 = random.randint(10, 25)
            p4 = random.randint(10, 20)
            p5 = 100 - (p1 + p2 + p3 + p4)

            resp_answers = {
                created_questions[1].id: age_val,
                created_questions[2].id: random.choice(genders),
                created_questions[3].id: random.choice(statuses),
                created_questions[5].id: sleep,
                created_questions[6].id: bp,
                created_questions[7].id: water,
                created_questions[8].id: exercises[exercise_idx],
                created_questions[9].id: random.choice(conditions),
                created_questions[10].id: f"{stress} - Option",
                created_questions[11].id: str(energy),
                created_questions[12].id: vitality_sem,
                created_questions[13].id: nps_val,
                created_questions[14].id: {
                    "Sleep Hygiene": p1,
                    "Balanced Diet": p2,
                    "Physical Exercise": p3,
                    "Stress Management": p4,
                    "Hydration": p5
                },
                created_questions[15].id: {
                    "Primary Care Access": random.choice(["Satisfied", "Very Satisfied", "Neutral"]),
                    "Mental Health Resources": random.choice(["Neutral", "Satisfied", "Dissatisfied"]),
                    "Preventive Screening Options": random.choice(["Satisfied", "Very Satisfied"])
                },
                created_questions[16].id: random.choice(qual_comments),
            }

            resp_obj = Response(
                id=str(uuid.uuid4()),
                survey_id=survey_id,
                participant_email=f"patient_{i+1}@healthstudy.org",
                answers=resp_answers,
                flags={},
                submitted_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72))
            )
            db.add(resp_obj)

        await db.commit()
        print("Inserted 50 synthetic respondent records.")

        print("=== 5. Launching Analysis Job with AI Auto Selection ===")
        job_id = str(uuid.uuid4())
        job = AnalysisJob(
            id=job_id,
            user_id=user.id,
            survey_id=survey_id,
            status=JobStatus.pending,
            source_type="survey_db",
            project_brief=survey.project_brief,
            academic_tradition="standard",
            report_type="chapter4",
            auto_select_techniques=True, # AI Auto Statistical Test Selection
            auto_tables=True,            # AI Auto Table Selection
            auto_viz=True,               # AI Auto Chart Selection
            manual_choices=None
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        print(f"AnalysisJob {job.id} created with AI Auto Selection enabled!")
        print("Executing pipeline...")

        # Run pipeline directly
        _run_pipeline(job.id)
        print(f"\n SUCCESS! Analysis job {job.id} completed.")
        print(f"Respondent Survey Slug: http://localhost:3000/s/{slug}")
        print(f"Analysis Dashboard URL: http://localhost:3000/analysis/{job.id}")

if __name__ == "__main__":
    asyncio.run(run())
