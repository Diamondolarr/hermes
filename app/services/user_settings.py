from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_setting import UserSetting
from app.services.email_scheduling import validate_send_timezone

DEFAULT_DAILY_SEND_LIMIT = 50
DEFAULT_EMAIL_TONE = "consultative"
DEFAULT_NOTIFICATIONS_ENABLED = True
DEFAULT_TIMEZONE = "UTC"


def get_or_create_user_settings(db: Session, user: User) -> UserSetting:
    settings = db.query(UserSetting).filter(UserSetting.user_id == user.id).first()
    if settings:
        return settings

    settings = UserSetting(
        user_id=user.id,
        daily_send_limit=DEFAULT_DAILY_SEND_LIMIT,
        default_email_tone=DEFAULT_EMAIL_TONE,
        notifications_enabled=DEFAULT_NOTIFICATIONS_ENABLED,
        timezone=DEFAULT_TIMEZONE,
    )
    db.add(settings)
    db.flush()
    return settings


def normalize_user_timezone(value: str) -> str:
    return validate_send_timezone(value)
