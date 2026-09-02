"""Stripe integration for analysis credit purchases."""
from __future__ import annotations

from typing import Any, Optional

import stripe
from config import settings

class StripeError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

def is_stripe_enabled() -> bool:
    return bool(settings.STRIPE_SECRET_KEY) and not settings.DEV_MODE

async def initialize_transaction(
    *,
    email: str,
    amount_kobo: int,  # This might be mapped to cents for Stripe if we assume 1 kobo ~ 1 cent? No, it's NGN. Stripe supports NGN. We'll pass it as NGN amount in kobo.
    reference: str,
    callback_url: str,
    metadata: Optional[dict] = None,
) -> dict[str, Any]:
    if not settings.STRIPE_SECRET_KEY:
        raise StripeError("Stripe is not configured", 503)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'ngn',
                    'unit_amount': amount_kobo,
                    'product_data': {
                        'name': metadata.get('package_id', 'Analysis Credits'),
                        'description': 'Purchase analysis credits on ResearchForm',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{callback_url}?reference={reference}&package_id={metadata.get('package_id', '')}",
            cancel_url=f"{callback_url}?reference={reference}&package_id={metadata.get('package_id', '')}",
            customer_email=email,
            client_reference_id=reference,
            metadata=metadata or {},
        )
        return {"authorization_url": session.url, "reference": session.id}
    except Exception as e:
        raise StripeError(str(e), 400)


async def verify_transaction(session_id: str) -> dict[str, Any]:
    if not settings.STRIPE_SECRET_KEY:
        raise StripeError("Stripe is not configured", 503)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            # Format response to match the Paystack structure slightly so it can be handled similarly
            return {
                "status": "success",
                "amount": session.amount_total,
                "metadata": session.metadata,
                "id": session.id,
                "channel": "stripe",
                "client_reference_id": session.client_reference_id
            }
        else:
            return {
                "status": session.payment_status,
                "amount": session.amount_total,
                "metadata": session.metadata,
            }
    except Exception as e:
        raise StripeError(str(e), 400)
