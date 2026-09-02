"""
Payment integrations — Paystack (NGN) + Stripe (USD)
"""
import hmac
import hashlib
import httpx
import uuid
from decimal import Decimal
from typing import Optional
from config import settings

PAYSTACK_BASE = "https://api.paystack.co"


# ─── Paystack ─────────────────────────────────────────────────────────────────
async def paystack_initialize(
    email: str,
    amount_naira: Decimal,
    reference: str,
    metadata: dict = None,
) -> dict:
    """Initialise a Paystack payment. Returns {authorization_url, access_code, reference}."""
    amount_kobo = int(amount_naira * 100)  # Paystack uses kobo
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "amount": amount_kobo,
        "reference": reference,
        "callback_url": settings.PAYSTACK_CALLBACK_URL,
        "metadata": metadata or {},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{PAYSTACK_BASE}/transaction/initialize", json=payload, headers=headers)
        data = resp.json()
        if not data.get("status"):
            raise ValueError(f"Paystack init failed: {data.get('message')}")
        return data["data"]


async def paystack_verify(reference: str) -> dict:
    """Verify a Paystack payment. Returns transaction data."""
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PAYSTACK_BASE}/transaction/verify/{reference}", headers=headers)
        data = resp.json()
        if not data.get("status"):
            raise ValueError(f"Paystack verify failed: {data.get('message')}")
        return data["data"]


def verify_paystack_signature(payload: bytes, signature: str) -> bool:
    """Verify webhook signature from Paystack."""
    secret = settings.PAYSTACK_SECRET_KEY.encode()
    computed = hmac.new(secret, payload, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, signature)


async def paystack_transfer(
    amount_naira: Decimal,
    account_number: str,
    bank_code: str,
    account_name: str,
    reference: str,
    reason: str = "DataNest payout",
) -> dict:
    """Initiate a Paystack bank transfer to a seller."""
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    # First create transfer recipient
    async with httpx.AsyncClient() as client:
        recip_resp = await client.post(
            f"{PAYSTACK_BASE}/transferrecipient",
            json={
                "type": "nuban",
                "name": account_name,
                "account_number": account_number,
                "bank_code": bank_code,
                "currency": "NGN",
            },
            headers=headers,
        )
        recip_data = recip_resp.json()
        if not recip_data.get("status"):
            raise ValueError(f"Recipient creation failed: {recip_data.get('message')}")
        recipient_code = recip_data["data"]["recipient_code"]

        # Then initiate transfer
        transfer_resp = await client.post(
            f"{PAYSTACK_BASE}/transfer",
            json={
                "source": "balance",
                "amount": int(amount_naira * 100),
                "recipient": recipient_code,
                "reason": reason,
                "reference": reference,
            },
            headers=headers,
        )
        transfer_data = transfer_resp.json()
        if not transfer_data.get("status"):
            raise ValueError(f"Transfer failed: {transfer_data.get('message')}")
        return transfer_data["data"]


# ─── Stripe ───────────────────────────────────────────────────────────────────
async def stripe_create_checkout(
    email: str,
    amount_usd_cents: int,
    dataset_id: str,
    success_url: str,
    cancel_url: str,
) -> dict:
    """Create a Stripe Checkout session. Returns {url, session_id}."""
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        session = stripe.checkout.Session.create(
            customer_email=email,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": amount_usd_cents,
                    "product_data": {"name": "DataNest Dataset Purchase"},
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"dataset_id": dataset_id},
        )
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        raise ValueError(f"Stripe checkout failed: {e}")


# ─── Fee calculator ───────────────────────────────────────────────────────────
from typing import Any, Optional

def calculate_fees(price_naira: Decimal, custom_fee_percent: Optional[Decimal] = None) -> tuple[Decimal, Decimal]:
    """
    Returns (platform_fee, seller_earnings).
    Platform takes custom_fee_percent or falls back to PLATFORM_FEE_PERCENT.
    """
    if custom_fee_percent is not None:
        fee_pct = custom_fee_percent / Decimal("100")
    else:
        fee_pct = Decimal(str(settings.PLATFORM_FEE_PERCENT)) / Decimal("100")
    platform_fee = (price_naira * fee_pct).quantize(Decimal("0.01"))
    seller_earnings = (price_naira - platform_fee).quantize(Decimal("0.01"))
    return platform_fee, seller_earnings


def generate_payment_reference() -> str:
    return f"DN-{uuid.uuid4().hex[:16].upper()}"
