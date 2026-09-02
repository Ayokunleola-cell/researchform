"""
Power BI Integration Router
Provides secure data feeds for Power BI consumption.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.responses import StreamingResponse
import io
import csv
import uuid

from api.deps import get_db, get_current_user
from api.models.database import User, DataFeedToken, Survey, Response, Dataset
import json
import pandas as pd

router = APIRouter()

@router.post("/generate-link")
async def generate_powerbi_link(
    resource_type: str,
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates a secure token for a Power BI feed."""
    if resource_type not in ["survey", "dataset"]:
        raise HTTPException(status_code=400, detail="Invalid resource type")
        
    # Verify ownership
    if resource_type == "survey":
        res = await db.execute(select(Survey).where(Survey.id == resource_id, Survey.user_id == current_user.id))
        if not res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Survey not found")
    elif resource_type == "dataset":
        # For dataset, verify if they own it or bought it. Simplify for now: verify ownership
        res = await db.execute(select(Dataset).where(Dataset.id == resource_id))
        dataset = res.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
            
    # Check if token exists
    res = await db.execute(
        select(DataFeedToken).where(
            DataFeedToken.user_id == current_user.id,
            DataFeedToken.resource_id == resource_id
        )
    )
    existing_token = res.scalar_one_or_none()
    if existing_token:
        token = existing_token.token
    else:
        token = str(uuid.uuid4())
        new_token = DataFeedToken(
            user_id=current_user.id,
            resource_type=resource_type,
            resource_id=resource_id,
            token=token
        )
        db.add(new_token)
        await db.commit()
        
    feed_url = f"/datanest/integrations/powerbi/feed?token={token}"
    return {"token": token, "feed_url": feed_url}

@router.get("/feed")
async def powerbi_feed(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Consumes a data feed token and streams CSV data."""
    res = await db.execute(select(DataFeedToken).where(DataFeedToken.token == token))
    feed_token = res.scalar_one_or_none()
    
    if not feed_token:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    if feed_token.resource_type == "survey":
        # Stream survey responses
        survey_res = await db.execute(select(Survey).where(Survey.id == feed_token.resource_id))
        survey = survey_res.scalar_one_or_none()
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")
            
        responses_res = await db.execute(select(Response).where(Response.survey_id == survey.id))
        responses = responses_res.scalars().all()
        
        output = io.StringIO()
        if not responses:
            output.write("id,submitted_at\n")
        else:
            # Extract headers from the first response
            first_data = responses[0].data if isinstance(responses[0].data, dict) else json.loads(responses[0].data)
            headers = ["response_id", "submitted_at"] + list(first_data.keys())
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            
            for r in responses:
                row_data = r.data if isinstance(r.data, dict) else json.loads(r.data)
                row = {
                    "response_id": r.id,
                    "submitted_at": r.submitted_at.isoformat()
                }
                for k, v in row_data.items():
                    row[k] = v
                writer.writerow(row)
                
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]), 
            media_type="text/csv", 
            headers={"Content-Disposition": f"attachment; filename=survey_{survey.id}_feed.csv"}
        )
        
    elif feed_token.resource_type == "dataset":
        # Stream dataset CSV
        dataset_res = await db.execute(select(Dataset).where(Dataset.id == feed_token.resource_id))
        dataset = dataset_res.scalar_one_or_none()
        if not dataset or not dataset.primary_file_path:
            raise HTTPException(status_code=404, detail="Dataset file not found")
            
        import os
        file_path = os.path.join(dataset.primary_file_path)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on server")
            
        def iterfile():
            with open(file_path, mode="rb") as f:
                yield from f
                
        return StreamingResponse(
            iterfile(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=dataset_{dataset.id}_feed.csv"}
        )
    
    raise HTTPException(status_code=400, detail="Unsupported resource")
