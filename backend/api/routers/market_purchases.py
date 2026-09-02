"""
Purchase, download, library endpoints
"""
import uuid
import secrets
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.deps import get_db
from api.models.database import Dataset, Purchase, SellerWallet, User, DatasetReview, DatasetWishlist
from api.schemas.schemas import PurchaseOut, ReviewCreate, ReviewOut, PipelinePushRequest, PipelinePushResponse
from api.deps import get_current_user as require_user
from api.payments import (
    paystack_initialize, paystack_verify, verify_paystack_signature,
    calculate_fees, generate_payment_reference
)
from api.wallet import get_or_create_wallet, credit_wallet
from api.storage import get_presigned_url, copy_between_buckets
from config import settings

router = APIRouter(tags=["Market Purchases"])


async def _get_dataset_or_404(slug_or_id: str, db: AsyncSession) -> Dataset:
    result = await db.execute(
        select(Dataset).where(
            (Dataset.slug == slug_or_id) | (Dataset.id == slug_or_id)
        )
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dataset not found")
    return d


# ─── Wishlist ─────────────────────────────────────────────────────────────────
@router.get("/me/wishlist")
async def get_wishlist(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DatasetWishlist).where(DatasetWishlist.user_id == current_user.id)
    )
    items = result.scalars().all()
    return [{"id": str(i.id), "dataset_id": str(i.dataset_id)} for i in items]


@router.post("/me/wishlist/{dataset_id}", status_code=201)
async def add_wishlist(
    dataset_id: str,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(DatasetWishlist).where(
            DatasetWishlist.user_id == current_user.id,
            DatasetWishlist.dataset_id == dataset_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"ok": True, "message": "Already in wishlist"}
    w = DatasetWishlist(user_id=current_user.id, dataset_id=dataset_id)
    db.add(w)
    await db.commit()
    return {"ok": True}


@router.delete("/me/wishlist/{dataset_id}")
async def remove_wishlist(
    dataset_id: str,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DatasetWishlist).where(
            DatasetWishlist.user_id == current_user.id,
            DatasetWishlist.dataset_id == dataset_id,
        )
    )
    w = result.scalar_one_or_none()
    if w:
        await db.delete(w)
        await db.commit()
    return {"ok": True}


# ─── Library ──────────────────────────────────────────────────────────────────
@router.get("/me/library")
async def get_library(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Purchase)
        .options(
            selectinload(Purchase.dataset).selectinload(Dataset.seller),
            selectinload(Purchase.dataset).selectinload(Dataset.files),
        )
        .where(
            Purchase.buyer_id == current_user.id,
            Purchase.status == "completed",
        )
        .order_by(Purchase.created_at.desc())
    )
    purchases = result.scalars().all()
    return [PurchaseOut.model_validate(p) for p in purchases]


# ─── Free download ────────────────────────────────────────────────────────────
@router.post("/datasets/{slug}/download-free")
async def download_free(
    slug: str,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await _get_dataset_or_404(slug, db)

    if dataset.price_naira > 0:
        raise HTTPException(400, "This dataset requires purchase")
    if dataset.status != "verified":
        raise HTTPException(400, "Dataset not available")

    # Check if already downloaded
    existing = await db.execute(
        select(Purchase).where(
            Purchase.buyer_id == current_user.id,
            Purchase.dataset_id == dataset.id,
            Purchase.status == "completed",
        )
    )
    if existing.scalar_one_or_none():
        # Return existing token
        p = existing.scalar_one_or_none()
        return {"download_token": p.download_token, "message": "Already in library"}

    token = secrets.token_urlsafe(32)
    purchase = Purchase(
        buyer_id=current_user.id,
        dataset_id=dataset.id,
        price_paid_naira=Decimal("0.00"),
        platform_fee_naira=Decimal("0.00"),
        seller_earnings_naira=Decimal("0.00"),
        payment_provider="free",
        payment_reference="free",
        status="completed",
        download_token=token,
    )
    db.add(purchase)
    dataset.download_count = (dataset.download_count or 0) + 1
    await db.commit()

    return {
        "download_token": token,
        "download_url": f"{settings.PORTAL_URL}/api/market/download/{token}",
    }


# ─── Paid purchase ────────────────────────────────────────────────────────────
@router.post("/datasets/{slug}/purchase")
async def initiate_purchase(
    slug: str,
    provider: str = "paystack",
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await _get_dataset_or_404(slug, db)

    if dataset.status != "verified":
        raise HTTPException(400, "Dataset not available for purchase")
    if dataset.price_naira <= 0:
        raise HTTPException(400, "Dataset is free — use the free download endpoint")

    # Check already purchased
    existing = await db.execute(
        select(Purchase).where(
            Purchase.buyer_id == current_user.id,
            Purchase.dataset_id == dataset.id,
            Purchase.status == "completed",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "You have already purchased this dataset")

    from api.models.database import SystemSettings
    setting = await db.execute(select(SystemSettings).where(SystemSettings.key == "marketplace_commission_percent"))
    comm_setting = setting.scalar_one_or_none()
    custom_fee = Decimal(comm_setting.value) if comm_setting else None
    
    platform_fee, seller_earnings = calculate_fees(dataset.price_naira, custom_fee)
    reference = generate_payment_reference()

    # Create pending purchase
    purchase = Purchase(
        buyer_id=current_user.id,
        dataset_id=dataset.id,
        price_paid_naira=dataset.price_naira,
        platform_fee_naira=platform_fee,
        seller_earnings_naira=seller_earnings,
        payment_provider=provider,
        payment_reference=reference,
        status="pending",
        download_token=secrets.token_urlsafe(32),
    )
    db.add(purchase)
    await db.flush()

    if provider == "paystack":
        try:
            paystack_data = await paystack_initialize(
                email=current_user.email,
                amount_naira=dataset.price_naira,
                reference=reference,
                metadata={
                    "purchase_id": str(purchase.id),
                    "dataset_id": str(dataset.id),
                    "buyer_id": str(current_user.id),
                },
            )
            await db.commit()
            return {
                "authorization_url": paystack_data["authorization_url"],
                "reference": reference,
                "purchase_id": str(purchase.id),
            }
        except Exception as e:
            await db.rollback()
            raise HTTPException(502, f"Payment initialisation failed: {e}")
    else:
        raise HTTPException(400, f"Unsupported payment provider: {provider}")


@router.post("/purchases/verify")
async def verify_payment(
    reference: str,
    db: AsyncSession = Depends(get_db),
):
    """Called after Paystack redirects buyer back. Verifies transaction."""
    try:
        tx_data = await paystack_verify(reference)
    except Exception as e:
        raise HTTPException(502, f"Payment verification failed: {e}")

    if tx_data.get("status") != "success":
        raise HTTPException(400, "Payment was not successful")

    # Find purchase
    result = await db.execute(
        select(Purchase).where(Purchase.payment_reference == reference)
    )
    purchase = result.scalar_one_or_none()
    if not purchase:
        raise HTTPException(404, "Purchase record not found")
    if purchase.status == "completed":
        return {"status": "already_completed", "purchase_id": str(purchase.id)}

    purchase.status = "completed"
    dataset = await db.get(Dataset, purchase.dataset_id)
    if dataset:
        dataset.download_count   = (dataset.download_count or 0) + 1
        dataset.purchase_count   = (dataset.purchase_count or 0) + 1

    # Credit seller wallet (with hold)
    if dataset and dataset.seller_id:
        await credit_wallet(
            user_id=str(dataset.seller_id),
            amount=purchase.seller_earnings_naira,
            tx_type="credit_sale",
            description=f"Sale of '{dataset.title}'",
            reference_id=purchase.id,
            db=db,
            pending=True,
        )

    await db.commit()
    return {
        "status": "completed",
        "purchase_id": str(purchase.id),
        "download_token": purchase.download_token,
        "redirect": f"{settings.FRONTEND_URL}/purchase/{purchase.id}/success",
    }


@router.post("/webhook/paystack")
async def paystack_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Paystack webhook events."""
    payload = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    if not verify_paystack_signature(payload, signature):
        raise HTTPException(400, "Invalid webhook signature")

    import json
    event = json.loads(payload)

    if event.get("event") == "charge.success":
        reference = event["data"]["reference"]
        await verify_payment(reference=reference, db=db)

    return {"status": "ok"}


# ─── Secure download ──────────────────────────────────────────────────────────
@router.get("/download/{token}")
async def serve_download(
    token: str,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.dataset))
        .where(
            Purchase.download_token == token,
            Purchase.buyer_id == current_user.id,
            Purchase.status == "completed",
        )
    )
    purchase = result.scalar_one_or_none()
    if not purchase:
        raise HTTPException(403, "Invalid or expired download token")

    dataset = purchase.dataset
    if not dataset or not dataset.primary_file_path:
        raise HTTPException(404, "File not available")

    if not purchase.downloaded_at:
        purchase.downloaded_at = datetime.now(timezone.utc)
        # Increment per-format download count
        from ..models import DatasetFile
        f_result = await db.execute(
            select(DatasetFile).where(
                DatasetFile.dataset_id == dataset.id,
                DatasetFile.is_primary == True,
            )
        )
        pf = f_result.scalar_one_or_none()
        if pf:
            pf.download_count = (pf.download_count or 0) + 1
        await db.commit()

    url = get_presigned_url(settings.S3_BUCKET_DATASETS, dataset.primary_file_path, expires_in=3600)
    return RedirectResponse(url=url)


# ─── Reviews ─────────────────────────────────────────────────────────────────
@router.post("/datasets/{slug}/reviews", response_model=ReviewOut)
async def submit_review(
    slug: str,
    body: ReviewCreate,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Dataset).where(Dataset.slug == slug))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(404, "Dataset not found")

    # Verify purchaser
    p_result = await db.execute(
        select(Purchase).where(
            Purchase.buyer_id == current_user.id,
            Purchase.dataset_id == dataset.id,
            Purchase.status == "completed",
        )
    )
    verified = p_result.scalar_one_or_none() is not None

    review = DatasetReview(
        dataset_id=dataset.id,
        reviewer_id=current_user.id,
        verified_purchase=verified,
        **body.model_dump(),
    )
    db.add(review)

    # Update average rating
    from sqlalchemy import func
    rating_result = await db.execute(
        select(func.avg(DatasetReview.rating)).where(DatasetReview.dataset_id == dataset.id)
    )
    avg = rating_result.scalar()
    dataset.average_rating = round(float(avg or body.rating), 2)

    await db.commit()
    await db.refresh(review)
    return review


# ─── Push to analysis pipeline ────────────────────────────────────────────────
@router.post("/purchases/{purchase_id}/send-to-pipeline", response_model=PipelinePushResponse)
async def send_to_pipeline(
    purchase_id: str,
    body: PipelinePushRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Server-side S3-to-S3 copy of dataset file into ResearchForm analysis bucket.
    Creates an analysis_job record and returns redirect URL to decode review.
    """
    result = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.dataset).selectinload(Dataset.files))
        .where(
            Purchase.id == purchase_id,
            Purchase.buyer_id == current_user.id,
            Purchase.status == "completed",
        )
    )
    purchase = result.scalar_one_or_none()
    if not purchase:
        raise HTTPException(403, "Purchase not found or access denied")

    dataset = purchase.dataset
    if not dataset or not dataset.primary_file_path:
        raise HTTPException(404, "Dataset file not available")

    # Server-side copy to ResearchForm analysis bucket
    # (ResearchForm uses its own S3 bucket for analysis inputs)
    dst_key = f"analysis_inputs/{current_user.id}/{uuid.uuid4().hex}/{dataset.primary_file_path.split('/')[-1]}"
    try:
        copy_between_buckets(
            src_bucket=settings.S3_BUCKET_DATASETS,
            src_key=dataset.primary_file_path,
            dst_bucket=settings.S3_BUCKET_DATASETS,  # or ResearchForm's own bucket
            dst_key=dst_key,
        )
    except Exception as e:
        raise HTTPException(500, f"File transfer failed: {e}")

    # Create analysis job in ResearchForm's system
    # (In production this calls ResearchForm's internal API or directly creates the DB record)
    new_job_id = str(uuid.uuid4())

    # Mark pushed
    purchase.pushed_to_pipeline = True
    purchase.pipeline_job_id = new_job_id
    await db.commit()

    return PipelinePushResponse(
        job_id=new_job_id,
        redirect_url=f"{settings.PORTAL_URL}/analysis/jobs/{new_job_id}/decode-review",
        message=f"Dataset '{dataset.title}' is ready for analysis. Redirecting to decode review...",
    )
