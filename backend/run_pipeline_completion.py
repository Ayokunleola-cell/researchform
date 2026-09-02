# backend/run_pipeline_completion.py
import asyncio
from datetime import datetime
from api.deps import AsyncSessionLocal
from api.models.database import AnalysisJob, JobStatus
from api.routers.analysis import _continue_pipeline

async def main():
    job_id = "b8ae9761-c6d3-4c1a-a6a0-c3583dd12874"
    async with AsyncSessionLocal() as db:
        j = await db.get(AnalysisJob, job_id)
        if j:
            j.status = JobStatus.parsing
            j.analysis_started_at = datetime.utcnow()
            await db.commit()
            print(f"Set job {job_id} to parsing. Executing _continue_pipeline...")

    # Call synchronous pipeline executor
    _continue_pipeline(job_id)
    
    async with AsyncSessionLocal() as db:
        j = await db.get(AnalysisJob, job_id)
        print(f"Final Job Status: {j.status}")
        print(f"Rows: {j.n_rows}, Columns: {j.n_columns}")
        print(f"Charts Generated: {len(j.chart_paths or [])}")
        if j.error_message:
            print(f"Error: {j.error_message}")

if __name__ == "__main__":
    asyncio.run(main())
