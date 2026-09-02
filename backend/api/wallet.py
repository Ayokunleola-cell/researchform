"""
Wallet operations — credit, debit, withdrawal
"""
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from api.models.database import SellerWallet, WalletTransaction, User
from config import settings


async def get_or_create_wallet(user_id: str, db: AsyncSession) -> SellerWallet:
    result = await db.execute(select(SellerWallet).where(SellerWallet.user_id == user_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        wallet = SellerWallet(user_id=user_id)
        db.add(wallet)
        await db.flush()
    return wallet


async def credit_wallet(
    user_id: str,
    amount: Decimal,
    tx_type: str,
    description: str,
    reference_id=None,
    db: AsyncSession = None,
    pending: bool = True,
) -> WalletTransaction:
    """
    Credit earnings to wallet.
    pending=True: goes to pending_naira (7-day hold).
    pending=False: goes directly to balance_naira.
    """
    wallet = await get_or_create_wallet(user_id, db)

    if pending:
        wallet.pending_naira = (wallet.pending_naira or Decimal("0")) + amount
    else:
        wallet.balance_naira = (wallet.balance_naira or Decimal("0")) + amount

    wallet.total_earned_naira = (wallet.total_earned_naira or Decimal("0")) + amount

    tx = WalletTransaction(
        wallet_id=wallet.id,
        type=tx_type,
        amount_naira=amount,
        reference_id=reference_id,
        description=description,
        balance_after=wallet.balance_naira,
    )
    db.add(tx)
    await db.flush()
    return tx


async def debit_wallet(
    user_id: str,
    amount: Decimal,
    tx_type: str,
    description: str,
    reference_id=None,
    db: AsyncSession = None,
) -> WalletTransaction:
    wallet = await get_or_create_wallet(user_id, db)

    if (wallet.balance_naira or Decimal("0")) < amount:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")

    wallet.balance_naira -= amount

    if tx_type == "debit_withdrawal":
        wallet.total_withdrawn_naira = (wallet.total_withdrawn_naira or Decimal("0")) + amount
        wallet.last_payout_at = datetime.now(timezone.utc)

    tx = WalletTransaction(
        wallet_id=wallet.id,
        type=tx_type,
        amount_naira=-amount,
        reference_id=reference_id,
        description=description,
        balance_after=wallet.balance_naira,
    )
    db.add(tx)
    await db.flush()
    return tx


async def release_pending_earnings(db: AsyncSession):
    """
    Cron job: move pending earnings older than EARNINGS_HOLD_DAYS to available balance.
    Called by Celery beat scheduler or background task daily.
    """
    from sqlalchemy import update
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.EARNINGS_HOLD_DAYS)

    # Find transactions that are still pending (cleared=False) and old enough
    result = await db.execute(
        select(WalletTransaction).where(
            WalletTransaction.type == "credit_sale",
            WalletTransaction.created_at <= cutoff,
            WalletTransaction.cleared == False
        )
    )
    txs = result.scalars().all()

    for tx in txs:
        wallet = await db.get(SellerWallet, tx.wallet_id)
        if wallet and wallet.pending_naira > 0:
            release = tx.amount_naira
            wallet.pending_naira -= release
            if wallet.pending_naira < 0:
                wallet.pending_naira = Decimal("0")
            wallet.balance_naira = (wallet.balance_naira or Decimal("0")) + release
            tx.cleared = True

    await db.commit()
