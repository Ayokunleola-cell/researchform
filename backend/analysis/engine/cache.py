# backend/analysis/engine/cache.py
"""
Result caching layer for the Statistical Engine.
Caches results keyed by: dataset_hash + test_function + variables + params.
Invalidated automatically when the user uploads a new dataset.
"""
from __future__ import annotations
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

CACHE_DIR = Path("storage/engine_cache")
CACHE_TTL_HOURS = 24  # Results expire after 24 hours


def _make_key(dataset_hash: str, test_function: str, variables: list, params: dict) -> str:
    """Create a deterministic cache key from analysis parameters."""
    payload = json.dumps(
        {
            "dataset": dataset_hash,
            "test": test_function,
            "vars": sorted(variables),
            "params": params,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.md5(payload.encode()).hexdigest()


def get_cached(dataset_hash: str, test_function: str, variables: list, params: dict = None) -> dict | None:
    """
    Retrieve a cached result. Returns None if not found or expired.
    """
    key = _make_key(dataset_hash, test_function, variables, params or {})
    path = CACHE_DIR / f"{key}.json"

    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
        if datetime.utcnow() - cached_at > timedelta(hours=CACHE_TTL_HOURS):
            path.unlink(missing_ok=True)
            logger.debug(f"[Cache] EXPIRED: {test_function} / {variables}")
            return None
        logger.debug(f"[Cache] HIT: {test_function} / {variables}")
        return data.get("result")
    except Exception as e:
        logger.warning(f"[Cache] Read error for {key}: {e}")
        return None


def set_cached(
    result: dict,
    dataset_hash: str,
    test_function: str,
    variables: list,
    params: dict = None,
) -> None:
    """Store a result in the cache."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        key = _make_key(dataset_hash, test_function, variables, params or {})
        path = CACHE_DIR / f"{key}.json"
        payload = {
            "_cached_at": datetime.utcnow().isoformat(),
            "_dataset_hash": dataset_hash,
            "_test_function": test_function,
            "_variables": variables,
            "result": result,
        }
        path.write_text(json.dumps(payload, default=str, ensure_ascii=False), encoding="utf-8")
        logger.debug(f"[Cache] STORED: {test_function} / {variables}")
    except Exception as e:
        logger.warning(f"[Cache] Write error: {e}")


def invalidate_dataset(dataset_hash: str) -> int:
    """
    Remove all cached results for a specific dataset.
    Called when the user uploads a new file so stale results don't persist.
    Returns the count of deleted entries.
    """
    count = 0
    if not CACHE_DIR.exists():
        return 0
    for f in CACHE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("_dataset_hash") == dataset_hash:
                f.unlink(missing_ok=True)
                count += 1
        except Exception:
            pass
    logger.info(f"[Cache] Invalidated {count} entries for dataset {dataset_hash[:8]}...")
    return count


def cache_stats() -> dict:
    """Return cache health statistics."""
    if not CACHE_DIR.exists():
        return {"total": 0, "expired": 0, "valid": 0, "size_kb": 0}
    files = list(CACHE_DIR.glob("*.json"))
    now = datetime.utcnow()
    expired = 0
    valid = 0
    total_size = 0
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
            total_size += f.stat().st_size
            if now - cached_at > timedelta(hours=CACHE_TTL_HOURS):
                expired += 1
            else:
                valid += 1
        except Exception:
            expired += 1
    return {
        "total": len(files),
        "expired": expired,
        "valid": valid,
        "size_kb": round(total_size / 1024, 1),
    }


def clear_all() -> int:
    """Nuclear option: wipe the entire cache. Admin use only."""
    if not CACHE_DIR.exists():
        return 0
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        try:
            f.unlink()
            count += 1
        except Exception:
            pass
    logger.warning(f"[Cache] Full clear: removed {count} entries.")
    return count
