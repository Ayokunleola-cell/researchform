"""Unit tests for analysis credit wallet math and purchase idempotency."""
import os
import sys
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.credits import (
    credits_from_llm_usage,
    estimate_analysis_credits,
    credit_purchase_from_paystack,
    InsufficientCreditsError,
    deduct_credits_sync,
    get_or_create_wallet_sync,
)
from config import settings


def test_credits_from_llm_usage_minimum_when_empty():
    assert credits_from_llm_usage(None) == Decimal(str(settings.CREDIT_MIN_REPORT_CHARGE))


def test_credits_from_llm_usage_scales_with_tokens():
    usage = {"total_input_tokens": 10_000, "total_output_tokens": 20_000}
    credits = credits_from_llm_usage(usage)
    assert credits >= Decimal(str(settings.CREDIT_MIN_REPORT_CHARGE))


def test_estimate_includes_chapters_doc():
    base = estimate_analysis_credits(study_types=["quantitative"], has_chapters_doc=False)
    with_doc = estimate_analysis_credits(study_types=["quantitative"], has_chapters_doc=True)
    assert with_doc["credits_required"] > base["credits_required"]


def test_deduct_raises_when_insufficient():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from api.models.database import Base, User, UserRole
    import uuid

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user_id = str(uuid.uuid4())
    db.add(
        User(
            id=user_id,
            email="credits@test.edu",
            hashed_password="x",
            full_name="Credit Test",
            role=UserRole.student,
        )
    )
    db.commit()
    wallet = get_or_create_wallet_sync(db, user_id)
    wallet.balance = Decimal("1.00")
    db.commit()
    with pytest.raises(InsufficientCreditsError):
        deduct_credits_sync(db, user_id, Decimal("5.00"), "job-1", "report")
    db.close()


def test_paystack_purchase_idempotent():
    import asyncio

    async def _run():
        db = AsyncMock()
        existing_tx = object()
        wallet_mock = type("W", (), {"balance": Decimal("50")})()

        with patch("services.credits.find_purchase_by_reference", new_callable=AsyncMock) as find_ref:
            find_ref.return_value = existing_tx
            with patch("services.credits.get_or_create_wallet_async", new_callable=AsyncMock) as get_wallet:
                get_wallet.return_value = wallet_mock
                return await credit_purchase_from_paystack(db, "user-1", "starter", "pay_ref_123")

    result = asyncio.run(_run())
    assert result["already_processed"] is True
    assert result["credits_added"] == 0.0
