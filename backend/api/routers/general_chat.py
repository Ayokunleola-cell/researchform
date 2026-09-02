"""
General-purpose Claude AI chat endpoint.
Supports three context modes:
  - general  : research assistant chat
  - analysis : loads a completed AnalysisJob (results, data dictionary, report)
  - dataset  : accepts dataset metadata from the frontend

Claude AI only (Anthropic). Credits are deducted per message, identical to
the per-job analysis chat in api/routers/chat.py.
"""
import json
from decimal import Decimal
from typing import List, Optional, Any

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.deps import get_current_user, get_db
from api.models.database import (
    User, AnalysisJob, CreditWallet, CreditTransaction,
    CreditTransactionType,
)
from config import settings

router = APIRouter()

# ─── Schemas ──────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str        # 'user' | 'assistant'
    content: str

class GeneralChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    context_type: str = "general"       # "general" | "analysis" | "dataset"
    context_id: Optional[str] = None    # job_id when context_type == "analysis"
    context_data: Optional[Any] = None  # dataset info dict when context_type == "dataset"

class GeneralChatResponse(BaseModel):
    response: str
    role: str = "assistant"
    credits_used: float = 0.0
    tokens_used: int = 0
    wallet_balance: float = 0.0

# ─── System-prompt builders ────────────────────────────────────────────────────

GENERAL_SYSTEM_PROMPT = """You are ResearchForm AI, a knowledgeable assistant for academic researchers and data scientists.
You can help with:
- Research methodology and study design
- Statistical concepts and data analysis interpretation
- Survey design and data collection strategies
- Academic writing, citations, and literature reviews
- Interpreting results, p-values, confidence intervals, and effect sizes
- Choosing the right statistical test for a study
- Understanding the ResearchForm platform and marketplace

Be concise, accurate, and helpful. Use markdown formatting (headers, bullet points, code blocks) when it adds clarity.
When you don't know something, say so honestly."""


def _analysis_system_prompt(job: AnalysisJob) -> str:
    """Build a rich system prompt from a completed AnalysisJob — includes
    results, data dictionary, cleaning summary and full report text."""

    def _safe(val, label=""):
        if val is None:
            return f"  {label}: Not available" if label else "Not available"
        if isinstance(val, (dict, list)):
            return json.dumps(val, indent=2)
        return str(val)

    techniques = ", ".join(job.selected_techniques or []) or "Not specified"
    study_types = ", ".join(job.study_types or []) or "Not specified"

    sections = [
        f"""You are ResearchForm AI, a world-class statistical analysis expert.
You are helping a researcher deeply understand their completed data analysis.
Answer all questions using the data below. Be precise, cite specific numbers when relevant,
and explain statistical concepts in plain English where possible.
Use markdown formatting for clarity.\n""",

        "═══════ PROJECT CONTEXT ═══════",
        f"Source file     : {job.source_filename or 'Unknown'}",
        f"Dataset size    : {job.n_rows or '?'} rows × {job.n_columns or '?'} columns",
        f"Complete rows   : {job.n_complete_rows or '?'}",
        f"Techniques      : {techniques}",
        f"Study type(s)   : {study_types}",

        "\n═══════ PROJECT BRIEF ═══════",
        _safe(job.project_brief),

        "\n═══════ DATA DICTIONARY ═══════",
        _safe(job.data_dictionary),

        "\n═══════ DATA CLEANING SUMMARY ═══════",
        _safe(job.cleaning_summary),

        "\n═══════ FULL STATISTICAL RESULTS ═══════",
        _safe(job.results),
    ]

    # Include report text if available (rich narrative context)
    if job.report_text:
        sections += [
            "\n═══════ GENERATED REPORT TEXT ═══════",
            str(job.report_text)[:8000],   # cap at ~8k chars to stay within context
        ]

    return "\n".join(sections)


def _dataset_system_prompt(ctx: dict) -> str:
    """Build a system prompt from dataset metadata supplied by the frontend."""
    files_str = ""
    for f in (ctx.get("files") or []):
        fmt = (f.get("format") or "?").upper()
        rows = f.get("row_count", "?")
        cols = f.get("column_count", "?")
        size_bytes = f.get("file_size_bytes")
        size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes else "size unknown"
        files_str += f"  • {fmt}: {rows} rows × {cols} columns ({size_str})\n"

    return f"""You are ResearchForm AI, a research data expert.
You are helping a researcher evaluate and work with a specific marketplace dataset.
Answer questions about its uses, quality, potential biases, suitable analyses, and preprocessing steps.
Use markdown formatting for clarity.

═══════ DATASET INFORMATION ═══════
Title         : {ctx.get('title', 'Unknown')}
Domain        : {ctx.get('domain', 'Unknown')}
Country/Region: {ctx.get('country', 'Unknown')}
Sample size   : {ctx.get('sample_size', 'Unknown')} records
License       : {ctx.get('license', 'Unknown')}
Price         : ₦{float(ctx.get('price_naira', 0)):,.0f}
Downloads     : {ctx.get('download_count', 0)}
Avg. rating   : {ctx.get('average_rating', 0)}/5.0

DESCRIPTION:
{ctx.get('description', 'No description provided.')}

AVAILABLE FILES:
{files_str.rstrip() or '  No file details available'}"""


# ─── Credit helpers ────────────────────────────────────────────────────────────

# Same rates as api/routers/chat.py for consistency
_COST_PER_1M_INPUT  = 0.25   # USD
_COST_PER_1M_OUTPUT = 1.25   # USD
_USD_TO_CREDIT      = 10.0   # 1 credit ≈ $0.10


def _calc_credits(input_tokens: int, output_tokens: int) -> float:
    cost_usd = (
        (input_tokens  / 1_000_000) * _COST_PER_1M_INPUT +
        (output_tokens / 1_000_000) * _COST_PER_1M_OUTPUT
    )
    return cost_usd * _USD_TO_CREDIT


async def _check_and_deduct(
    user_id: str,
    credits: float,
    description: str,
    db: AsyncSession,
) -> float:
    """Deduct credits from wallet and record the transaction. Returns new balance."""
    w_res = await db.execute(
        select(CreditWallet).where(CreditWallet.user_id == user_id)
    )
    wallet = w_res.scalar_one_or_none()

    if wallet is None:
        raise HTTPException(status_code=402, detail="No credit wallet found. Please contact support.")

    current = float(wallet.balance)
    if current <= 0:
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please top up your credit wallet to continue chatting.",
        )

    new_balance = current - credits
    wallet.balance = Decimal(str(new_balance))

    tx = CreditTransaction(
        user_id=user_id,
        amount=Decimal(str(-credits)),
        type=CreditTransactionType.chat_inference,
        description=description,
        balance_after=Decimal(str(new_balance)),
    )
    db.add(tx)
    await db.commit()
    return new_balance


# ─── Route ─────────────────────────────────────────────────────────────────────

@router.post("/general", response_model=GeneralChatResponse)
async def general_chat(
    payload: GeneralChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Context-aware Claude AI chat with credit deduction.

    context_type = "general"  → research assistant, no extra data needed
    context_type = "analysis" → loads the AnalysisJob identified by context_id
    context_type = "dataset"  → uses context_data dict supplied by the frontend
    """
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Claude AI is not configured. Please set ANTHROPIC_API_KEY in the backend .env file.",
        )

    # ── Pre-flight credit check ────────────────────────────────────────────────
    w_res = await db.execute(
        select(CreditWallet).where(CreditWallet.user_id == current_user.id)
    )
    wallet = w_res.scalar_one_or_none()
    if wallet is None or float(wallet.balance) <= 0:
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please top up your credit wallet to continue chatting.",
        )

    # ── Build conversation history ─────────────────────────────────────────────
    messages = [{"role": m.role, "content": m.content} for m in payload.history]
    messages.append({"role": "user", "content": payload.message})

    # ── Select system prompt ───────────────────────────────────────────────────
    if payload.context_type == "analysis" and payload.context_id:
        result = await db.execute(
            select(AnalysisJob).where(
                AnalysisJob.id == payload.context_id,
                AnalysisJob.user_id == current_user.id,
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=404,
                detail="Analysis job not found or you do not have permission to access it.",
            )
        if job.status != "complete":
            raise HTTPException(
                status_code=400,
                detail="This analysis job is not yet complete. Please wait for it to finish.",
            )
        system_prompt = _analysis_system_prompt(job)
        context_label = f"analysis job '{job.source_filename or job.id[:8]}'"

    elif payload.context_type == "dataset" and payload.context_data:
        ctx = payload.context_data if isinstance(payload.context_data, dict) else {}
        system_prompt = _dataset_system_prompt(ctx)
        context_label = f"dataset '{ctx.get('title', 'unknown')}'"

    else:
        system_prompt = GENERAL_SYSTEM_PROMPT
        context_label = "general research chat"

    # ── Call Claude ────────────────────────────────────────────────────────────
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model="claude-3-haiku-20240307",
            system=system_prompt,
            max_tokens=2048,
            messages=messages,
        )
        ai_text       = resp.content[0].text
        input_tokens  = resp.usage.input_tokens
        output_tokens = resp.usage.output_tokens
        total_tokens  = input_tokens + output_tokens

    except anthropic.AuthenticationError:
        raise HTTPException(status_code=503, detail="Claude AI authentication failed. Check ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Claude AI rate limit reached. Please try again shortly.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude AI error: {str(e)}")

    # ── Deduct credits ─────────────────────────────────────────────────────────
    credits_used = _calc_credits(input_tokens, output_tokens)
    description  = (
        f"AI Chat ({context_label}) — "
        f"{total_tokens:,} tokens ({input_tokens:,} in + {output_tokens:,} out)"
    )

    new_balance = await _check_and_deduct(
        user_id=current_user.id,
        credits=credits_used,
        description=description,
        db=db,
    )

    return GeneralChatResponse(
        response=ai_text,
        role="assistant",
        credits_used=round(credits_used, 4),
        tokens_used=total_tokens,
        wallet_balance=round(new_balance, 4),
    )
