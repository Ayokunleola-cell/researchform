# backend/rerun_failed_job.py
import asyncio
from sqlalchemy import select
from api.deps import AsyncSessionLocal
from api.models.database import AnalysisJob, JobStatus
from api.routers.analysis import _continue_pipeline, _run_pipeline

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AnalysisJob).where(AnalysisJob.status == JobStatus.failed))
        failed_jobs = res.scalars().all()
        print(f"Found {len(failed_jobs)} failed jobs. Resetting to pending...")
        for j in failed_jobs:
            j.status = JobStatus.pending
            j.preprocessing_mode = "auto"
            j.error_message = None
            j.results = None
            j.n_rows = None
            j.n_columns = None
        await db.commit()

        # Re-fetch pending jobs
        res = await db.execute(select(AnalysisJob).where(AnalysisJob.status == JobStatus.pending))
        pending_jobs = res.scalars().all()

    for j in pending_jobs:
        print(f"Running pipeline for Job {j.id}...")
        try:
            _run_pipeline(j.id)
            _continue_pipeline(j.id)
            print(f"Job {j.id} pipeline execution finished.")
        except Exception as e:
            print(f"Job {j.id} exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
