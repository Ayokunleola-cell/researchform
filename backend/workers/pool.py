# backend/workers/pool.py
"""
ProcessPoolExecutor manager.
Analysis jobs run in isolated OS processes so the FastAPI event loop
stays responsive for all other users while heavy pandas/scipy work runs.
"""
from concurrent.futures import ProcessPoolExecutor
import asyncio
import os

MAX_WORKERS = int(os.getenv("MAX_ANALYSIS_WORKERS", str(max(1, (os.cpu_count() or 2) - 1))))

_pool: ProcessPoolExecutor | None = None


def get_pool() -> ProcessPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(max_workers=MAX_WORKERS)
    return _pool


async def run_in_process(fn, *args):
    """
    Run a synchronous function in the process pool.
    Returns a coroutine — await it from async FastAPI code.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(get_pool(), fn, *args)


def shutdown_pool():
    global _pool
    if _pool:
        _pool.shutdown(wait=False)
        _pool = None
