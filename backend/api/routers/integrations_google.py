"""
Google Drive & Sheets Integration Router
Handles OAuth flow and exporting/importing data from Google Workspace.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import os
import json
import csv

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from api.deps import get_db, get_current_user
from api.models.database import User, UserIntegration, Survey, Response, Dataset
from config import settings

router = APIRouter()

# Scopes needed for Drive and Sheets
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/spreadsheets'
]

# We will need these environment variables later:
# GOOGLE_CLIENT_ID
# GOOGLE_CLIENT_SECRET
# GOOGLE_REDIRECT_URI

def get_google_flow():
    # Helper to get the OAuth flow.
    # We create a dummy client_secrets JSON if env vars aren't fully set yet,
    # so the app doesn't crash on startup. In production, provide a real client_secrets.json
    # or pass directly.
    client_config = {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", "dummy_client_id"),
            "project_id": "researchform",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "dummy_client_secret"),
            "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/settings/integrations")]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=client_config["web"]["redirect_uris"][0]
    )
    return flow

@router.get("/auth-url")
async def get_google_auth_url():
    """Returns the URL to redirect the user to Google for OAuth."""
    flow = get_google_flow()
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    return {"auth_url": auth_url}

@router.post("/callback")
async def google_callback(
    code: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Exchanges the authorization code for tokens and saves to DB."""
    flow = get_google_flow()
    try:
        flow.fetch_token(code=code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch token: {str(e)}")
        
    credentials = flow.credentials
    
    # Get user email
    user_info_service = build('oauth2', 'v2', credentials=credentials)
    user_info = user_info_service.userinfo().get().execute()
    email = user_info.get("email", "")

    # Check if integration already exists
    res = await db.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == current_user.id,
            UserIntegration.provider == "google"
        )
    )
    integration = res.scalar_one_or_none()
    
    if integration:
        integration.access_token = credentials.token
        if credentials.refresh_token:
            integration.refresh_token = credentials.refresh_token
        integration.token_expiry = credentials.expiry
        integration.account_email = email
    else:
        integration = UserIntegration(
            user_id=current_user.id,
            provider="google",
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_expiry=credentials.expiry,
            account_email=email
        )
        db.add(integration)
        
    await db.commit()
    return {"status": "success", "email": email}

@router.get("/status")
async def get_google_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == current_user.id,
            UserIntegration.provider == "google"
        )
    )
    integration = res.scalar_one_or_none()
    if integration:
        return {"connected": True, "email": integration.account_email}
    return {"connected": False}

async def get_valid_credentials(integration: UserIntegration, db: AsyncSession) -> Credentials:
    creds = Credentials(
        token=integration.access_token,
        refresh_token=integration.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID", "dummy_client_id"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET", "dummy_client_secret")
    )
    
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        integration.access_token = creds.token
        integration.token_expiry = creds.expiry
        await db.commit()
        
    return creds

@router.post("/export-drive")
async def export_to_drive(
    resource_type: str = Body(...),
    resource_id: str = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(UserIntegration).where(UserIntegration.user_id == current_user.id, UserIntegration.provider == "google"))
    integration = res.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=401, detail="Google account not connected")
        
    creds = await get_valid_credentials(integration, db)
    service = build('drive', 'v3', credentials=creds)
    
    if resource_type == "dataset":
        res = await db.execute(select(Dataset).where(Dataset.id == resource_id))
        dataset = res.scalar_one_or_none()
        if not dataset or not dataset.primary_file_path:
            raise HTTPException(status_code=404, detail="Dataset not found")
            
        file_metadata = {'name': f'{dataset.title}.csv'}
        media = MediaFileUpload(dataset.primary_file_path, mimetype='text/csv')
        
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return {"status": "success", "file_id": file.get('id')}
        
    if resource_type == "survey":
        res = await db.execute(select(Survey).where(Survey.id == resource_id))
        survey = res.scalar_one_or_none()
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")
            
        res_resp = await db.execute(select(Response).where(Response.survey_id == survey.id))
        responses = res_resp.scalars().all()
        
        import tempfile
        import uuid
        filename = f"Survey_{survey.id[:8]}_Export_{uuid.uuid4().hex[:4]}.csv"
        filepath = os.path.join(tempfile.gettempdir(), filename)
        
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if responses:
                first_data = responses[0].data if isinstance(responses[0].data, dict) else json.loads(responses[0].data)
                headers = ["Response ID", "Submitted At"] + list(first_data.keys())
                writer.writerow(headers)
                
                for r in responses:
                    row_data = r.data if isinstance(r.data, dict) else json.loads(r.data)
                    row = [r.id, r.submitted_at.isoformat()]
                    for h in headers[2:]:
                        row.append(str(row_data.get(h, "")))
                    writer.writerow(row)
            else:
                writer.writerow(["No responses yet"])
                
        file_metadata = {'name': f'{survey.title}.csv'}
        media = MediaFileUpload(filepath, mimetype='text/csv')
        
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        
        try:
            os.remove(filepath)
        except:
            pass
            
        return {"status": "success", "file_id": file.get('id')}
    
    raise HTTPException(status_code=400, detail="Unsupported resource type")

@router.post("/export-sheets")
async def export_to_sheets(
    resource_type: str = Body(...),
    resource_id: str = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(UserIntegration).where(UserIntegration.user_id == current_user.id, UserIntegration.provider == "google"))
    integration = res.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=401, detail="Google account not connected")
        
    creds = await get_valid_credentials(integration, db)
    service = build('sheets', 'v4', credentials=creds)
    
    if resource_type == "survey":
        res_survey = await db.execute(select(Survey).where(Survey.id == resource_id))
        survey = res_survey.scalar_one_or_none()
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")
            
        res_responses = await db.execute(select(Response).where(Response.survey_id == survey.id))
        responses = res_responses.scalars().all()
        
        # Prepare data
        values = []
        if responses:
            first_data = responses[0].data if isinstance(responses[0].data, dict) else json.loads(responses[0].data)
            headers = ["Response ID", "Submitted At"] + list(first_data.keys())
            values.append(headers)
            
            for r in responses:
                row_data = r.data if isinstance(r.data, dict) else json.loads(r.data)
                row = [r.id, r.submitted_at.isoformat()]
                for h in headers[2:]:
                    row.append(str(row_data.get(h, "")))
                values.append(row)
        else:
            values.append(["No responses yet"])
            
        spreadsheet = {
            'properties': {'title': f'Survey: {survey.title}'}
        }
        spreadsheet = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
        spreadsheet_id = spreadsheet.get('spreadsheetId')
        
        body = {'values': values}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range='Sheet1!A1',
            valueInputOption='RAW', body=body).execute()
            
        return {"status": "success", "spreadsheet_id": spreadsheet_id, "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"}
        
    raise HTTPException(status_code=400, detail="Unsupported resource type")

@router.post("/import-sheets")
async def import_from_sheets(
    spreadsheet_url: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(UserIntegration).where(UserIntegration.user_id == current_user.id, UserIntegration.provider == "google"))
    integration = res.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=401, detail="Google account not connected")
        
    creds = await get_valid_credentials(integration, db)
    service = build('sheets', 'v4', credentials=creds)
    
    # Extract spreadsheet ID from URL (e.g. https://docs.google.com/spreadsheets/d/ID/edit)
    import re
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", spreadsheet_url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid Google Sheets URL")
    spreadsheet_id = match.group(1)
    
    try:
        # Get first sheet's name
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get('sheets', '')
        title = sheets[0].get("properties", {}).get("title", "Sheet1")
        
        # Read data
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=title).execute()
        values = result.get('values', [])
        
        if not values:
            raise HTTPException(status_code=400, detail="Sheet is empty")
            
        # Save as a temporary local CSV
        import tempfile
        import uuid
        filename = f"imported_sheet_{uuid.uuid4().hex[:8]}.csv"
        filepath = os.path.join("storage", "dataframes", filename)
        
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(values)
            
        return {"status": "success", "file_path": filepath, "filename": filename, "rows_imported": len(values)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import sheet: {str(e)}")
