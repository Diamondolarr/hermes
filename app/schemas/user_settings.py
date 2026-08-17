from datetime import datetime

from pydantic import BaseModel, Field


class UserSettingsResponse(BaseModel):
    user_id: str
    daily_send_limit: int
    default_email_tone: str
    notifications_enabled: bool
    timezone: str
    created_at: datetime
    updated_at: datetime


class UserSettingsUpdateRequest(BaseModel):
    daily_send_limit: int = Field(ge=1, le=1000)
    default_email_tone: str = Field(min_length=1, max_length=255)
    notifications_enabled: bool
    timezone: str = Field(min_length=1, max_length=64)
