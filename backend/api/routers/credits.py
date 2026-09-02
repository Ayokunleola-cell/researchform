# backend/api/routers/credits.py
"""Analysis credit wallet API (separate from DataNest marketplace payments)."""
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_current_user
from api.models.database import CreditTransaction, CreditTransactionType, User
from config import settings
from services.credits import (
    add_credits_async,
    credit_purchase_from_paystack,
    credit_purchase_from_stripe,
    estimate_analysis_credits,
    get_credit_packages,
    get_credit_packages_db,
    get_or_create_wallet_async,
)
from services.paystack import initialize_transaction as paystack_init, is_paystack_enabled, PaystackError
from services.stripe import initialize_transaction as stripe_init, is_stripe_enabled, StripeError
from api.routers.referral import process_referral_commission

router = APIRouter()


def _tx_out(tx: CreditTransaction) -> dict:
    return {
        "id": tx.id,
        "amount": float(tx.amount),
        "type": tx.type.value if hasattr(tx.type, "value") else tx.type,
        "description": tx.description,
        "reference_id": tx.reference_id,
        "balance_after": float(tx.balance_after),
        "created_at": str(tx.created_at),
        "extra": tx.extra or {},
    }


@router.get("/config")
async def credits_config():
    return {
        "dev_mode": settings.DEV_MODE,
        "paystack_enabled": is_paystack_enabled(),
        "stripe_enabled": is_stripe_enabled(),
        "paystack_public_key": settings.PAYSTACK_PUBLIC_KEY if is_paystack_enabled() else "",
        "stripe_public_key": settings.STRIPE_PUBLIC_KEY if is_stripe_enabled() else "",
        "currency": settings.CURRENCY,
        "currency_symbol": settings.CURRENCY_SYMBOL,
        "currency_locale": settings.CURRENCY_LOCALE,
        "minimum_report_credits": settings.CREDIT_MIN_REPORT_CHARGE,
        "signup_bonus": settings.SIGNUP_BONUS_CREDITS,
    }



@router.get("/wallet")
async def get_wallet(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    wallet = await get_or_create_wallet_async(db, user.id)
    return {
        "balance": float(wallet.balance),
        "updated_at": str(wallet.updated_at) if wallet.updated_at else None,
        "currency_label": "analysis credits",
    }


@router.get("/transactions")
async def list_transactions(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    limit = min(max(limit, 1), 100)
    result = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(limit)
    )
    return [_tx_out(tx) for tx in result.scalars().all()]


@router.get("/packages")
async def list_packages(db: AsyncSession = Depends(get_db)):
    return {"packages": await get_credit_packages_db(db)}


class EstimateCreditsRequest(BaseModel):
    study_types: list[str] = Field(default_factory=lambda: ["quantitative"])
    auto_select_techniques: bool = True
    technique_count: int = 0
    qualitative_file_count: int = 0
    has_chapters_doc: bool = False
    report_type: str = "chapter4"


@router.post("/estimate")
async def estimate_credits(
    data: EstimateCreditsRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wallet = await get_or_create_wallet_async(db, user.id)
    estimate = estimate_analysis_credits(
        study_types=data.study_types,
        auto_select_techniques=data.auto_select_techniques,
        technique_count=data.technique_count,
        qualitative_file_count=data.qualitative_file_count,
        has_chapters_doc=data.has_chapters_doc,
        report_type=data.report_type,
    )
    est = float(estimate["credits_required"])
    return {
        **estimate,
        "wallet_balance": float(wallet.balance),
        "likely_sufficient": float(wallet.balance) >= est,
    }


class InitCheckoutRequest(BaseModel):
    package_id: str
    provider: str = "paystack"


@router.post("/checkout/initialize")
async def init_checkout(
    data: InitCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    packages = {p["id"]: p for p in await get_credit_packages_db(db)}
    pkg = packages.get(data.package_id)
    if not pkg:
        raise HTTPException(400, "Unknown credit package")

    if data.provider == "stripe" and not is_stripe_enabled() and not settings.DEV_MODE:
         raise HTTPException(400, detail="Stripe is not configured.")
    elif data.provider == "paystack" and not is_paystack_enabled() and not settings.DEV_MODE:
        raise HTTPException(
            400,
            detail="Use direct purchase in development mode, or configure PAYSTACK_SECRET_KEY.",
        )

    reference = f"rf_cr_{uuid.uuid4().hex[:16]}"
    callback_url = f"{settings.FRONTEND_URL.rstrip('/')}/settings/credits"

    try:
        kwargs = dict(
            email=user.email,
            amount_kobo=int(pkg["price_naira"]) * 100,
            reference=reference,
            callback_url=callback_url,
            metadata={
                "user_id": user.id,
                "package_id": data.package_id,
                "credits": pkg["credits"],
                "product": "researchform_analysis_credits",
            },
        )
        if data.provider == "stripe":
            result = await stripe_init(**kwargs)
        else:
            result = await paystack_init(**kwargs)
    except PaystackError as e:
        raise HTTPException(e.status_code, e.message) from e
    except StripeError as e:
         raise HTTPException(e.status_code, e.message) from e

    return {
        "authorization_url": result["authorization_url"],
        "access_code": result.get("access_code"),
        "reference": result.get("reference") or reference,
        "amount_naira": pkg["price_naira"],
        "credits": pkg["credits"],
        "provider": data.provider,
    }


class PurchaseCreditsRequest(BaseModel):
    package_id: str
    payment_reference: Optional[str] = None


@router.post("/purchase")
async def purchase_credits(
    data: PurchaseCreditsRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    packages = {p["id"]: p for p in await get_credit_packages_db(db)}
    pkg = packages.get(data.package_id)
    if not pkg:
        raise HTTPException(400, "Unknown credit package")

    credits = Decimal(str(pkg["credits"]))

    if settings.DEV_MODE:
        wallet = await add_credits_async(
            db,
            user.id,
            credits,
            CreditTransactionType.purchase,
            f"Purchased {pkg['label']} pack ({pkg['credits']} credits)",
            reference_id=data.payment_reference or f"dev_{uuid.uuid4().hex[:12]}",
            extra={"package_id": pkg["id"], "price_naira": pkg["price_naira"], "dev_mode": True},
        )
        await db.commit()
        # Fire referral commission (idempotent)
        await process_referral_commission(
            db, user, pkg["id"], credits,
            price_naira=pkg["price_naira"],
            payment_reference=data.payment_reference or f"dev_{uuid.uuid4().hex[:12]}",
        )
        await db.commit()
        return {
            "success": True,
            "balance": float(wallet.balance),
            "credits_added": float(credits),
            "message": "Credits added (development mode)",
        }

    if not data.payment_reference:
        raise HTTPException(402, "Payment reference required")

    try:
        result = await credit_purchase_from_paystack(
            db, user.id, data.package_id, data.payment_reference
        )
        await db.commit()
        # Fire referral commission (idempotent)
        packages = {p["id"]: p for p in get_credit_packages()}
        pkg = packages.get(data.package_id, {})
        await process_referral_commission(
            db, user, data.package_id,
            Decimal(str(pkg.get("credits", 0))),
            price_naira=float(pkg.get("price_naira", 0)),
            payment_reference=data.payment_reference,
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/checkout/verify/{reference}")
async def verify_checkout(
    reference: str,
    package_id: str,
    provider: str = "paystack",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        if provider == "stripe":
            result = await credit_purchase_from_stripe(db, user.id, package_id, reference)
        else:
            result = await credit_purchase_from_paystack(db, user.id, package_id, reference)
        await db.commit()
        # Fire referral commission (idempotent)
        packages = {p["id"]: p for p in get_credit_packages()}
        pkg = packages.get(package_id, {})
        await process_referral_commission(
            db, user, package_id,
            Decimal(str(pkg.get("credits", 0))),
            price_naira=float(pkg.get("price_naira", 0)),
            payment_reference=reference,
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
