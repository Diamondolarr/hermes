from datetime import datetime

from pydantic import BaseModel


class AdminOverviewResponse(BaseModel):
    total_users: int
    total_workspaces: int
    total_leads: int
    total_campaigns: int
    total_sent_emails: int
    total_replies: int
    total_meetings: int
    open_abuse_alerts: int
    api_requests_last_24h: int
    failed_api_requests_last_24h: int


class AdminCampaignMonitorResponse(BaseModel):
    campaign_id: str
    workspace_id: str
    campaign_name: str
    status: str
    emails_sent: int
    emails_replied: int
    reply_rate: float
    meetings_booked: int
    created_at: datetime


class AdminApiUsageSummaryResponse(BaseModel):
    provider: str
    feature: str
    model_name: str | None
    total_requests: int
    failed_requests: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    last_called_at: datetime


class AbuseAlertResponse(BaseModel):
    id: str
    workspace_id: str | None
    alert_type: str
    severity: str
    status: str
    dedupe_key: str
    title: str
    description: str
    metadata: dict
    created_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None
