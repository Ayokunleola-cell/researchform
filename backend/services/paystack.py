"""Paystack integration for analysis credit purchases."""
from __future__ import annotations

from typing import Any, Optional

import httpx

from config import settings


class PaystackError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _headers() -> dict[str, str]:
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaystackError("Paystack is not configured", 503)
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def is_paystack_enabled() -> bool:
    return bool(settings.PAYSTACK_SECRET_KEY) and not settings.DEV_MODE


async def initialize_transaction(
    *,
    email: str,
    amount_kobo: int,
    reference: str,
    callback_url: str,
    metadata: Optional[dict] = None,
) -> dict[str, Any]:
    payload = {
        "email": email,
        "amount": amount_kobo,
        "reference": reference,
        "callback_url": callback_url,
        "currency": "NGN",
        "metadata": metadata or {},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.paystack.co/transaction/initialize",
            json=payload,
            headers=_headers(),
        )
    data = resp.json()
    if not resp.is_success or not data.get("status"):
        msg = data.get("message") or "Failed to initialize Paystack checkout"
        raise PaystackError(msg, resp.status_code)
    return data["data"]


async def verify_transaction(reference: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers=_headers(),
        )
    data = resp.json()
    if not resp.is_success or not data.get("status"):
        msg = data.get("message") or "Payment verification failed"
        raise PaystackError(msg, resp.status_code)
    return data["data"]
