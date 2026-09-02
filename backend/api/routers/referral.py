# backend/api/routers/referral.py
"""Referral / Ambassador system endpoints."""
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import get_db, get_current_user, get_admin_user
from api.models.database import User, ReferralEvent, CreditTransactionType, SystemSettings
from services.credits import add_credits_async, get_or_create_wallet_async

router = APIRouter()

# ─── helpers ────────────────────────────────────────────────────────────────

def _generate_referral_code(user_id: str) -> str:
    """Generate a short, readable 8-char alphanumeric code from user id."""
    import hashlib, base64
    digest = hashlib.sha256(user_id.encode()).digest()
    code = base64.b32encode(digest)[:8].decode().upper()
    return code


async def _get_or_create_referral_code(db: AsyncSession, user: User) -> str:
    """Ensure the user has a referral code, generate one if missing."""
    if user.referral_code:
        return user.referral_code
    code = _generate_referral_code(user.id)
    # Collision guard – extremely unlikely but safe
    existing = await db.execute(select(User).where(User.referral_code == code, User.id != user.id))
    if existing.scalar_one_or_none():
        import uuid
        code = base64.b32encode(uuid.uuid4().bytes)[:8].decode().upper()
    user.referral_code = code
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return code


async def _get_commission_pct(db: AsyncSession) -> Decimal:
    """Read referral_commission_pct from SystemSettings (default 10%)."""
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "referral_commission_pct")
    )
    setting = result.scalar_one_or_none()
    if setting:
        try:
            return Decimal(str(setting.value))
        except Exception:
            pass
    return Decimal("10.0")


async def _get_min_threshold(db: AsyncSession) -> Decimal:
    """Read referral_min_credits_threshold from SystemSettings (default 0 = no minimum)."""
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "referral_min_credits_threshold")
    )
    setting = result.scalar_one_or_none()
    if setting:
        try:
            return Decimal(str(setting.value))
        except Exception:
            pass
    return Decimal("0")  # 0 means no minimum


async def _get_referral_enabled(db: AsyncSession) -> bool:
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "referral_enabled")
    )
    setting = result.scalar_one_or_none()
    if setting:
        return setting.value.lower() not in ("false", "0", "off", "no")
    return True  # default enabled


# ─── User endpoints ─────────────────────────────────────────────────────────

@router.get("/me")
async def get_my_referral(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current user's referral code, link, and summary stats."""
    try:
        from config import settings as app_settings
        code = await _get_or_create_referral_code(db, user)
        base_url = app_settings.FRONTEND_URL.rstrip("/")
        referral_link = f"{base_url}/register?ref={code}"

        # Count referrals and paid conversions
        total_result = await db.execute(
            select(func.count(ReferralEvent.id)).where(ReferralEvent.referrer_id == user.id)
        )
        total_events = total_result.scalar() or 0

        earnings_result = await db.execute(
            select(func.sum(ReferralEvent.credits_earned)).where(ReferralEvent.referrer_id == user.id)
        )
        total_earned = float(earnings_result.scalar() or 0)

        # Count unique referees who signed up with your code
        ref_result = await db.execute(
            select(func.count(User.id)).where(User.referred_by_id == user.id)
        )
        total_referees = ref_result.scalar() or 0

        commission_pct = await _get_commission_pct(db)

        # Safely read referral_earnings (may be None if column was added after account creation)
        referral_earnings = 0.0
        try:
            referral_earnings = float(user.referral_earnings or 0)
        except Exception:
            pass

        return {
            "referral_code": code,
            "referral_link": referral_link,
            "total_referees": total_referees,
            "total_conversions": total_events,
            "total_credits_earned": total_earned,
            "commission_pct": float(commission_pct),
            "referral_earnings": referral_earnings,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load referral data: {str(e)}")


@router.get("/my-referees")
async def get_my_referees(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all users who signed up using this user's referral code."""
    result = await db.execute(
        select(User)
        .where(User.referred_by_id == user.id)
        .order_by(User.created_at.desc())
    )
    referees = result.scalars().all()

    # Get all referral events for these referees
    if referees:
        ref_ids = [r.id for r in referees]
        events_result = await db.execute(
            select(ReferralEvent).where(
                ReferralEvent.referrer_id == user.id,
                ReferralEvent.referee_id.in_(ref_ids)
            )
        )
        events_by_referee = {}
        for ev in events_result.scalars().all():
            events_by_referee.setdefault(ev.referee_id, []).append(ev)
    else:
        events_by_referee = {}

    out = []
    for r in referees:
        evs = events_by_referee.get(r.id, [])
        credits_from_this = sum(float(e.credits_earned) for e in evs)
        out.append({
            "id": r.id,
            "full_name": r.full_name,
            "email": r.email[:3] + "***" + r.email[r.email.index("@"):],  # masked
            "joined_at": str(r.created_at),
            "is_verified": r.is_verified,
            "has_paid": len(evs) > 0,
            "conversion_count": len(evs),
            "credits_earned_from": credits_from_this,
        })
    return {"referees": out, "total": len(out)}


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),  # login required
):
    """Public leaderboard — top referrers ranked by number of conversions."""
    limit = min(max(limit, 5), 50)

    # Top referrers by conversion count
    result = await db.execute(
        select(
            ReferralEvent.referrer_id,
            func.count(ReferralEvent.id).label("conversion_count"),
            func.sum(ReferralEvent.credits_earned).label("total_earned"),
        )
        .group_by(ReferralEvent.referrer_id)
        .order_by(func.count(ReferralEvent.id).desc())
        .limit(limit)
    )
    rows = result.all()

    if not rows:
        return {"leaderboard": []}

    # Fetch user info
    user_ids = [r.referrer_id for r in rows]
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    board = []
    for rank, row in enumerate(rows, start=1):
        u = users_map.get(row.referrer_id)
        if not u:
            continue
        # Privacy: show first name + last initial only
        parts = (u.full_name or "").split()
        display_name = parts[0] if parts else "User"
        if len(parts) > 1:
            display_name += f" {parts[-1][0]}."

        board.append({
            "rank": rank,
            "display_name": display_name,
            "initial": (u.full_name or "?")[0].upper(),
            "conversion_count": row.conversion_count,
            "total_credits_earned": float(row.total_earned or 0),
            "medal": {1: "gold", 2: "silver", 3: "bronze"}.get(rank),
        })

    return {"leaderboard": board}


# ─── Commission processing (called internally by credits router) ─────────────

async def process_referral_commission(
    db: AsyncSession,
    buyer_user: User,
    package_id: str,
    credits_purchased: Decimal,
    price_naira: float,
    payment_reference: str,
):
    """
    Award referral commission credits to the referrer when a referred user buys credits.
    Called from credits.py after a successful purchase.
    Idempotent: duplicate purchase_ref is silently ignored.
    """
    if not buyer_user.referred_by_id:
        return  # Not a referred user

    if not await _get_referral_enabled(db):
        return  # Referral program disabled

    # Check minimum purchase threshold
    min_threshold = await _get_min_threshold(db)
    if min_threshold > 0 and credits_purchased < min_threshold:
        return  # Purchase is below required minimum

    # Idempotency: skip if this purchase_ref was already processed
    existing = await db.execute(
        select(ReferralEvent).where(ReferralEvent.purchase_ref == payment_reference)
    )
    if existing.scalar_one_or_none():
        return  # Already processed

    # Self-referral guard (extra safety)
    if buyer_user.referred_by_id == buyer_user.id:
        return

    commission_pct = await _get_commission_pct(db)
    credits_earned = (credits_purchased * commission_pct / Decimal("100")).quantize(Decimal("0.0001"))

    if credits_earned <= 0:
        return

    # Award credits to referrer
    referrer = await db.get(User, buyer_user.referred_by_id)
    if not referrer:
        return

    await add_credits_async(
        db,
        referrer.id,
        credits_earned,
        CreditTransactionType.referral_commission,
        f"Referral commission — {buyer_user.full_name} purchased {package_id} pack",
        reference_id=payment_reference,
        extra={
            "referee_id": buyer_user.id,
            "referee_name": buyer_user.full_name,
            "package_id": package_id,
            "commission_pct": float(commission_pct),
            "credits_purchased": float(credits_purchased),
        },
    )

    # Update referrer's total earnings field
    referrer.referral_earnings = (referrer.referral_earnings or Decimal("0")) + credits_earned
    db.add(referrer)

    # Record referral event
    event = ReferralEvent(
        referrer_id=referrer.id,
        referee_id=buyer_user.id,
        purchase_ref=payment_reference,
        package_id=package_id,
        credits_purchased=credits_purchased,
        amount_naira=Decimal(str(price_naira)),
        commission_pct=commission_pct,
        credits_earned=credits_earned,
    )
    db.add(event)
    # Note: caller commits the transaction


# ─── Admin endpoints ─────────────────────────────────────────────────────────

@router.get("/admin/stats", dependencies=[Depends(get_admin_user)])
async def admin_referral_stats(db: AsyncSession = Depends(get_db)):
    """Admin: platform-wide referral statistics."""
    total_events = (await db.execute(select(func.count(ReferralEvent.id)))).scalar() or 0
    total_commission = (await db.execute(select(func.sum(ReferralEvent.credits_earned)))).scalar() or 0
    total_referrers = (await db.execute(
        select(func.count(func.distinct(ReferralEvent.referrer_id)))
    )).scalar() or 0
    total_referred_users = (await db.execute(
        select(func.count(User.id)).where(User.referred_by_id.isnot(None))
    )).scalar() or 0
    commission_pct = await _get_commission_pct(db)
    min_threshold = await _get_min_threshold(db)
    enabled = await _get_referral_enabled(db)

    return {
        "enabled": enabled,
        "commission_pct": float(commission_pct),
        "min_credits_threshold": float(min_threshold),
        "total_referral_events": total_events,
        "total_credits_paid_out": float(total_commission),
        "total_active_referrers": total_referrers,
        "total_referred_users": total_referred_users,
    }


@router.get("/admin/events", dependencies=[Depends(get_admin_user)])
async def admin_referral_events(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Admin: paginated list of all referral commission events."""
    limit = min(max(limit, 1), 100)
    result = await db.execute(
        select(ReferralEvent)
        .options(
            selectinload(ReferralEvent.referrer),
            selectinload(ReferralEvent.referee),
        )
        .order_by(ReferralEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    events = result.scalars().all()
    total = (await db.execute(select(func.count(ReferralEvent.id)))).scalar() or 0

    return {
        "total": total,
        "events": [
            {
                "id": e.id,
                "referrer_name": e.referrer.full_name if e.referrer else "—",
                "referrer_email": e.referrer.email if e.referrer else "—",
                "referee_name": e.referee.full_name if e.referee else "—",
                "referee_email": e.referee.email if e.referee else "—",
                "package_id": e.package_id,
                "credits_purchased": float(e.credits_purchased),
                "amount_naira": float(e.amount_naira or 0),
                "commission_pct": float(e.commission_pct),
                "credits_earned": float(e.credits_earned),
                "created_at": str(e.created_at),
            }
            for e in events
        ],
    }
