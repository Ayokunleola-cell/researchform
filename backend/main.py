# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
import os
import asyncio
from contextlib import asynccontextmanager
from api.routers import auth, surveys, responses, analysis, export, users, credits, admin
from api.routers import general_chat, market_public, market_purchases, market_seller, wallet
from api.routers import integrations_powerbi, integrations_google
from api.routers import referral
from config import settings
from api.deps import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self' https:;"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    from api.deps import AsyncSessionLocal
    from api.wallet import release_pending_earnings

    async def _cron_release_earnings():
        while True:
            try:
                async with AsyncSessionLocal() as db:
                    await release_pending_earnings(db)
            except Exception as e:
                print(f"Error in release_pending_earnings job: {e}")
            await asyncio.sleep(3600)  # Run every 1 hour

    async def _cron_stale_jobs():
        """Every 5 min: cancel jobs stuck in non-terminal states > 20 min."""
        while True:
            try:
                from workers.queue import cleanup_stale_jobs
                cleaned = await cleanup_stale_jobs(max_age_minutes=20)
                if cleaned:
                    print(f"[Cron] Cleaned {cleaned} stale analysis job(s)")
            except Exception as e:
                print(f"[Cron] Stale job cleanup error: {e}")
            await asyncio.sleep(300)  # every 5 minutes


    task1 = asyncio.create_task(_cron_release_earnings())
    task2 = asyncio.create_task(_cron_stale_jobs())
    yield
    for t in (task1, task2):
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass

app = FastAPI(title="ResearchForm API", version="1.0.0", lifespan=lifespan)

# ── Startup security check ────────────────────────────────────────────
if "CHANGE_ME" in settings.SECRET_KEY:
    import warnings
    warnings.warn(
        "\n" + "="*60 +
        "\n[SECURITY WARNING] SECRET_KEY is still set to the default insecure value!" +
        "\nGenerate a secure key with: openssl rand -hex 32" +
        "\nSet it in backend/.env as: SECRET_KEY=<your_key>" +
        "\n" + "="*60,
        stacklevel=1
    )
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)  # compress responses > 1KB
app.add_middleware(CORSMiddleware, allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"])
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

from api.routers import auth_social
from api.routers import power as power_router
from api.routers import missing as missing_router
from api.routers import transforms as transforms_router
app.include_router(auth.router,      prefix="/auth",     tags=["Auth"])
app.include_router(auth_social.router, prefix="/auth/social", tags=["Auth Social"])
app.include_router(users.router,     prefix="/users",    tags=["Users"])
app.include_router(surveys.router,   prefix="/surveys",  tags=["Surveys"])
app.include_router(responses.router, prefix="/public",   tags=["Public"])
app.include_router(analysis.router,  prefix="/analysis", tags=["Analysis"])
from api.routers import chat
app.include_router(chat.router,      prefix="/analysis", tags=["Chat"])
app.include_router(export.router,    prefix="/export",   tags=["Export"])
app.include_router(market_public.router, prefix="/datanest", tags=["DataNest Marketplace"])
app.include_router(market_purchases.router, prefix="/datanest", tags=["DataNest Marketplace"])
app.include_router(market_seller.router, prefix="/datanest", tags=["DataNest Marketplace Seller"])
app.include_router(wallet.router, prefix="/wallet", tags=["Wallet & Payouts"])
app.include_router(credits.router,   prefix="/credits",  tags=["Analysis Credits"])
app.include_router(admin.router,     prefix="/admin",    tags=["Admin"])
app.include_router(general_chat.router,  prefix="/chat",    tags=["AI Chat"])
app.include_router(integrations_powerbi.router, prefix="/integrations/powerbi", tags=["Integrations - Power BI"])
app.include_router(integrations_google.router, prefix="/integrations/google", tags=["Integrations - Google"])
app.include_router(referral.router, prefix="/referral", tags=["Referral"])
app.include_router(power_router.router)
app.include_router(missing_router.router)
app.include_router(transforms_router.router)

for d in ["storage/charts","storage/reports","storage/dataframes","storage/avatars","storage/uploads","storage/uploads/responses", "api/local_storage"]:
    os.makedirs(d, exist_ok=True)
app.mount("/storage", StaticFiles(directory="storage"), name="storage")
app.mount("/api/local-storage", StaticFiles(directory="api/local_storage"), name="local_storage")

@app.get("/health")
def health(): return {"status": "ok", "version": "1.0.0"}

@app.get("/analysis/queue-stats")
def queue_stats_endpoint():
    """Live queue depth — used by frontend to show estimated wait time."""
    try:
        from workers.queue import queue_stats
        return queue_stats()
    except Exception as e:
        return {"error": str(e), "max_workers": 1, "active_workers": 0, "queued_jobs": 0}

