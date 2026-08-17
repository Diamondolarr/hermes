from datetime import datetime, timedelta
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.token import EmailVerificationToken, PasswordResetToken, UserSession
from app.models.onboarding import CompanyProfile
from app.models.user import User
from app.models.workspace import Workspace
from app.models.user_setting import UserSetting
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)
from app.services.admin_monitoring import (
    PROVIDER_INTERNAL,
    record_api_usage,
    record_api_usage_event,
)
from app.services.email import send_email
from app.utils.jwt import create_access_token
from app.utils.rate_limit import rate_limit
from app.utils.security import hash_password, verify_and_update_password
from app.utils.tokens import expires_in_hours, generate_token, hash_token

router = APIRouter()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _client_ip(request: Request) -> Optional[str]:
    if request.client:
        return request.client.host
    return None


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[rate_limit(3, 60)],
)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    email = _normalize_email(payload.email)
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")

    user_id = str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())

    workspace = Workspace(
        id=workspace_id,
        user_id=user_id,
    )

    company_profile = CompanyProfile(
        workspace_id=workspace_id,
        company_name=payload.company_name,
        company_website=payload.company_website,
        product_description=payload.product_description,
        industry=payload.industry,
        target_market=payload.target_market,
    )

    user = User(
        id=user_id,
        name=payload.name,
        email=email,
        password_hash=hash_password(payload.password),
        workspace_id=workspace_id,
        is_verified=False,
    )

    verification_token = generate_token()
    verification_token_hash = hash_token(verification_token)
    verification_expires_at = expires_in_hours(settings.verify_token_expire_hours)

    db.add(workspace)
    db.add(user)
    db.add(company_profile)
    db.add(
        UserSetting(
            user_id=user_id,
        )
    )
    db.flush()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=verification_token_hash,
            expires_at=verification_expires_at,
        )
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered.")

    verification_link = (
        f"{settings.frontend_app_url}/verify-email?token={verification_token}"
    )
    send_email(
        to_email=user.email,
        subject="Verify your email",
        body=(
            f"Hi {user.name},\n\n"
            "Please verify your email by clicking the link below:\n"
            f"{verification_link}\n\n"
            "If you did not create this account, you can ignore this email."
        ),
    )

    return SignupResponse(
        message="Verification email sent.",
        workspace_id=workspace_id,
        onboarding_completed=False,
        next_step="ideal_customer_profile",
    )


@router.get(
    "/verify-email",
    response_model=MessageResponse,
    dependencies=[rate_limit(10, 900)],
)
def verify_email(token: str, db: Session = Depends(get_db)) -> MessageResponse:
    token_hash_value = hash_token(token)
    token_row = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token_hash == token_hash_value,
            EmailVerificationToken.used_at.is_(None),
        )
        .first()
    )

    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")

    if token_row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired token.")

    token_row.used_at = datetime.utcnow()
    token_row.user.is_verified = True
    db.commit()

    return MessageResponse(message="Email verified successfully.")


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[rate_limit(5, 60)],
)
def login(
    payload: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    email = _normalize_email(payload.email)
    ip_address = _client_ip(request)
    user = db.query(User).filter(User.email == email).first()

    if not user:
        record_api_usage_event(
            workspace_id=None,
            provider=PROVIDER_INTERNAL,
            feature="auth_login",
            success=False,
            metadata={
                "email": email,
                "ip_address": ip_address,
                "reason": "unknown_user",
            },
        )
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    is_valid, updated_hash = verify_and_update_password(
        payload.password, user.password_hash
    )
    if not is_valid:
        record_api_usage_event(
            workspace_id=user.workspace_id,
            provider=PROVIDER_INTERNAL,
            feature="auth_login",
            success=False,
            metadata={
                "email": email,
                "ip_address": ip_address,
                "reason": "invalid_password",
            },
        )
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if updated_hash:
        user.password_hash = updated_hash

    if not user.is_verified:
        record_api_usage_event(
            workspace_id=user.workspace_id,
            provider=PROVIDER_INTERNAL,
            feature="auth_login",
            success=False,
            metadata={
                "email": email,
                "ip_address": ip_address,
                "reason": "email_not_verified",
            },
        )
        raise HTTPException(status_code=403, detail="Email not verified.")

    expires_at = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    jti = str(uuid.uuid4())
    access_token = create_access_token(
        subject=user.id,
        jti=jti,
        expires_at=expires_at,
        workspace_id=user.workspace_id,
    )

    session = UserSession(
        user_id=user.id,
        jti=jti,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    record_api_usage(
        db,
        workspace_id=user.workspace_id,
        provider=PROVIDER_INTERNAL,
        feature="auth_login",
        success=True,
        metadata={
            "email": email,
            "ip_address": ip_address,
        },
    )
    db.commit()

    return TokenResponse(
        access_token=access_token, token_type="bearer", expires_at=expires_at
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    dependencies=[rate_limit(3, 900)],
)
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    email = _normalize_email(payload.email)
    user = db.query(User).filter(User.email == email).first()

    if user:
        reset_token = generate_token()
        reset_token_hash = hash_token(reset_token)
        reset_expires_at = expires_in_hours(settings.reset_token_expire_hours)

        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=reset_token_hash,
                expires_at=reset_expires_at,
            )
        )
        db.commit()

        reset_link = f"{settings.frontend_app_url}/reset-password?token={reset_token}"
        send_email(
            to_email=user.email,
            subject="Reset your password",
            body=(
                f"Hi {user.name},\n\n"
                "You requested a password reset. Use the link below to set a new password:\n"
                f"{reset_link}\n\n"
                "If you did not request a reset, you can ignore this email."
            ),
        )

    return MessageResponse(message="If the email exists, a reset link has been sent.")


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=[rate_limit(5, 900)],
)
def reset_password(
    payload: ResetPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    token_hash_value = hash_token(payload.token)
    token_row = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash_value,
            PasswordResetToken.used_at.is_(None),
        )
        .first()
    )

    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")

    if token_row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired token.")

    now = datetime.utcnow()
    token_row.used_at = now
    token_row.user.password_hash = hash_password(payload.new_password)
    for session in token_row.user.sessions:
        if session.revoked_at is None and session.expires_at >= now:
            session.revoked_at = now
    db.commit()

    return MessageResponse(message="Password updated successfully.")
