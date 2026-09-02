# backend/finish_pending.py
import asyncio
from sqlalchemy import select
from api.deps import AsyncSessionLocal
from api.models.database import AnalysisJob, JobStatus
from api.routers.analysis import _continue_pipeline, _run_pipeline

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AnalysisJob).where(AnalysisJob.id.in_(["bdf98164-57f7-4232-b47b-bba4dc707eaf", "3065e7b0-afc7-4e36-9d75-5d8242122997"])))
        jobs = res.scalars().all()

    for j in jobs:
        print(f"Executing pipeline for Job {j.id}...")
        try:
            _run_pipeline(j.id)
            _continue_pipeline(j.id)
        except Exception as e:
            print(f"Error on Job {j.id}: {e}")

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AnalysisJob).where(AnalysisJob.id.in_(["bdf98164-57f7-4232-b47b-bba4dc707eaf", "3065e7b0-afc7-4e36-9d75-5d8242122997"])))
        jobs = res.scalars().all()
        for j in jobs:
            print(f"Job {j.id} -> status: {j.status}, error: {j.error_message}")

if __name__ == "__main__":
    asyncio.run(main())
