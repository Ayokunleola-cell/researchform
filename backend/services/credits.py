"""
Analysis credit wallet — separate from DataNest marketplace payments.
Credits are charged when downloading a completed report, based on LLM usage.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from api.models.database import CreditTransaction, CreditWallet, CreditTransactionType, AnalysisJob
from config import settings


def _d(value: float | int | str | Decimal) -> Decimal:
    return Decimal(str(value))


def _round_credits(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def credits_from_llm_usage(usage: Optional[dict], markup_multiplier: Optional[float] = None) -> Decimal:
    """
    Convert recorded LLM tokens to analysis credits (includes platform markup).
    """
    if not usage:
        return _round_credits(_d(settings.CREDIT_MIN_REPORT_CHARGE))

    inp = int(usage.get("total_input_tokens") or 0)
    out = int(usage.get("total_output_tokens") or 0)

    if inp == 0 and out == 0 and usage.get("calls"):
        for call in usage.get("calls") or []:
            inp += int(call.get("input_tokens") or 0)
            out += int(call.get("output_tokens") or 0)

    if inp == 0 and out == 0:
        # Fallback: estimate from max_tokens requested in each call
        for call in usage.get("calls") or []:
            out += int(call.get("max_tokens_requested") or 0) // 2
            inp += len(str(call.get("model", ""))) * 50

    input_rate = _d(settings.CREDIT_PER_1K_INPUT_TOKENS)
    output_rate = _d(settings.CREDIT_PER_1K_OUTPUT_TOKENS)
    markup = _d(str(markup_multiplier)) if markup_multiplier is not None else _d(settings.CREDIT_MARKUP_MULTIPLIER)

    base = (input_rate * _d(inp) / 1000) + (output_rate * _d(out) / 1000)
    total = _round_credits(base * markup)
    minimum = _round_credits(_d(settings.CREDIT_MIN_REPORT_CHARGE))
    return max(total, minimum)


def billing_breakdown(usage: Optional[dict], markup_multiplier: Optional[float] = None) -> dict[str, Any]:
    credits = credits_from_llm_usage(usage, markup_multiplier)
    inp = int((usage or {}).get("total_input_tokens") or 0)
    out = int((usage or {}).get("total_output_tokens") or 0)
    markup = float(markup_multiplier) if markup_multiplier is not None else settings.CREDIT_MARKUP_MULTIPLIER
    return {
        "credits_required": float(credits),
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
        "call_count": int((usage or {}).get("call_count") or len((usage or {}).get("calls") or [])),
        "markup_multiplier": markup,
        "rate_per_1k_input": settings.CREDIT_PER_1K_INPUT_TOKENS,
        "rate_per_1k_output": settings.CREDIT_PER_1K_OUTPUT_TOKENS,
        "minimum_credits": settings.CREDIT_MIN_REPORT_CHARGE,
    }


def get_credit_packages() -> list[dict]:
    """Sync fallback — returns config defaults. Use get_credit_packages_db() when you have a DB session."""
    return list(settings.CREDIT_PACKAGES)


async def get_credit_packages_db(db) -> list[dict]:
    """Async version — reads from SystemSettings first, falls back to config defaults."""
    import json
    from sqlalchemy import select as _select
    from api.models.database import SystemSettings
    try:
        result = await db.execute(
            _select(SystemSettings).where(SystemSettings.key == "credit_packages")
        )
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            packages = json.loads(setting.value)
            if isinstance(packages, list) and packages:
                return packages
    except Exception:
        pass
    return list(settings.CREDIT_PACKAGES)


async def get_or_create_wallet_async(db: AsyncSession, user_id: str) -> CreditWallet:
    result = await db.execute(select(CreditWallet).where(CreditWallet.user_id == user_id))
    wallet = result.scalar_one_or_none()
    if wallet:
        return wallet
    wallet = CreditWallet(user_id=user_id, balance=_d(0))
    db.add(wallet)
    await db.flush()
    return wallet


def get_or_create_wallet_sync(db: Session, user_id: str) -> CreditWallet:
    wallet = db.get(CreditWallet, user_id)
    if wallet:
        return wallet
    wallet = CreditWallet(user_id=user_id, balance=_d(0))
    db.add(wallet)
    db.flush()
    return wallet


async def add_credits_async(
    db: AsyncSession,
    user_id: str,
    amount: Decimal,
    tx_type: CreditTransactionType,
    description: str,
    reference_id: Optional[str] = None,
    extra: Optional[dict] = None,
) -> CreditWallet:
    if amount <= 0:
        raise ValueError("amount must be positive")
    wallet = await get_or_create_wallet_async(db, user_id)
    wallet.balance = _round_credits(wallet.balance + amount)
    tx = CreditTransaction(
        user_id=user_id,
        amount=amount,
        type=tx_type,
        description=description,
        reference_id=reference_id,
        balance_after=wallet.balance,
        extra=extra or {},
    )
    db.add(tx)
    await db.flush()
    return wallet


def deduct_credits_sync(
    db: Session,
    user_id: str,
    amount: Decimal,
    job_id: str,
    description: str,
) -> CreditWallet:
    amount = _round_credits(amount)
    if amount <= 0:
        raise ValueError("deduction must be positive")

    wallet = get_or_create_wallet_sync(db, user_id)
    if wallet.balance < amount:
        raise InsufficientCreditsError(float(wallet.balance), float(amount))

    wallet.balance = _round_credits(wallet.balance - amount)
    tx = CreditTransaction(
        user_id=user_id,
        amount=-amount,
        type=CreditTransactionType.report_download,
        description=description,
        reference_id=job_id,
        balance_after=wallet.balance,
        extra={"job_id": job_id},
    )
    db.add(tx)
    db.flush()
    return wallet


class InsufficientCreditsError(Exception):
    def __init__(self, balance: float, required: float):
        self.balance = balance
        self.required = required
        super().__init__(f"Insufficient credits: have {balance}, need {required}")


def persist_job_usage_and_estimate(job: AnalysisJob, usage_dict: dict) -> None:
    job.llm_usage = usage_dict
    job.credits_estimated = credits_from_llm_usage(usage_dict)


async def find_purchase_by_reference(db: AsyncSession, reference: str) -> Optional[CreditTransaction]:
    result = await db.execute(
        select(CreditTransaction).where(
            CreditTransaction.reference_id == reference,
            CreditTransaction.type == CreditTransactionType.purchase,
        )
    )
    return result.scalar_one_or_none()


def estimate_analysis_credits(
    *,
    study_types: list[str],
    auto_select_techniques: bool = True,
    technique_count: int = 0,
    qualitative_file_count: int = 0,
    has_chapters_doc: bool = False,
    report_type: str = "chapter4",
) -> dict[str, Any]:
    """
    Heuristic pre-run estimate (actual charge uses measured tokens on report download).
    """
    inp = 12_000
    out = 18_000

    types = study_types or ["quantitative"]
    if any(t in types for t in ("qualitative", "mixed")):
        inp += 18_000
        out += 12_000
        inp += qualitative_file_count * 4_000
    if "case_study" in types:
        inp += 4_000
        out += 6_000
    if not auto_select_techniques:
        inp += 2_000
        out += max(technique_count, 1) * 1_200
    else:
        inp += 6_000
        out += 14_000
    if has_chapters_doc:
        inp += 8_000
        out += 4_000
    if report_type != "chapter4":
        out += 3_000

    usage = {
        "total_input_tokens": inp,
        "total_output_tokens": out,
        "call_count": 6,
        "estimated": True,
    }
    credits = credits_from_llm_usage(usage)
    return {
        **billing_breakdown(usage),
        "note": "Estimate only — final charge is based on actual Claude usage when you download the report.",
    }


async def credit_purchase_from_paystack(
    db: AsyncSession,
    user_id: str,
    package_id: str,
    payment_reference: str,
) -> dict[str, Any]:
    """Verify Paystack payment and credit wallet (idempotent)."""
    from services.paystack import verify_transaction, PaystackError

    existing = await find_purchase_by_reference(db, payment_reference)
    if existing:
        wallet = await get_or_create_wallet_async(db, user_id)
        return {
            "success": True,
            "already_processed": True,
            "balance": float(wallet.balance),
            "credits_added": 0.0,
        }

    packages = {p["id"]: p for p in get_credit_packages()}
    pkg = packages.get(package_id)
    if not pkg:
        raise ValueError("Unknown credit package")

    try:
        pay_data = await verify_transaction(payment_reference)
    except PaystackError as e:
        raise ValueError(e.message) from e

    status = pay_data.get("status")
    if status != "success":
        raise ValueError(f"Payment not successful (status: {status})")

    amount_paid_kobo = int(pay_data.get("amount") or 0)
    expected_kobo = int(pkg["price_naira"]) * 100
    if amount_paid_kobo < expected_kobo:
        raise ValueError("Paid amount does not match package price")

    meta = pay_data.get("metadata") or {}
    if str(meta.get("user_id", "")) not in ("", user_id):
        raise ValueError("Payment does not belong to this account")
    if meta.get("package_id") and meta.get("package_id") != package_id:
        raise ValueError("Payment package mismatch")

    credits = Decimal(str(pkg["credits"]))
    wallet = await add_credits_async(
        db,
        user_id,
        credits,
        CreditTransactionType.purchase,
        f"Purchased {pkg['label']} pack ({pkg['credits']} credits)",
        reference_id=payment_reference,
        extra={
            "package_id": package_id,
            "price_naira": pkg["price_naira"],
            "paystack_id": pay_data.get("id"),
            "channel": pay_data.get("channel"),
        },
    )
    return {
        "success": True,
        "already_processed": False,
        "balance": float(wallet.balance),
        "credits_added": float(credits),
    }


async def credit_purchase_from_stripe(
    db: AsyncSession,
    user_id: str,
    package_id: str,
    payment_reference: str,
) -> dict[str, Any]:
    """Verify Stripe payment and credit wallet (idempotent)."""
    from services.stripe import verify_transaction, StripeError

    existing = await find_purchase_by_reference(db, payment_reference)
    if existing:
        wallet = await get_or_create_wallet_async(db, user_id)
        return {
            "success": True,
            "already_processed": True,
            "balance": float(wallet.balance),
            "credits_added": 0.0,
        }

    packages = {p["id"]: p for p in get_credit_packages()}
    pkg = packages.get(package_id)
    if not pkg:
        raise ValueError("Unknown credit package")

    try:
        pay_data = await verify_transaction(payment_reference)
    except StripeError as e:
        raise ValueError(e.message) from e

    status = pay_data.get("status")
    if status != "success":
        raise ValueError(f"Payment not successful (status: {status})")

    amount_paid_kobo = int(pay_data.get("amount") or 0)
    expected_kobo = int(pkg["price_naira"]) * 100
    if amount_paid_kobo < expected_kobo:
        raise ValueError("Paid amount does not match package price")

    meta = pay_data.get("metadata") or {}
    if str(meta.get("user_id", "")) not in ("", user_id):
        raise ValueError("Payment does not belong to this account")
    if meta.get("package_id") and meta.get("package_id") != package_id:
        raise ValueError("Payment package mismatch")

    credits = Decimal(str(pkg["credits"]))
    wallet = await add_credits_async(
        db,
        user_id,
        credits,
        CreditTransactionType.purchase,
        f"Purchased {pkg['label']} pack ({pkg['credits']} credits)",
        reference_id=payment_reference,
        extra={
            "package_id": package_id,
            "price_naira": pkg["price_naira"],
            "stripe_id": pay_data.get("id"),
            "channel": pay_data.get("channel"),
        },
    )
    return {
        "success": True,
        "already_processed": False,
        "balance": float(wallet.balance),
        "credits_added": float(credits),
    }
