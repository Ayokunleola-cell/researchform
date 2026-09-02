from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from decimal import Decimal

from api.deps import get_db, get_current_user, limiter
from fastapi import Request
from api.models.database import User, SellerWallet, SellerVerification, WithdrawalRequest, SystemSettings, CreditWallet
from api.storage import upload_file_obj, settings as s_settings
from api.wallet import debit_wallet
from services.email import send_kyc_status_email
import uuid

router = APIRouter()

class ConvertCreditsRequest(BaseModel):
    package_id: str

class WithdrawRequestSchema(BaseModel):
    amount_naira: Decimal = Field(gt=0)
    payout_method: str = "bank_transfer"
    paypal_email: str | None = None
    swift_code: str | None = None
    routing_number: str | None = None

@router.post("/kyc-submit")
@limiter.limit("5/minute")
async def submit_kyc(
    request: Request,
    id_document_type: str = Form(...),
    bank_name: str = Form(...),
    account_number: str = Form(...),
    account_name: str = Form(...),
    id_document: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Profile Completion Gate
    if not current_user.full_name or not current_user.institution or not current_user.avatar_path or not current_user.bio:
        raise HTTPException(status_code=400, detail="Please complete your profile (Name, Institution, Bio, and Profile Picture) before submitting KYC.")

    # 2. Upload Document
    path = f"kyc/{current_user.id}/{uuid.uuid4()}_{id_document.filename}"
    file_url = upload_file_obj(id_document.file, s_settings.S3_BUCKET_DATASETS, path, id_document.content_type)

    # 3. Create or update SellerVerification
    result = await db.execute(select(SellerVerification).where(SellerVerification.user_id == current_user.id))
    verification = result.scalar_one_or_none()

    if not verification:
        verification = SellerVerification(user_id=current_user.id)
        db.add(verification)

    verification.id_document_type = id_document_type
    verification.id_document_path = file_url
    verification.bank_name = bank_name
    verification.account_number = account_number
    verification.account_name = account_name
    
    # Generic Mock API Integration: Instantly approve KYC for testing purposes
    verification.status = "approved"
    verification.rejection_reason = None
    
    current_user.kyc_status = "verified"
    
    await db.flush()

    # 4. Trigger Email (Simulate approval email)
    await send_kyc_status_email(current_user.email, "approved")

    await db.commit()
    return {"status": "success", "message": "KYC submitted and verified successfully via mock API."}

@router.post("/withdraw")
@limiter.limit("3/minute")
async def withdraw_funds(
    request: Request,
    data: WithdrawRequestSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Check KYC Status
    result = await db.execute(select(SellerVerification).where(SellerVerification.user_id == current_user.id))
    verification = result.scalar_one_or_none()
    
    if not verification or verification.status != "approved" or current_user.kyc_status != "verified":
        raise HTTPException(status_code=400, detail="Your account is not fully verified. Please complete KYC verification first.")

    # 2. Check Min Withdrawal Amount
    min_wd_res = await db.execute(select(SystemSettings).where(SystemSettings.key == "MINIMUM_WITHDRAWAL_AMOUNT"))
    min_wd_setting = min_wd_res.scalar_one_or_none()
    min_amount = Decimal(min_wd_setting.value) if min_wd_setting else Decimal("5000")

    if data.amount_naira < min_amount:
        raise HTTPException(status_code=400, detail=f"Minimum withdrawal amount is N{min_amount}")

    # 3. Debit Wallet (will raise HTTP 400 if insufficient funds)
    # Using 'debit_withdrawal' type. The actual money will be sent later by admin.
    await debit_wallet(
        user_id=current_user.id,
        amount=data.amount_naira,
        tx_type="debit_withdrawal",
        description=f"Withdrawal Request via {data.payout_method}",
        db=db
    )

    # 4. Update Seller Wallet with preferences
    sw_res = await db.execute(select(SellerWallet).where(SellerWallet.user_id == current_user.id))
    sw = sw_res.scalar_one_or_none()
    if sw:
        sw.payout_method = data.payout_method
        if data.paypal_email: sw.paypal_email = data.paypal_email
        if data.swift_code: sw.swift_code = data.swift_code
        if data.routing_number: sw.routing_number = data.routing_number

    # 5. Create Withdrawal Request
    wr = WithdrawalRequest(
        user_id=current_user.id,
        amount=data.amount_naira,
        status="pending",
        payout_method=data.payout_method,
        bank_name=verification.bank_name,
        account_number=verification.account_number,
        account_name=verification.account_name,
        paypal_email=data.paypal_email,
        swift_code=data.swift_code,
        routing_number=data.routing_number
    )
    db.add(wr)
    
    await db.commit()
    return {"status": "success", "message": f"Withdrawal request for N{data.amount_naira} via {data.payout_method} submitted. Please allow 2 working days for processing."}

@router.post("/buy-credits")
@limiter.limit("5/minute")
async def buy_premium_credits(
    request: Request,
    data: ConvertCreditsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    package = next((p for p in s_settings.CREDIT_PACKAGES if p["id"] == data.package_id), None)
    if not package:
        raise HTTPException(status_code=400, detail="Invalid credit package selected.")
        
    amount_naira = Decimal(str(package["price_naira"]))
    credits_to_add = Decimal(str(package["credits"]))

    # 1. Debit Seller Wallet
    await debit_wallet(
        user_id=current_user.id,
        amount=amount_naira,
        tx_type="debit_buy_credits",
        description=f"Bought {credits_to_add} Premium Analysis Credits ({package['label']} Package)",
        db=db
    )

    # 2. Credit CreditWallet
    cw_res = await db.execute(select(CreditWallet).where(CreditWallet.user_id == current_user.id))
    cw = cw_res.scalar_one_or_none()
    if not cw:
        cw = CreditWallet(user_id=current_user.id)
        db.add(cw)
    
    cw.balance = (cw.balance or Decimal("0")) + credits_to_add
    
    await db.commit()
    return {"status": "success", "message": f"Successfully converted N{amount_naira} to {credits_to_add} Credits."}
