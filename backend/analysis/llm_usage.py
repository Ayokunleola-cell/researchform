"""
Per-job LLM token tracking for usage-based credit billing.
"""
from __future__ import annotations

import contextvars
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

_current_job_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "llm_usage_job_id", default=None
)


@dataclass
class LLMCallRecord:
    model: str
    input_tokens: int
    output_tokens: int
    max_tokens_requested: int
    provider: str = "anthropic"


@dataclass
class LLMUsageSummary:
    job_id: Optional[str] = None
    calls: list[LLMCallRecord] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "calls": [asdict(c) for c in self.calls],
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "call_count": len(self.calls),
        }


# In-memory store for sync pipeline workers (keyed by job_id)
_job_summaries: dict[str, LLMUsageSummary] = {}


def start_job_tracking(job_id: str, previous_usage_dict: Optional[dict[str, Any]] = None) -> LLMUsageSummary:
    calls = []
    if previous_usage_dict and "calls" in previous_usage_dict:
        for c in previous_usage_dict.get("calls", []):
            calls.append(LLMCallRecord(**c))
    summary = LLMUsageSummary(job_id=job_id, calls=calls)
    _job_summaries[job_id] = summary
    _current_job_id.set(job_id)
    return summary


def end_job_tracking(job_id: str) -> LLMUsageSummary:
    _current_job_id.set(None)
    return _job_summaries.get(job_id) or LLMUsageSummary(job_id=job_id)


def get_job_usage(job_id: str) -> LLMUsageSummary:
    return _job_summaries.get(job_id) or LLMUsageSummary(job_id=job_id)


def record_llm_call(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    max_tokens_requested: int,
    provider: str = "anthropic",
    job_id: Optional[str] = None,
) -> None:
    jid = job_id or _current_job_id.get()
    if not jid:
        return
    summary = _job_summaries.setdefault(jid, LLMUsageSummary(job_id=jid))
    summary.calls.append(
        LLMCallRecord(
            model=model,
            input_tokens=max(0, int(input_tokens)),
            output_tokens=max(0, int(output_tokens)),
            max_tokens_requested=max_tokens_requested,
            provider=provider,
        )
    )


def estimate_tokens_from_text(text: str) -> int:
    """Rough token estimate when provider omits usage (≈4 chars per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)
