# backend/api/routers/admin.py
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import get_db, get_admin_user
from api.models.database import User, CreditWallet, CreditTransactionType, UserRole, Dataset, VerificationJob
from services.credits import add_credits_async
from services.email import send_dataset_review_email
import os
from datetime import datetime, timezone
from api.storage import get_presigned_url

router = APIRouter(dependencies=[Depends(get_admin_user)])

# ── Platform Overview Stats ────────────────────────────────────────────────────

@router.get("/stats")
async def platform_stats(db: AsyncSession = Depends(get_db)):
    """Return high-level platform metrics for the admin dashboard."""
    from sqlalchemy import func
    from api.models.database import CreditTransaction, SellerVerification, WithdrawalRequest

    # ── AnalysisJob optional (table may not exist in all deployments) ─────────
    try:
        from api.models.database import AnalysisJob
        _has_analysis = True
    except ImportError:
        _has_analysis = False

    # User counts
    user_result = await db.execute(select(User))
    all_users = user_result.scalars().all()
    total_users = len(all_users)
    by_role: dict = {}
    for u in all_users:
        r = u.role.value if hasattr(u.role, 'value') else str(u.role)
        by_role[r] = by_role.get(r, 0) + 1
    suspended_count = sum(1 for u in all_users if not u.is_verified)

    # Credits in circulation
    wallets_result = await db.execute(select(CreditWallet))
    wallets = wallets_result.scalars().all()
    total_credits = float(sum(w.balance for w in wallets))
    wallets_with_credits = sum(1 for w in wallets if w.balance > 0)

    # Credit transactions total (all-time purchased/granted)
    try:
        tx_result = await db.execute(
            select(func.sum(CreditTransaction.amount)).where(CreditTransaction.amount > 0)
        )
        total_credits_sold = float(tx_result.scalar() or 0)
    except Exception:
        total_credits_sold = 0.0

    # Pending datasets
    try:
        pending_ds_result = await db.execute(
            select(func.count(Dataset.id)).where(Dataset.status == "pending_verification")
        )
        pending_datasets = int(pending_ds_result.scalar() or 0)
    except Exception:
        pending_datasets = 0

    # Analysis jobs
    total_jobs = 0
    completed_jobs = 0
    if _has_analysis:
        try:
            jobs_result = await db.execute(select(func.count(AnalysisJob.id)))
            total_jobs = int(jobs_result.scalar() or 0)
            completed_result = await db.execute(
                select(func.count(AnalysisJob.id)).where(AnalysisJob.status == "done")
            )
            completed_jobs = int(completed_result.scalar() or 0)
        except Exception:
            pass

    # Pending KYC (SellerVerification) & withdrawals
    try:
        kyc_result = await db.execute(
            select(func.count(SellerVerification.id))
            .where(SellerVerification.status == "in_process")
        )
        pending_kyc = int(kyc_result.scalar() or 0)
    except Exception:
        pending_kyc = 0

    try:
        wd_result = await db.execute(
            select(func.count(WithdrawalRequest.id))
            .where(WithdrawalRequest.status == "pending")
        )
        pending_withdrawals = int(wd_result.scalar() or 0)
    except Exception:
        pending_withdrawals = 0

    return {
        "users": {
            "total": total_users,
            "by_role": by_role,
            "suspended": suspended_count,
            "active": total_users - suspended_count,
        },
        "credits": {
            "total_in_circulation": round(total_credits, 2),
            "wallets_with_credits": wallets_with_credits,
            "total_sold_all_time": round(total_credits_sold, 2),
        },
        "datasets": {
            "pending_review": pending_datasets,
        },
        "jobs": {
            "total": total_jobs,
            "completed": completed_jobs,
            "completion_rate": round(completed_jobs / max(total_jobs, 1) * 100, 1),
        },
        "pending_actions": {
            "kyc": pending_kyc,
            "withdrawals": pending_withdrawals,
            "datasets": pending_datasets,
            "total": pending_kyc + pending_withdrawals + pending_datasets,
        },
    }



@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value if hasattr(u.role, 'value') else str(u.role),
            "institution": u.institution,
            "referral_code": u.referral_code,
            "is_verified": u.is_verified,
            "suspended": not u.is_verified,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]

@router.get("/credits/wallets")
async def list_wallets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CreditWallet).options(selectinload(CreditWallet.user)).order_by(CreditWallet.balance.desc())
    )
    wallets = result.scalars().all()
    return [
        {
            "user_id": w.user_id,
            "email": w.user.email if w.user else "Unknown",
            "full_name": w.user.full_name if w.user else "Unknown",
            "balance": float(w.balance),
            "updated_at": w.updated_at.isoformat() if w.updated_at else None,
        }
        for w in wallets
    ]

class GrantCreditRequest(BaseModel):
    user_id: str
    amount: float
    description: str

@router.post("/credits/grant")
async def grant_credits(data: GrantCreditRequest, db: AsyncSession = Depends(get_db), current_admin: User = Depends(get_admin_user)):
    user = await db.get(User, data.user_id)
    if not user:
        raise HTTPException(404, "User not found")
        
    if data.amount == 0:
        raise HTTPException(400, "Amount must be non-zero")
        
    try:
        # add_credits_async requires positive amount, so we handle deduction slightly differently if it's negative
        if data.amount > 0:
            wallet = await add_credits_async(
                db,
                data.user_id,
                Decimal(str(data.amount)),
                CreditTransactionType.adjustment,
                f"Admin Adjustment: {data.description}",
                extra={"admin_id": current_admin.id}
            )
        else:
            # For deduction we need to do it manually or modify the service.
            # We'll do it manually here.
            from api.models.database import CreditTransaction
            from services.credits import get_or_create_wallet_async, _round_credits
            wallet = await get_or_create_wallet_async(db, data.user_id)
            amount_dec = Decimal(str(abs(data.amount)))
            if wallet.balance < amount_dec:
                 raise HTTPException(400, f"User only has {wallet.balance} credits.")
                 
            wallet.balance = _round_credits(wallet.balance - amount_dec)
            tx = CreditTransaction(
                user_id=data.user_id,
                amount=-amount_dec,
                type=CreditTransactionType.adjustment,
                description=f"Admin Deduction: {data.description}",
                balance_after=wallet.balance,
                extra={"admin_id": current_admin.id},
            )
            db.add(tx)
            
        await db.commit()
        return {"success": True, "balance": float(wallet.balance)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(400, str(e))

class SystemSettingUpdate(BaseModel):
    value: str

@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    from api.models.database import SystemSettings
    result = await db.execute(select(SystemSettings))
    settings = result.scalars().all()
    # Default operations cost to 5.00 if not found
    from config import settings as app_settings
    settings_dict = {s.key: s.value for s in settings}
    if "base_operations_cost" not in settings_dict:
        settings_dict["base_operations_cost"] = "5.00"
    if "credit_markup_multiplier" not in settings_dict:
        settings_dict["credit_markup_multiplier"] = str(app_settings.CREDIT_MARKUP_MULTIPLIER)
    return settings_dict

@router.post("/settings/{key}")
async def update_setting(key: str, data: SystemSettingUpdate, db: AsyncSession = Depends(get_db)):
    from api.models.database import SystemSettings
    setting = await db.get(SystemSettings, key)
    if not setting:
        setting = SystemSettings(key=key, value=data.value)
        db.add(setting)
    else:
        setting.value = data.value
    await db.commit()
    return {"key": key, "value": data.value}


# ── Credit Package Management ─────────────────────────────────────────────────

class CreditPackage(BaseModel):
    id: str
    label: str
    credits: float
    price_naira: float
    description: str = ""

class CreditPackagesUpdate(BaseModel):
    packages: list[CreditPackage]

@router.get("/credit-packages")
async def get_credit_packages_admin(db: AsyncSession = Depends(get_db)):
    """Get current credit packages (DB overrides config defaults)."""
    from services.credits import get_credit_packages_db
    packages = await get_credit_packages_db(db)
    return {"packages": packages}

@router.put("/credit-packages")
async def update_credit_packages(
    data: CreditPackagesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Save credit packages to SystemSettings as JSON (overrides config defaults)."""
    import json
    from api.models.database import SystemSettings

    if not data.packages:
        raise HTTPException(400, "At least one package is required")

    # Validate
    for pkg in data.packages:
        if pkg.credits <= 0:
            raise HTTPException(400, f"Package '{pkg.id}' must have credits > 0")
        if pkg.price_naira < 0:
            raise HTTPException(400, f"Package '{pkg.id}' price cannot be negative")

    packages_json = json.dumps([p.dict() for p in data.packages])
    setting = await db.get(SystemSettings, "credit_packages")
    if not setting:
        setting = SystemSettings(
            key="credit_packages",
            value=packages_json,
            description="Credit package definitions (overrides config defaults)",
        )
        db.add(setting)
    else:
        setting.value = packages_json
    await db.commit()
    return {"success": True, "packages": [p.dict() for p in data.packages]}

@router.get("/datasets/pending")
async def pending_datasets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Dataset)
        .options(selectinload(Dataset.seller))
        .where(Dataset.status == "pending_verification")
        .order_by(Dataset.created_at.asc())
    )
    datasets = result.scalars().all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "description": d.description,
            "domain": d.domain,
            "seller_email": d.seller.email if d.seller else "Unknown",
            "seller_name": d.seller.full_name if d.seller else "Unknown",
            "proof_document_path": d.proof_document_path,
            "created_at": d.created_at,
        }
        for d in datasets
    ]

@router.get("/datasets/{dataset_id}/download")
async def admin_download_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(404, "Dataset not found")
    
    if dataset.primary_file_path:
        from api.storage import get_presigned_url
        from config import settings as app_settings
        url = get_presigned_url(app_settings.S3_BUCKET_DATASETS, dataset.primary_file_path)
        return {"download_url": url}
        
    raise HTTPException(404, "Dataset file not found")

class DatasetReviewRequest(BaseModel):
    status: str
    rejection_reason: Optional[str] = None

@router.post("/datasets/{dataset_id}/review")
async def review_dataset(
    dataset_id: str,
    data: DatasetReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_admin_user),
):
    if data.status not in ["verified", "rejected"]:
        raise HTTPException(400, "Status must be 'verified' or 'rejected'")

    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found")

    dataset.status = data.status
    if data.status == "verified":
        dataset.verified_at = datetime.now(timezone.utc)
        dataset.rejection_reason = None
    else:
        dataset.rejection_reason = data.rejection_reason

    # Find associated verification job
    job_result = await db.execute(
        select(VerificationJob)
        .where(VerificationJob.dataset_id == dataset.id)
        .order_by(VerificationJob.created_at.desc())
        .limit(1)
    )
    job = job_result.scalar_one_or_none()
    if job:
        job.status = "completed" if data.status == "verified" else "rejected"
        job.manual_reviewer_id = current_admin.id
        job.rejection_reason = data.rejection_reason
        job.completed_at = datetime.now(timezone.utc)

    await db.commit()

    # Send email notification
    await db.refresh(dataset, ["seller"])
    if dataset.seller and dataset.seller.email:
        await send_dataset_review_email(
            to_email=dataset.seller.email,
            dataset_title=dataset.title,
            status=data.status,
            reason=data.rejection_reason
        )

    return {"success": True, "status": data.status}

from api.models.database import SellerVerification, WithdrawalRequest, SellerWallet

class KYCReviewRequest(BaseModel):
    status: str # "approved" or "denied"
    rejection_reason: Optional[str] = None

@router.get("/kyc-requests")
async def list_kyc_requests(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SellerVerification)
        .options(selectinload(SellerVerification.user))
        .where(SellerVerification.status.in_(["in_process", "approved", "denied"]))
        .order_by(SellerVerification.verified_at.desc().nullslast())
    )
    reqs = result.scalars().all()
    return [{
        "id": r.id,
        "user_id": r.user_id,
        "user_email": r.user.email if r.user else "Unknown",
        "user_name": r.user.full_name if r.user else "Unknown",
        "status": r.status,
        "id_document_type": r.id_document_type,
        "id_document_path": get_presigned_url(r.id_document_path, "id-docs") if r.id_document_path else None,
        "bank_name": r.bank_name,
        "account_number": r.account_number,
        "account_name": r.account_name,
        "rejection_reason": r.rejection_reason,
        "verified_at": r.verified_at
    } for r in reqs]

@router.post("/kyc-requests/{id}/review")
async def review_kyc(id: str, data: KYCReviewRequest, db: AsyncSession = Depends(get_db), current_admin: User = Depends(get_admin_user)):
    from services.email import send_kyc_status_email
    req = await db.get(SellerVerification, id)
    if not req:
        raise HTTPException(404, "Request not found")
        
    req.status = data.status
    req.verified_by = current_admin.id
    req.verified_at = datetime.now(timezone.utc)
    
    if data.status == "approved":
        req.rejection_reason = None
        # Update SellerWallet
        wallet_res = await db.execute(select(SellerWallet).where(SellerWallet.user_id == req.user_id))
        wallet = wallet_res.scalar_one_or_none()
        if not wallet:
            wallet = SellerWallet(user_id=req.user_id)
            db.add(wallet)
        wallet.bank_name = req.bank_name
        wallet.account_number = req.account_number
        wallet.account_name = req.account_name
        wallet.verified_bank = True
    else:
        req.rejection_reason = data.rejection_reason
        
    await db.commit()
    
    # Trigger email
    await db.refresh(req, ["user"])
    if req.user and req.user.email:
        await send_kyc_status_email(req.user.email, data.status, data.rejection_reason)
        
    return {"status": "success"}

class WithdrawalReviewRequest(BaseModel):
    status: str # "paid" or "rejected"
    rejection_reason: Optional[str] = None

@router.get("/withdrawals")
async def list_withdrawals(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WithdrawalRequest)
        .options(selectinload(WithdrawalRequest.user))
        .order_by(WithdrawalRequest.created_at.desc())
    )
    reqs = result.scalars().all()
    return [{
        "id": r.id,
        "user_email": r.user.email if r.user else "Unknown",
        "user_name": r.user.full_name if r.user else "Unknown",
        "amount": float(r.amount),
        "status": r.status,
        "bank_name": r.bank_name,
        "account_number": r.account_number,
        "account_name": r.account_name,
        "rejection_reason": r.rejection_reason,
        "created_at": r.created_at,
        "processed_at": r.processed_at
    } for r in reqs]

@router.post("/withdrawals/{id}/review")
async def review_withdrawal(id: str, data: WithdrawalReviewRequest, db: AsyncSession = Depends(get_db), current_admin: User = Depends(get_admin_user)):
    req = await db.get(WithdrawalRequest, id)
    if not req:
        raise HTTPException(404, "Request not found")
        
    if req.status != "pending":
        raise HTTPException(400, "Withdrawal is already processed")
        
    req.status = data.status
    req.processed_by = current_admin.id
    req.processed_at = datetime.now(timezone.utc)
    
    if data.status == "rejected":
        req.rejection_reason = data.rejection_reason
        # Refund the wallet
        from api.wallet import credit_wallet
        await credit_wallet(
            user_id=req.user_id,
            amount=req.amount,
            tx_type="credit_refund",
            description=f"Refund for rejected withdrawal: {data.rejection_reason}",
            pending=False,
            db=db
        )
    
    await db.commit()
    return {"status": "success"}


# ── User Management ───────────────────────────────────────────────────────────

class SuspendUserRequest(BaseModel):
    suspended: bool

class ChangeRoleRequest(BaseModel):
    role: str

@router.patch("/users/{user_id}/suspend")
async def suspend_user(user_id: str, data: SuspendUserRequest, db: AsyncSession = Depends(get_db)):
    """Suspend or unsuspend a user.

    Uses `is_verified` as a suspension proxy since the User model has no
    dedicated `is_active` / `suspended_at` column.  Setting `suspended=True`
    marks `is_verified=False`, which blocks login / access on the frontend.
    """
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    # suspended=True  →  is_verified=False  (account blocked)
    # suspended=False →  is_verified=True   (account restored)
    user.is_verified = not data.suspended
    await db.commit()
    return {"ok": True, "suspended": data.suspended}


@router.patch("/users/{user_id}/role")
async def change_user_role(user_id: str, data: ChangeRoleRequest, db: AsyncSession = Depends(get_db)):
    """Change the role of a user."""
    valid_roles = [r.value for r in UserRole]
    if data.role not in valid_roles:
        raise HTTPException(400, f"Invalid role. Must be one of: {', '.join(valid_roles)}")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    user.role = UserRole(data.role)
    await db.commit()
    return {"ok": True, "role": data.role}


@router.get("/users/{user_id}")
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    """Return full details for a single user."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "institution": user.institution,
        "referral_code": user.referral_code,
        "is_verified": user.is_verified,
        "suspended": not user.is_verified,
        "mfa_enabled": user.mfa_enabled,
        "username": user.username,
        "bio": user.bio,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
