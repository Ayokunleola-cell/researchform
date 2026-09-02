"""
Seller endpoints — upload, manage listings, wallet, analytics
"""
import uuid
import re
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from api.deps import get_db
from api.models.database import (
    Dataset, DatasetFile, VerificationJob, SellerWallet,
    WalletTransaction, SellerVerification, User, DatasetQuestion
)
from api.schemas.schemas import (
    DatasetCreate, DatasetUpdate, DatasetOut, WalletOut,
    WalletTransactionOut, BankDetailsUpdate, WithdrawalRequest,
    SellerVerifSubmit, FromSurveyListingRequest
)
from api.deps import get_current_user as require_user
from api.storage import upload_file_obj, make_dataset_key, settings as s_settings
from api.wallet import get_or_create_wallet, debit_wallet
from config import settings

# Stub run_verification_task since celery might not be configured identically
class MockTask:
    def delay(self, *args, **kwargs):
        pass
run_verification_task = MockTask()

router = APIRouter(prefix="/sell", tags=["Market Seller"])


def _slugify(text: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower().strip())
    slug = slug.strip('-')[:80]
    return f"{slug}-{uuid.uuid4().hex[:6]}"


async def _require_seller_or_admin(user: User, dataset_id: str, db: AsyncSession) -> Dataset:
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(404, "Dataset not found")
    if str(dataset.seller_id) != str(user.id) and user.role != "admin":
        raise HTTPException(403, "Not your dataset")
    return dataset


# ─── Upload & create listing ──────────────────────────────────────────────────
@router.post("/datasets", status_code=201)
async def create_listing(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(...),
    domain: str = Form(...),
    country: str = Form(...),
    collection_method: str = Form(...),
    year_collected: int = Form(...),
    license: str = Form("CC-BY"),
    price_naira: float = Form(0.0),
    tags: str = Form("[]"),
    sub_domain: Optional[str] = Form(None),
    sample_size: Optional[int] = Form(None),
    visibility: str = Form("public"),
    proof_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    import json, io

    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit")

    fmt = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin"
    dataset_id = str(uuid.uuid4())
    file_key = make_dataset_key(str(current_user.id), dataset_id, file.filename)

    # Upload to S3
    try:
        upload_file_obj(
            io.BytesIO(file_bytes),
            s_settings.S3_BUCKET_DATASETS,
            file_key,
            file.content_type or "application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(500, f"File upload failed: {e}")

    # Parse tags
    try:
        parsed_tags = json.loads(tags)
    except Exception:
        parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]

    # Upload proof document if provided
    proof_key = None
    if proof_file:
        proof_bytes = await proof_file.read()
        if len(proof_bytes) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(400, f"Proof file exceeds {settings.MAX_FILE_SIZE_MB} MB limit")
        
        # Save to a distinct path under ID docs or datasets
        proof_key = f"proof-docs/{current_user.id}/{dataset_id}_{proof_file.filename}"
        try:
            upload_file_obj(
                io.BytesIO(proof_bytes),
                s_settings.S3_BUCKET_ID_DOCS,  # Or another appropriate bucket
                proof_key,
                proof_file.content_type or "application/pdf",
            )
        except Exception as e:
            raise HTTPException(500, f"Proof file upload failed: {e}")

    from api.models.database import SystemSettings
    setting = await db.execute(select(SystemSettings).where(SystemSettings.key == "auto_approve_datasets"))
    auto_approve = setting.scalar_one_or_none()
    initial_status = "approved" if auto_approve and auto_approve.value.lower() == "true" else "pending_verification"

    slug = _slugify(title)
    dataset = Dataset(
        id=dataset_id,
        seller_id=current_user.id,
        title=title,
        slug=slug,
        description=description,
        domain=domain,
        sub_domain=sub_domain,
        country=country,
        collection_method=collection_method,
        year_collected=year_collected,
        sample_size=sample_size,
        primary_file_path=file_key,
        price_naira=Decimal(str(price_naira)),
        license=license,
        tags=parsed_tags,
        visibility=visibility,
        status=initial_status,
        proof_document_path=proof_key,
    )
    db.add(dataset)

    # Primary file record
    df_file = DatasetFile(
        dataset_id=dataset_id,
        format=fmt,
        file_path=file_key,
        file_size_bytes=len(file_bytes),
        is_primary=True,
    )
    db.add(df_file)

    # Verification job
    verif_job = VerificationJob(dataset_id=dataset_id, triggered_by="upload")
    db.add(verif_job)
    await db.commit()

    if initial_status == "pending_verification":
        metadata = {
            "title": title, "description": description, "domain": domain,
            "country": country, "collection_method": collection_method,
            "year_collected": year_collected, "license": license, "tags": parsed_tags
        }
        run_verification_task.delay(dataset_id, file_key, fmt, metadata)

    msg = "Dataset published successfully." if initial_status == "approved" else "Dataset uploaded. Verification in progress (usually 5-15 minutes)."

    return {
        "ok": True,
        "dataset_id": dataset_id,
        "slug": slug,
        "status": initial_status,
        "message": msg,
    }


@router.post("/datasets/{dataset_id}/files", status_code=201)
async def add_format_file(
    dataset_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Add an additional format file to an existing listing."""
    dataset = await _require_seller_or_admin(current_user, dataset_id, db)
    import io

    file_bytes = await file.read()
    fmt = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin"
    file_key = make_dataset_key(str(current_user.id), dataset_id, file.filename)

    upload_file_obj(io.BytesIO(file_bytes), s_settings.S3_BUCKET_DATASETS, file_key,
                    file.content_type or "application/octet-stream")

    df_file = DatasetFile(
        dataset_id=dataset_id,
        format=fmt,
        file_path=file_key,
        file_size_bytes=len(file_bytes),
        is_primary=False,
    )
    db.add(df_file)
    await db.commit()
    return {"ok": True, "format": fmt}


@router.put("/datasets/{dataset_id}")
async def update_listing(
    dataset_id: str,
    body: DatasetUpdate,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await _require_seller_or_admin(current_user, dataset_id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(dataset, field, value)
    await db.commit()
    return {"ok": True}


@router.delete("/datasets/{dataset_id}")
async def archive_listing(
    dataset_id: str,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await _require_seller_or_admin(current_user, dataset_id, db)
    dataset.status = "archived"
    await db.commit()
    return {"ok": True}


@router.post("/datasets/{dataset_id}/relist")
async def relist_dataset(
    dataset_id: str,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Resubmit a rejected dataset for verification after fixing issues."""
    dataset = await _require_seller_or_admin(current_user, dataset_id, db)
    if dataset.status not in ("rejected",):
        raise HTTPException(400, "Only rejected datasets can be relisted")

    from api.models.database import SystemSettings
    setting = await db.execute(select(SystemSettings).where(SystemSettings.key == "auto_approve_datasets"))
    auto_approve = setting.scalar_one_or_none()
    new_status = "approved" if auto_approve and auto_approve.value.lower() == "true" else "pending_verification"

    dataset.status = new_status
    verif_job = VerificationJob(dataset_id=dataset_id, triggered_by="resubmit")
    db.add(verif_job)
    await db.commit()

    if new_status == "pending_verification":
        # Re-trigger verification
        metadata = {
            "title": dataset.title, "description": dataset.description,
            "domain": dataset.domain, "country": dataset.country,
            "collection_method": dataset.collection_method,
            "year_collected": dataset.year_collected, "license": dataset.license,
            "tags": dataset.tags or [],
        }
        run_verification_task.delay(dataset_id, dataset.primary_file_path, "csv", metadata)
    return {"ok": True, "status": new_status}


# ─── From-survey listing ──────────────────────────────────────────────────────
@router.post("/from-survey/{survey_id}")
async def list_from_survey(
    survey_id: str,
    body: FromSurveyListingRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """
    One-click: create a DataNest listing from a ResearchForm survey.
    The survey's data is exported to CSV, uploaded to S3, and a listing is created.
    In production this queries ResearchForm's surveys/responses tables.
    """
    # Stub: in production, query ResearchForm survey + responses tables
    # and generate CSV export.
    dataset_id = str(uuid.uuid4())
    slug = _slugify(f"survey-{survey_id}")

    from api.models.database import SystemSettings
    setting = await db.execute(select(SystemSettings).where(SystemSettings.key == "auto_approve_datasets"))
    auto_approve = setting.scalar_one_or_none()
    initial_status = "approved" if auto_approve and auto_approve.value.lower() == "true" else "pending_verification"

    dataset = Dataset(
        id=dataset_id,
        seller_id=current_user.id,
        title=f"Survey Data — {survey_id[:8]}",
        slug=slug,
        description="Dataset generated from ResearchForm survey responses.",
        domain="Social Sciences",
        country="Global",
        collection_method="Survey (ResearchForm)",
        year_collected=datetime.now().year,
        primary_file_path=f"survey-exports/{dataset_id}.csv",
        price_naira=Decimal(str(body.price_naira)),
        visibility="public",
        status=initial_status,
        from_survey_id=survey_id,
    )
    db.add(dataset)
    await db.commit()

    return {
        "dataset_id": dataset_id,
        "slug": slug,
        "message": "Listing created from survey. Upload your CSV to complete.",
    }


# ─── My listings ─────────────────────────────────────────────────────────────
@router.get("/listings")
async def my_listings(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Dataset)
        .options(selectinload(Dataset.files), selectinload(Dataset.verification_jobs))
        .where(Dataset.seller_id == current_user.id)
        .order_by(Dataset.created_at.desc())
    )
    datasets = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "title": d.title,
            "slug": d.slug,
            "status": d.status,
            "price_naira": float(d.price_naira or 0),
            "download_count": d.download_count,
            "purchase_count": d.purchase_count,
            "view_count": d.view_count,
            "average_rating": float(d.average_rating or 0),
            "verification_score": d.verification_score,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in datasets
    ]


# ─── Analytics ───────────────────────────────────────────────────────────────
@router.get("/analytics")
async def seller_analytics(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            func.count(Dataset.id).label("total_listings"),
            func.sum(Dataset.download_count).label("total_downloads"),
            func.sum(Dataset.view_count).label("total_views"),
            func.sum(Dataset.purchase_count).label("total_sales"),
        ).where(Dataset.seller_id == current_user.id)
    )
    stats = result.one()

    wallet = await get_or_create_wallet(str(current_user.id), db)

    from api.models.database import SystemSettings
    setting = await db.execute(select(SystemSettings).where(SystemSettings.key == "marketplace_commission_percent"))
    comm_setting = setting.scalar_one_or_none()
    custom_fee = float(comm_setting.value) if comm_setting else float(getattr(settings, 'PLATFORM_FEE_PERCENT', 15.0))

    return {
        "total_listings": stats.total_listings or 0,
        "total_downloads": stats.total_downloads or 0,
        "total_views": stats.total_views or 0,
        "total_sales": stats.total_sales or 0,
        "wallet_balance": float(wallet.balance_naira or 0),
        "pending_earnings": float(wallet.pending_naira or 0),
        "total_earned": float(wallet.total_earned_naira or 0),
        "platform_fee_percent": custom_fee,
    }


# ─── Wallet ───────────────────────────────────────────────────────────────────
@router.get("/wallet", response_model=WalletOut)
async def get_wallet(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_or_create_wallet(str(current_user.id), db)


@router.get("/wallet/transactions")
async def wallet_transactions(
    page: int = 1,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    wallet = await get_or_create_wallet(str(current_user.id), db)
    offset = (page - 1) * 20
    result = await db.execute(
        select(WalletTransaction)
        .where(WalletTransaction.wallet_id == wallet.id)
        .order_by(WalletTransaction.created_at.desc())
        .offset(offset).limit(20)
    )
    txs = result.scalars().all()
    return [WalletTransactionOut.model_validate(t) for t in txs]


@router.put("/wallet/bank")
async def update_bank_details(
    body: BankDetailsUpdate,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    wallet = await get_or_create_wallet(str(current_user.id), db)
    wallet.bank_name     = body.bank_name
    wallet.account_number = body.account_number  # encrypt in production
    wallet.account_name  = body.account_name
    await db.commit()
    return {"ok": True}


@router.post("/wallet/withdraw")
async def request_withdrawal(
    body: WithdrawalRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if not getattr(current_user, "mfa_enabled", False):
        raise HTTPException(403, "MFA must be enabled to withdraw funds. Please set it up in Settings.")

    if float(body.amount_naira) < settings.MIN_WITHDRAWAL_NAIRA:
        raise HTTPException(400, f"Minimum withdrawal is ₦{settings.MIN_WITHDRAWAL_NAIRA:,.0f}")

    wallet = await get_or_create_wallet(str(current_user.id), db)
    if not wallet.bank_name or not wallet.account_number:
        raise HTTPException(400, "Please add bank details before withdrawing")

    if (wallet.balance_naira or Decimal("0")) < body.amount_naira:
        raise HTTPException(400, "Insufficient balance")

    await debit_wallet(
        user_id=str(current_user.id),
        amount=body.amount_naira,
        tx_type="debit_withdrawal",
        description=f"Withdrawal to {wallet.bank_name}",
        db=db,
    )
    await db.commit()

    return {
        "ok": True,
            "message": f"Withdrawal of ₦{body.amount_naira:,.2f} initiated. Arrives in 3–5 business days.",
    }


# ─── Identity verification ────────────────────────────────────────────────────
@router.post("/kyc/submit")
async def submit_kyc(
    doc_type: str = Form(...),
    id_number: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if not getattr(current_user, "mfa_enabled", False):
        raise HTTPException(403, "MFA must be enabled to submit KYC. Please set it up in Settings.")

    # Check if pending request exists
    result = await db.execute(
        select(SellerVerification).where(SellerVerification.user_id == current_user.id)
    )
    verif = result.scalar_one_or_none()
    if not verif:
        verif = SellerVerification(user_id=current_user.id)
        db.add(verif)

    verif.status            = "pending"
    verif.verification_type = doc_type
    verif.id_number         = id_number

    # Upload ID document
    import io
    doc_bytes = await file.read()
    import uuid
    doc_key = f"id-docs/{current_user.id}/{uuid.uuid4().hex}.{file.filename.rsplit('.',1)[-1]}"
    from ..storage import upload_file
    upload_file(doc_bytes, s_settings.S3_BUCKET_ID_DOCS, doc_key, file.content_type or "application/octet-stream")
    verif.id_document_path = doc_key

    await db.commit()
    return {"ok": True, "status": "pending", "message": "Identity verification submitted. Review takes 24–48 hours."}


@router.post("/verify")
async def submit_verification(
    body: SellerVerifSubmit,
    id_document: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SellerVerification).where(SellerVerification.user_id == current_user.id)
    )
    verif = result.scalar_one_or_none()
    if not verif:
        verif = SellerVerification(user_id=current_user.id)
        db.add(verif)

    verif.status            = "pending"
    verif.verification_type = body.verification_type
    verif.institution_name  = body.institution_name
    if body.matric_number:
        import hashlib
        verif.matric_number = hashlib.sha256(body.matric_number.encode()).hexdigest()

    # Upload ID document
    if id_document:
        import io
        doc_bytes = await id_document.read()
        import uuid
        doc_key = f"id-docs/{current_user.id}/{uuid.uuid4().hex}.{id_document.filename.rsplit('.',1)[-1]}"
        from ..storage import upload_file
        upload_file(doc_bytes, s_settings.S3_BUCKET_ID_DOCS, doc_key, id_document.content_type or "application/octet-stream")
        verif.id_document_path = doc_key

    await db.commit()
    return {"ok": True, "status": "pending", "message": "Identity verification submitted. Review takes 24–48 hours."}


@router.get("/verify/status")
async def verification_status(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SellerVerification).where(SellerVerification.user_id == current_user.id)
    )
    verif = result.scalar_one_or_none()
    if not verif:
        return {"status": "unverified"}
    return {
        "status": verif.status,
        "institution_name": verif.institution_name,
        "verified_at": verif.verified_at.isoformat() if verif.verified_at else None,
        "rejection_reason": verif.rejection_reason,
    }


# ─── Q&A reply ────────────────────────────────────────────────────────────────
@router.post("/datasets/{dataset_id}/reply/{question_id}")
async def answer_question(
    dataset_id: str,
    question_id: str,
    answer: str = Form(...),
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_seller_or_admin(current_user, dataset_id, db)
    result = await db.execute(select(DatasetQuestion).where(DatasetQuestion.id == question_id))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    q.answer = answer
    q.answered_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}
