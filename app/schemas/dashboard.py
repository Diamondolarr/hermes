from datetime import datetime

from pydantic import BaseModel


class DashboardRecentReplyItem(BaseModel):
    id: str
    lead_id: str
    lead_name: str
    company: str
    category: str | None
    preview: str
    received_at: datetime


class DashboardPendingApprovalItem(BaseModel):
    scheduled_email_id: str
    lead_id: str
    lead_name: str
    campaign_id: str
    campaign_name: str
    scheduled_for: datetime
    step_number: int


class DashboardCampaignSnapshotItem(BaseModel):
    campaign_id: str
    name: str
    status: str
    emails_sent: int
    replies: int
    reply_rate: float


class DashboardNotificationPreviewItem(BaseModel):
    id: str
    event_type: str
    title: str
    body: str
    created_at: datetime


class DashboardActivityItem(BaseModel):
    id: str
    event_type: str
    message: str
    created_at: datetime


class DashboardSummaryResponse(BaseModel):
    leads: int
    active_campaigns: int
    emails_sent: int
    replies: int
    meetings: int
    pending_approvals_count: int
    unread_notifications_count: int
    connected_email_accounts: int
    recent_replies: list[DashboardRecentReplyItem]
    pending_approvals: list[DashboardPendingApprovalItem]
    active_campaigns_snapshot: list[DashboardCampaignSnapshotItem]
    notifications_preview: list[DashboardNotificationPreviewItem]
    recent_activity: list[DashboardActivityItem]
