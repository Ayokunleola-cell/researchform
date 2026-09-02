# backend/api/deps.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, text, event
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from config import settings
from api.models.database import User
import os

# ── Async engine (FastAPI event loop) ────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,          # detect stale connections before use
    pool_recycle=300,            # recycle connections every 5 min
    connect_args={"check_same_thread": False, "timeout": 30}
    if settings.DATABASE_URL.startswith("sqlite") else {},
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ── Sync engine (worker processes — cannot use async) ────────────────────
_sync_db_url = settings.DATABASE_URL.replace("sqlite+aiosqlite", "sqlite")
sync_engine = create_engine(
    _sync_db_url,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"check_same_thread": False, "timeout": 30}
    if _sync_db_url.startswith("sqlite") else {},
)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)

# ── Enable WAL mode for SQLite (allows concurrent readers + 1 writer) ────
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(sync_engine, "connect")
    def _set_wal_mode(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

    # Apply immediately so the async pool also picks it up on first connect
    with sync_engine.connect() as _conn:
        _conn.execute(text("PRAGMA journal_mode=WAL"))
        _conn.execute(text("PRAGMA synchronous=NORMAL"))
        _conn.execute(text("PRAGMA busy_timeout=10000"))
        _conn.commit()

security = HTTPBearer(auto_error=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    from api.models.database import UserRole
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user

async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except Exception:
        return None

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
