import asyncio
import numpy as np
import uuid
import json
from datetime import datetime, timezone
import os
import sys

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend')))

from api.models.database import Survey, Question, Response, User, QuestionType, MeasurementLevel

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///./researchform_dev.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def generate_data():
    async with async_session() as session:
        # Get demo user
        result = await session.execute(select(User).filter_by(email="demo@researchform.app"))
        user = result.scalars().first()
        if not user:
            print("Demo user not found.")
            return

        # Create Survey
        survey_id = str(uuid.uuid4())
        survey = Survey(
            id=survey_id,
            user_id=user.id,
            title="Comprehensive Pre-test Analysis Survey",
            description="Generated survey for testing Reliability, Path Analysis, Multicollinearity, and Normality.",
            status="active"
        )
        session.add(survey)

        # Create Questions
        questions = []
        pos = 1
        def add_q(var_name, text, q_type=QuestionType.likert):
            nonlocal pos
            q_id = str(uuid.uuid4())
            q = Question(
                id=q_id,
                survey_id=survey_id,
                position=pos,
                type=q_type,
                text=text,
                variable_name=var_name,
                measurement_level=MeasurementLevel.ordinal if q_type == QuestionType.likert else MeasurementLevel.ratio,
                scale_min=1,
                scale_max=5
            )
            session.add(q)
            questions.append(q)
            pos += 1

        # Construct A (Predictor)
        add_q("A1", "I often use the system for my tasks.")
        add_q("A2", "The system is a regular part of my workflow.")
        add_q("A3", "I depend on the system daily.")

        # Construct B (Mediator)
        add_q("B1", "I find the system easy to use.")
        add_q("B2", "The system is user-friendly.")
        add_q("B3", "Learning to use the system was easy.")

        # Construct C (Outcome) - Highly correlated with B
        add_q("C1", "I am satisfied with the system.")
        add_q("C2", "The system meets my expectations.")
        add_q("C3", "I would recommend the system to others.")

        # Demographic (Numeric)
        add_q("Age", "What is your age?", QuestionType.number)
        add_q("Income", "What is your annual income?", QuestionType.number)

        await session.commit()
        
        # Generate Responses (N=150)
        np.random.seed(42)
        n_resp = 150
        
        # Base factor for A
        factor_A = np.random.normal(3, 0.8, n_resp)
        
        # Base factor for B (depends on A)
        factor_B = 0.5 * factor_A + np.random.normal(1.5, 0.5, n_resp)
        
        # Base factor for C (depends heavily on B - Multicollinearity!)
        factor_C = 0.9 * factor_B + np.random.normal(0, 0.2, n_resp)

        # Generate items
        def gen_item(factor, error_std):
            vals = factor + np.random.normal(0, error_std, n_resp)
            vals = np.clip(np.round(vals), 1, 5)
            return vals
            
        data_A1 = gen_item(factor_A, 0.3)
        data_A2 = gen_item(factor_A, 0.3)
        data_A3 = gen_item(factor_A, 0.4)
        
        data_B1 = gen_item(factor_B, 0.3)
        data_B2 = gen_item(factor_B, 0.4)
        data_B3 = gen_item(factor_B, 0.3)
        
        data_C1 = gen_item(factor_C, 0.2)
        data_C2 = gen_item(factor_C, 0.2)
        data_C3 = gen_item(factor_C, 0.3)
        
        # Age (skewed, non-normal)
        data_age = np.random.exponential(scale=10, size=n_resp) + 18
        data_age = np.round(data_age)
        
        # Income (with outliers)
        data_income = np.random.normal(50000, 10000, n_resp)
        # Add a few massive outliers
        data_income[5] = 250000
        data_income[22] = 300000
        data_income = np.round(data_income)

        for i in range(n_resp):
            answers = {
                questions[0].id: int(data_A1[i]),
                questions[1].id: int(data_A2[i]),
                questions[2].id: int(data_A3[i]),
                questions[3].id: int(data_B1[i]),
                questions[4].id: int(data_B2[i]),
                questions[5].id: int(data_B3[i]),
                questions[6].id: int(data_C1[i]),
                questions[7].id: int(data_C2[i]),
                questions[8].id: int(data_C3[i]),
                questions[9].id: int(data_age[i]),
                questions[10].id: int(data_income[i]),
            }
            resp = Response(
                id=str(uuid.uuid4()),
                survey_id=survey_id,
                answers=answers,
                submitted_at=datetime.now(timezone.utc)
            )
            session.add(resp)
            
        await session.commit()
        print(f"Generated survey successfully! Survey ID: {survey_id}")

if __name__ == "__main__":
    asyncio.run(generate_data())
