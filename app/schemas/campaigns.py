from datetime import datetime

from pydantic import BaseModel, Field


class CampaignCreateRequest(BaseModel):
    campaign_name: str = Field(min_length=1, max_length=255)
    target_icp: str = Field(min_length=1, max_length=255)
    message_tone: str | None = Field(default=None, min_length=1, max_length=255)
    cta_type: str = Field(min_length=1, max_length=255)
    daily_send_limit: int | None = Field(default=None, ge=1, le=1000)
    send_time_window: str = Field(
        min_length=11,
        max_length=11,
        description="Send window in HH:MM-HH:MM format.",
    )
    send_timezone: str | None = Field(default=None, min_length=1, max_length=64)
    followup_delay_days: int = Field(ge=1, le=365)


class CampaignResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    target_icp: str
    message_tone: str
    cta_type: str
    daily_send_limit: int
    send_time_window: str
    send_timezone: str
    followup_delay_days: int
    status: str
    created_at: datetime


class CampaignAnalyticsResponse(BaseModel):
    campaign_id: str
    campaign_name: str
    status: str
    emails_sent: int
    emails_replied: int
    reply_rate: float
    meetings_booked: int
    conversion_rate: float
    ai_summary: str
    ai_recommendations: list[str]


class CampaignInsightResponse(BaseModel):
    id: str
    campaign_id: str
    best_subject_line: str
    best_send_time: str
    best_industry_response: str
    summary: str
    recommendations: list[str]
    generated_at: datetime
