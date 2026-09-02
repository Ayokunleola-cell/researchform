# backend/api/routers/auth_social.py
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from authlib.integrations.starlette_client import OAuth, OAuthError
import uuid
import secrets

from api.deps import get_db
from api.models.database import User, UserIntegration, UserRole
from api.routers.auth import make_token, hash_pw
from config import settings

router = APIRouter()
oauth = OAuth()

if settings.GOOGLE_CLIENT_ID:
    oauth.register(
        name='google',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

if settings.FACEBOOK_CLIENT_ID:
    oauth.register(
        name='facebook',
        client_id=settings.FACEBOOK_CLIENT_ID,
        client_secret=settings.FACEBOOK_CLIENT_SECRET,
        api_base_url='https://graph.facebook.com/v16.0/',
        access_token_url='https://graph.facebook.com/v16.0/oauth/access_token',
        authorize_url='https://www.facebook.com/v16.0/dialog/oauth',
        client_kwargs={'scope': 'email public_profile'}
    )

@router.get("/{provider}/login")
async def login_social(provider: str, request: Request):
    client = oauth.create_client(provider)
    if not client:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=provider_not_configured")
    
    redirect_uri = str(request.url_for('callback_social', provider=provider))
    return await client.authorize_redirect(request, redirect_uri)

@router.get("/{provider}/callback")
async def callback_social(provider: str, request: Request, db: AsyncSession = Depends(get_db)):
    client = oauth.create_client(provider)
    if not client:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=provider_not_configured")
        
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as e:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=oauth_failed")

    # Fetch user info
    if provider == 'google':
        user_info = token.get('userinfo')
        if not user_info:
            user_info = await client.userinfo(token=token)
        email = user_info.get('email')
        name = user_info.get('name', 'Google User')
    elif provider == 'facebook':
        resp = await client.get('me?fields=id,name,email', token=token)
        user_info = resp.json()
        email = user_info.get('email')
        name = user_info.get('name', 'Facebook User')
    else:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=provider_not_supported")
    
    if not email:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=no_email")

    # Find or create user
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            full_name=name,
            role=UserRole.student,
            hashed_password=hash_pw(secrets.token_urlsafe(32)),
            is_verified=True,
        )
        db.add(user)
        # give signup bonus
        from decimal import Decimal
        from api.models.database import CreditWallet, CreditTransaction, CreditTransactionType
        bonus = Decimal(str(settings.SIGNUP_BONUS_CREDITS))
        if bonus > 0:
            wallet = CreditWallet(user_id=user.id, balance=bonus)
            db.add(wallet)
            db.add(
                CreditTransaction(
                    user_id=user.id,
                    amount=bonus,
                    type=CreditTransactionType.signup_bonus,
                    description=f"Welcome bonus — {bonus} analysis credits",
                    balance_after=bonus,
                    extra={"source": "social_registration"},
                )
            )
        await db.flush()
    
    # Store integration token
    res_integ = await db.execute(select(UserIntegration).where(
        UserIntegration.user_id == user.id,
        UserIntegration.provider == provider
    ))
    integ = res_integ.scalar_one_or_none()
    if not integ:
        integ = UserIntegration(
            user_id=user.id,
            provider=provider,
            account_email=email,
            access_token=token.get('access_token'),
            refresh_token=token.get('refresh_token')
        )
        db.add(integ)
    else:
        integ.access_token = token.get('access_token')
        if token.get('refresh_token'):
            integ.refresh_token = token.get('refresh_token')

    await db.commit()
    await db.refresh(user)
    
    access_token = make_token(user)
    # Redirect to frontend callback page to save token and user info
    user_json_encoded = f"%7B%22full_name%22%3A%22{name.replace(' ', '%20')}%22%2C%22email%22%3A%22{email}%22%7D"
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback?token={access_token}&user={user_json_encoded}")
