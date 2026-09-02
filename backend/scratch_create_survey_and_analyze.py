# backend/scratch_create_survey_and_analyze.py
import asyncio
import uuid
import random
from datetime import datetime, timedelta
from sqlalchemy import select
from api.deps import AsyncSessionLocal
from api.models.database import User, Survey, Question, QuestionType, Response, AnalysisJob, JobStatus

async def run():
    async with AsyncSessionLocal() as db:
        print("=== 1. Finding or Creating Test User ===")
        res = await db.execute(select(User).where(User.email == "demo@researchform.app"))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                email="demo@researchform.app",
                full_name="Demo User",
                institution="Institute for Workplace Studies",
                role="admin",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        print(f"Using user: {user.email} ({user.id})")

        print("=== 2. Creating Full In-Depth Test Survey ===")
        survey_id = str(uuid.uuid4())
        slug = f"workplace-tech-study-{random.randint(1000, 9999)}"
        survey = Survey(
            id=survey_id,
            user_id=user.id,
            title="2026 Workplace Well-being Study (200 Responses)",
            description="An in-depth empirical investigation into remote work dynamics, organizational culture, productivity tool allocation, and employee retention.",
            slug=slug,
            status="active",
            allow_multiple=False,
            require_email=True,
            project_brief={
                "research_goal": "Evaluate the relationship between remote work flexibility, productivity tool satisfaction, and overall employee well-being.",
                "target_audience": "Knowledge workers and professionals across diverse corporate sectors.",
            }
        )
        db.add(survey)

        print("=== 3. Adding Questions for All Builder Question Types ===")
        questions_data = [
            # Part 1
            {
                "type": QuestionType.section_header,
                "text": "Part I: Professional Profile & Work Structure",
                "position": 0,
            },
            {
                "type": QuestionType.short_text,
                "text": "What is your primary job title?",
                "helper_text": "e.g. Senior Software Engineer, Product Designer, HR Specialist",
                "required": True,
                "variable_name": "job_title",
                "measurement_level": "nominal",
                "position": 1,
            },
            {
                "type": QuestionType.dropdown,
                "text": "Which department do you primarily work in?",
                "helper_text": "Select the department that best matches your daily operations.",
                "required": True,
                "options": ["Engineering", "Marketing", "Product Management", "Sales", "Human Resources", "Finance & Accounting", "Operations", "Data & Analytics"],
                "variable_name": "department",
                "measurement_level": "nominal",
                "position": 2,
            },
            {
                "type": QuestionType.single_choice,
                "text": "What is your primary work arrangement?",
                "required": True,
                "options": ["Fully Remote", "Hybrid (2-3 days in office)", "On-site / In Office"],
                "randomize_options": True,
                "variable_name": "work_arrangement",
                "measurement_level": "nominal",
                "position": 3,
            },
            {
                "type": QuestionType.number,
                "text": "How many total years of professional experience do you have?",
                "required": True,
                "validation_rules": {"min_val": 0, "max_val": 50, "integer_only": True},
                "variable_name": "years_experience",
                "measurement_level": "ratio",
                "position": 4,
            },
            # Part 2
            {
                "type": QuestionType.section_header,
                "text": "Part II: Organizational Climate & Satisfaction",
                "position": 5,
            },
            {
                "type": QuestionType.semantic_differential,
                "text": "How would you describe your current overall workplace environment?",
                "helper_text": "Rate your position between the two opposing descriptors.",
                "required": True,
                "options": ["Stressful / Exhausting", "Supportive / Energizing"],
                "scale_min": 1,
                "scale_max": 7,
                "variable_name": "environment_semantic",
                "measurement_level": "interval",
                "position": 6,
            },
            {
                "type": QuestionType.likert,
                "text": "I feel supported by my organization in maintaining a healthy work-life balance.",
                "required": True,
                "options": ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"],
                "variable_name": "worklife_balance_likert",
                "measurement_level": "ordinal",
                "position": 7,
            },
            {
                "type": QuestionType.rating,
                "text": "Rate the overall quality of workstation equipment provided by your employer.",
                "required": True,
                "scale_min": 1,
                "scale_max": 5,
                "variable_name": "equipment_rating",
                "measurement_level": "ordinal",
                "position": 8,
            },
            {
                "type": QuestionType.slider,
                "text": "On a scale of 0 to 100, what is your current weekly energy level at work?",
                "required": True,
                "scale_min": 0,
                "scale_max": 100,
                "options": ["Exhausted (0)", "Peak Energy (100)"],
                "variable_name": "energy_slider",
                "measurement_level": "ratio",
                "position": 9,
            },
            {
                "type": QuestionType.nps,
                "text": "How likely are you to recommend your organization to a colleague as a great place to work?",
                "required": True,
                "scale_min": 0,
                "scale_max": 10,
                "options": ["Not at all likely", "Extremely likely"],
                "variable_name": "nps_score",
                "measurement_level": "ordinal",
                "position": 10,
            },
            {
                "type": QuestionType.likert,
                "text": "Attention Check: For survey quality control, please select 'Agree' for this statement.",
                "required": True,
                "options": ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"],
                "is_attention_check": True,
                "correct_answer": "Agree",
                "variable_name": "attention_check_q",
                "measurement_level": "ordinal",
                "position": 11,
            },
            # Part 3
            {
                "type": QuestionType.section_header,
                "text": "Part III: Productivity & Tool Allocation",
                "position": 12,
            },
            {
                "type": QuestionType.multi_choice,
                "text": "Which digital tools do you rely on daily for collaborative work?",
                "helper_text": "Select all that apply.",
                "required": True,
                "options": ["Slack", "Microsoft Teams", "Notion", "ResearchForm", "Figma", "Jira", "Zoom"],
                "randomize_options": True,
                "variable_name": "daily_tools",
                "measurement_level": "nominal",
                "position": 13,
            },
            {
                "type": QuestionType.constant_sum,
                "text": "Please allocate 100 points across the following weekly activity categories:",
                "helper_text": "The total across all categories must equal exactly 100 points.",
                "required": True,
                "options": ["Deep Focus Work", "Team Meetings & Syncs", "Admin & Email Management", "Learning & Skill Building"],
                "scale_max": 100,
                "variable_name": "weekly_allocation",
                "measurement_level": "ratio",
                "position": 14,
            },
            {
                "type": QuestionType.rank_order,
                "text": "Rank your top 3 preferred workplace perks in order of preference:",
                "required": True,
                "options": ["Flexible Working Hours", "Professional Development Stipend", "Home Office Equipment Allowance", "Wellness & Mental Health Days", "Performance Bonuses"],
                "randomize_options": True,
                "variable_name": "perks_ranking",
                "measurement_level": "ordinal",
                "position": 15,
            },
            {
                "type": QuestionType.matrix,
                "text": "Rate your satisfaction with internal communications across key organizational areas:",
                "required": True,
                "rows": ["Company Strategy Updates", "Project Goals & Deadlines", "Peer Feedback Loops"],
                "columns": ["Dissatisfied", "Neutral", "Satisfied", "Very Satisfied"],
                "variable_name": "communication_matrix",
                "measurement_level": "ordinal",
                "position": 16,
            },
            # Part 4
            {
                "type": QuestionType.section_header,
                "text": "Part IV: Qualitative Insights & Review Timeline",
                "position": 17,
            },
            {
                "type": QuestionType.long_text,
                "text": "What single operational change would most enhance your productivity and work satisfaction?",
                "helper_text": "Share specific suggestions or bottlenecks.",
                "required": False,
                "variable_name": "qualitative_feedback",
                "measurement_level": "nominal",
                "position": 18,
            },
            {
                "type": QuestionType.date,
                "text": "What is the target date for your next annual performance review?",
                "required": False,
                "variable_name": "review_date",
                "measurement_level": "interval",
                "position": 19,
            },
            {
                "type": QuestionType.file_upload,
                "text": "Upload workspace proof or home setup photo (Optional)",
                "required": False,
                "validation_rules": {"accepted_types": ["images", "pdf"], "max_size_mb": 10},
                "variable_name": "workspace_file",
                "position": 20,
            }
        ]

        created_questions = []
        for qd in questions_data:
            q_id = str(uuid.uuid4())
            qd_copy = dict(qd)
            qd_copy["id"] = q_id
            qd_copy["survey_id"] = survey_id
            q_obj = Question(**qd_copy)
            db.add(q_obj)
            created_questions.append(q_obj)

        await db.commit()
        print(f"Created survey '{survey.title}' with {len(questions_data)} questions.")

        print("=== 4. Generating 200 Synthetic Responses ===")
        titles = ["Software Engineer", "Frontend Developer", "Product Manager", "Data Analyst", "UX Designer", "Marketing Manager", "HR Generalist", "Operations Associate"]
        departments = ["Engineering", "Marketing", "Product Management", "Sales", "Human Resources", "Finance & Accounting", "Operations", "Data & Analytics"]
        arrangements = ["Fully Remote", "Hybrid (2-3 days in office)", "On-site / In Office"]
        likert_opts = ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"]
        tools_pool = ["Slack", "Microsoft Teams", "Notion", "ResearchForm", "Figma", "Jira", "Zoom"]
        qual_comments = [
            "Streamline async updates and reduce unnecessary status meetings.",
            "Provide dedicated quiet focus blocks and better ergonomic equipment support.",
            "Implement clearer documentation for project handoffs and technical architecture.",
            "More budget allocation for continuous learning and conference attendance.",
            "Faster turnaround on cross-department approval processes.",
            "Standardize remote onboarding workflows and team knowledge bases.",
            "Greater transparency from executive leadership regarding quarterly milestones.",
            "Increase home office stipend to cover high-speed internet and monitors."
        ]

        for i in range(200):
            # 90% pass attention check, 10% fail
            passed_check = random.random() > 0.1
            att_answer = "Agree" if passed_check else random.choice(["Strongly Disagree", "Disagree", "Neutral"])
            
            # Constant sum allocations summing to 100
            p1 = random.randint(30, 50)
            p2 = random.randint(15, 30)
            p3 = random.randint(10, 20)
            p4 = 100 - (p1 + p2 + p3)

            resp_answers = {
                created_questions[1].id: random.choice(titles),
                created_questions[2].id: random.choice(departments),
                created_questions[3].id: random.choice(arrangements),
                created_questions[4].id: random.randint(1, 20),
                created_questions[6].id: random.randint(3, 7),
                created_questions[7].id: random.choice(likert_opts[2:] if passed_check else likert_opts[:3]),
                created_questions[8].id: random.randint(3, 5),
                created_questions[9].id: random.randint(50, 95),
                created_questions[10].id: random.randint(6, 10),
                created_questions[11].id: att_answer, # Attention check
                created_questions[13].id: random.sample(tools_pool, k=random.randint(2, 5)),
                created_questions[14].id: {
                    "Deep Focus Work": p1,
                    "Team Meetings & Syncs": p2,
                    "Admin & Email Management": p3,
                    "Learning & Skill Building": p4
                },
                created_questions[15].id: random.sample(["Flexible Working Hours", "Professional Development Stipend", "Home Office Equipment Allowance", "Wellness & Mental Health Days", "Performance Bonuses"], k=3),
                created_questions[16].id: {
                    "Company Strategy Updates": random.choice(["Neutral", "Satisfied", "Very Satisfied"]),
                    "Project Goals & Deadlines": random.choice(["Satisfied", "Very Satisfied"]),
                    "Peer Feedback Loops": random.choice(["Dissatisfied", "Neutral", "Satisfied"])
                },
                created_questions[18].id: random.choice(qual_comments),
                created_questions[19].id: (datetime.now() + timedelta(days=random.randint(30, 180))).strftime("%Y-%m-%d"),
            }

            flags = {}
            if not passed_check:
                flags = {"attention_check_failed": True, "failed_check_ids": [created_questions[11].id]}

            resp_obj = Response(
                id=str(uuid.uuid4()),
                survey_id=survey_id,
                participant_email=f"respondent_{i+1}@example.com",
                answers=resp_answers,
                flags=flags,
                submitted_at=datetime.utcnow() - timedelta(minutes=random.randint(10, 1440))
            )
            db.add(resp_obj)

        await db.commit()
        print("Inserted 40 synthetic responses with attention check metadata.")

        print("=== 5. Launching Statistical Analysis Job ===")
        from api.routers.analysis_worker import run_pipeline_sync
        from workers.queue import enqueue_job

        job_id = str(uuid.uuid4())
        job = AnalysisJob(
            id=job_id,
            user_id=user.id,
            survey_id=survey_id,
            status=JobStatus.pending,
            source_type="survey_db",
            project_brief=survey.project_brief,
            academic_tradition="standard",
            report_type="chapter4"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        print(f"Created AnalysisJob: {job.id}. Starting processing pipeline...")
        await enqueue_job(job.id, run_pipeline_sync, job.id)
        print(f"Analysis job {job.id} enqueued and processing! Survey URL slug: /s/{slug}")
        print(f"Survey ID: {survey_id}")
        print(f"Analysis Job ID: {job_id}")

if __name__ == "__main__":
    asyncio.run(run())
