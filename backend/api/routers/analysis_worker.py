# backend/api/routers/analysis_worker.py
"""
Top-level wrapper for the analysis pipeline so it can be called
from concurrent.futures.ProcessPoolExecutor (functions must be
importable at the module level — not closures or lambdas).

This simply re-exports _run_pipeline under a public name.
ProcessPoolExecutor serialises the function reference via pickle;
pickle requires the function to be importable by name from a module.
"""


def run_pipeline_sync(job_id: str, file_path: str = None):
    """
    Entry point for ProcessPoolExecutor worker process.
    Imports are done inside the function body so that worker processes
    don't inherit the parent's open DB connections / async loops.
    """
    # Each worker process gets its own fresh import context
    from api.routers.analysis import _run_pipeline
    _run_pipeline(job_id, file_path)
