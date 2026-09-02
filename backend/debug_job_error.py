# backend/debug_job_error.py
import asyncio
from api.deps import AsyncSessionLocal
from api.models.database import AnalysisJob
from api.routers.analysis import _run_pipeline

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.get(AnalysisJob, "aaea27af-567e-4879-aa7f-4812b0b4b57a")
        print("Job error_message:", res.error_message if res else "Not found")

if __name__ == "__main__":
    asyncio.run(main())
