# backend/workers/queue.py
"""
In-memory job queue with semaphore-based concurrency control.
- New jobs wait in a queue instead of crashing when the pool is full
- Per-job timeout (default 15 min) prevents stuck jobs from blocking workers
- On failure, writes job status back to DB so the UI can show the error
- Upgradeable to Celery + Redis for multi-server production deployments
"""
import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import Callable, Any

logger = logging.getLogger(__name__)

MAX_CONCURRENT  = int(os.getenv("MAX_ANALYSIS_WORKERS", str(max(1, (os.cpu_count() or 2) - 1))))
MAX_QUEUE_SIZE  = int(os.getenv("MAX_ANALYSIS_QUEUE",   "50"))
JOB_TIMEOUT_SEC = int(os.getenv("JOB_TIMEOUT_SECONDS",  str(25 * 60)))  # 25 minutes
MAX_JOB_RETRIES = int(os.getenv("MAX_JOB_RETRIES",      "1"))           # 1 automatic retry

_semaphore: asyncio.Semaphore | None = None
_queue_depth: int = 0


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    return _semaphore


def _mark_job_failed(job_id: str, reason: str) -> None:
    """Write failed status back to DB synchronously — called from async error handler."""
    try:
        from api.deps import SyncSessionLocal
        from api.models.database import AnalysisJob
        db = SyncSessionLocal()
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job and job.status not in ("complete", "failed"):
                job.status = "failed"
                job.error_message = reason[:2000]          # cap length for DB column
                job.completed_at  = datetime.utcnow()
                db.commit()
                logger.info("[Queue] Wrote failed status to DB for job %s", job_id)
        finally:
            db.close()
    except Exception as db_err:
        logger.error("[Queue] Could not write failed status to DB for job %s: %s", job_id, db_err)


async def enqueue_job(job_id: str, fn: Callable, *args: Any) -> None:
    """
    Enqueue an analysis job.  Returns immediately — job runs in background.
    fn must be a top-level importable synchronous function (picklable for ProcessPool).
    """
    global _queue_depth

    if _queue_depth >= MAX_QUEUE_SIZE:
        reason = (
            f"Analysis queue is full ({MAX_QUEUE_SIZE} jobs pending). "
            "Please try again in a few minutes."
        )
        _mark_job_failed(job_id, reason)
        raise RuntimeError(reason)

    _queue_depth += 1
    logger.info("[Queue] Job %s queued. Depth=%d/%d", job_id, _queue_depth, MAX_QUEUE_SIZE)

    async def _run():
        global _queue_depth
        sem = _get_semaphore()
        async with sem:
            _queue_depth -= 1
            active = MAX_CONCURRENT - sem._value
            logger.info("[Queue] Job %s starting. Active=%d/%d", job_id, active, MAX_CONCURRENT)
            started = datetime.utcnow()

            for attempt in range(1 + MAX_JOB_RETRIES):
                try:
                    from workers.pool import run_in_process
                    await asyncio.wait_for(
                        run_in_process(fn, *args),
                        timeout=JOB_TIMEOUT_SEC,
                    )
                    elapsed = (datetime.utcnow() - started).total_seconds()
                    logger.info("[Queue] Job %s completed in %.1fs", job_id, elapsed)
                    return  # success — exit retry loop

                except asyncio.TimeoutError:
                    elapsed = (datetime.utcnow() - started).total_seconds()
                    reason = (
                        f"Analysis timed out after {elapsed:.0f}s (limit {JOB_TIMEOUT_SEC}s). "
                        "This usually happens with very large datasets or too many tests selected. "
                        "Try reducing to 10–15 tests, or uncheck 'Auto-generate all charts', then re-run."
                    )
                    logger.error("[Queue] Job %s TIMED OUT after %.1fs", job_id, elapsed)
                    _mark_job_failed(job_id, reason)
                    return  # timeout is unrecoverable — don't retry

                except Exception as e:
                    elapsed = (datetime.utcnow() - started).total_seconds()
                    if attempt < MAX_JOB_RETRIES:
                        logger.warning(
                            "[Queue] Job %s failed on attempt %d/%d after %.1fs: %s — retrying...",
                            job_id, attempt + 1, 1 + MAX_JOB_RETRIES, elapsed, e
                        )
                        await asyncio.sleep(3)  # brief pause before retry
                    else:
                        reason = f"Worker process error after {elapsed:.0f}s: {e}"
                        logger.error("[Queue] Job %s FAILED after %.1fs (all retries exhausted): %s", job_id, elapsed, e)
                        _mark_job_failed(job_id, reason)

    # Fire-and-forget — API returns immediately, job runs in background
    asyncio.create_task(_run())


async def cleanup_stale_jobs(max_age_minutes: int = 25) -> int:
    """
    Mark jobs that have been stuck in a non-terminal state for too long.
    Called by the cron task in main.py.  Returns count of jobs cleaned.
    """
    try:
        from api.deps import AsyncSessionLocal
        from api.models.database import AnalysisJob
        from sqlalchemy import select, or_
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AnalysisJob).where(
                    AnalysisJob.status.notin_(["complete", "failed", "pending"]),
                    # Use analysis_started_at when set, fall back to created_at
                    or_(
                        AnalysisJob.analysis_started_at < cutoff,
                        AnalysisJob.created_at < cutoff,
                    ),
                )
            )
            stale = result.scalars().all()
            for job in stale:
                old_status = job.status
                job.status        = "failed"
                clean_stage = str(old_status).split('.')[-1].replace('_', ' ')
                job.error_message = (
                    f"The analysis stalled during the {clean_stage} phase "
                    "and was safely cancelled. Please try again."
                )
                job.completed_at  = datetime.utcnow()
                logger.warning("[Queue] Cleaned stale job %s (was '%s')", job.id, old_status)
            await db.commit()
            return len(stale)
    except Exception as e:
        logger.error("[Queue] Stale job cleanup error: %s", e)
        return 0


def queue_stats() -> dict:
    sem    = _get_semaphore()
    active = MAX_CONCURRENT - sem._value
    return {
        "max_workers":   MAX_CONCURRENT,
        "active_workers": active,
        "queued_jobs":   _queue_depth,
        "max_queue":     MAX_QUEUE_SIZE,
        "timeout_sec":   JOB_TIMEOUT_SEC,
        "available_slots": max(0, MAX_CONCURRENT - active),
    }
