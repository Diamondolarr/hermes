from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user_settings import UserSettingsResponse, UserSettingsUpdateRequest
from app.services.user_settings import get_or_create_user_settings, normalize_user_timezone
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("", response_model=UserSettingsResponse)
def get_user_settings(
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettingsResponse:
    user, _ = current
    settings = get_or_create_user_settings(db, user)
    db.commit()
    db.refresh(settings)
    return UserSettingsResponse(
        user_id=settings.user_id,
        daily_send_limit=settings.daily_send_limit,
        default_email_tone=settings.default_email_tone,
        notifications_enabled=settings.notifications_enabled,
        timezone=settings.timezone,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


@router.put("", response_model=UserSettingsResponse)
def update_user_settings(
    payload: UserSettingsUpdateRequest,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettingsResponse:
    user, _ = current
    settings = get_or_create_user_settings(db, user)
    settings.daily_send_limit = payload.daily_send_limit
    settings.default_email_tone = payload.default_email_tone.strip()
    settings.notifications_enabled = payload.notifications_enabled
    settings.timezone = normalize_user_timezone(payload.timezone.strip())
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return UserSettingsResponse(
        user_id=settings.user_id,
        daily_send_limit=settings.daily_send_limit,
        default_email_tone=settings.default_email_tone,
        notifications_enabled=settings.notifications_enabled,
        timezone=settings.timezone,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )
