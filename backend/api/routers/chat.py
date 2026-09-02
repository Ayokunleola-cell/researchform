import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from api.deps import get_db, get_current_user
from api.models.database import AnalysisJob, AnalysisChat, User, CreditTransaction, CreditTransactionType, SystemSettings
from api.schemas.schemas import ChatMessageRequest, ChatMessageResponse
from services.credits import deduct_credits_sync
from config import settings
import anthropic

anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

router = APIRouter()

@router.get("/{job_id}/chat", response_model=list[ChatMessageResponse])
async def get_chat_history(job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(AnalysisChat).where(AnalysisChat.job_id == job_id).order_by(AnalysisChat.created_at))
    return result.scalars().all()

@router.post("/{job_id}/chat", response_model=ChatMessageResponse)
async def send_chat_message(job_id: str, payload: ChatMessageRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 1. Verify job exists and belongs to user
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.user_id == current_user.id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    # 2. Save user message
    user_msg = AnalysisChat(
        job_id=job_id,
        user_id=current_user.id,
        role="user",
        content=payload.message
    )
    db.add(user_msg)
    await db.commit()

    # 3. Fetch chat history for context
    history_result = await db.execute(select(AnalysisChat).where(AnalysisChat.job_id == job_id).order_by(AnalysisChat.created_at))
    history = history_result.scalars().all()

    # 4. Build prompt context
    system_prompt = f"""You are a statistical data analysis assistant. 
You are helping the user understand the results of their statistical analysis.
Here is the project brief: {json.dumps(job.project_brief)}
Here are the statistical results computed by the pipeline: {json.dumps(job.results)}

Answer the user's questions clearly, accurately, and without jargon where possible. Keep your answers concise."""

    messages = []
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    # 5. Call Anthropic API
    try:
        response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            system=system_prompt,
            max_tokens=1024,
            messages=messages
        )
        ai_content = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        
        # Calculate cost in credits (e.g., $0.25 / 1M input, $1.25 / 1M output)
        # We can dynamically pull credit exchange rate, but for now we'll do a simple conversion
        # 1 credit = $1. Let's charge a micro-fee for the tokens.
        cost_usd = (input_tokens / 1_000_000) * 0.25 + (output_tokens / 1_000_000) * 1.25
        credit_cost = cost_usd * 10  # Arbitrary multiplier to make it visible
        
        # 6. Save AI response
        ai_msg = AnalysisChat(
            job_id=job_id,
            user_id=current_user.id,
            role="assistant",
            content=ai_content,
            tokens_used=input_tokens + output_tokens
        )
        db.add(ai_msg)
        
        # 7. Deduct credits
        if credit_cost > 0:
            tx = CreditTransaction(
                user_id=current_user.id,
                amount=-credit_cost,
                type=CreditTransactionType.chat_inference,
                description=f"Chat inference for job {job_id} ({input_tokens + output_tokens} tokens)"
            )
            db.add(tx)
            # Update wallet
            from api.models.database import CreditWallet
            w_res = await db.execute(select(CreditWallet).where(CreditWallet.user_id == current_user.id))
            wallet = w_res.scalar_one_or_none()
            if wallet:
                wallet.balance = float(wallet.balance) - float(credit_cost)
                
        await db.commit()
        await db.refresh(ai_msg)
        return ai_msg

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
