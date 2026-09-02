# backend/continue_health_job.py
import asyncio
from api.deps import AsyncSessionLocal
from api.models.database import AnalysisJob
from api.routers.analysis import _continue_pipeline

async def main():
    job_id = "b9b7e7bd-ac50-4375-a674-193d740bb9ab"
    async with AsyncSessionLocal() as db:
        j = await db.get(AnalysisJob, job_id)
        if j:
            j.missing_strategy = "flag_only"
            db.add(j)
            await db.commit()
            print(f"Continuing pipeline for job {job_id}...")
            await _continue_pipeline(job_id)
            print(f"Job {job_id} pipeline completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
