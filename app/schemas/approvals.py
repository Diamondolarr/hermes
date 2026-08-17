from datetime import datetime

from pydantic import BaseModel, Field


class HumanApprovalSettingsRequest(BaseModel):
    human_approval_enabled: bool


class HumanApprovalSettingsResponse(BaseModel):
    human_approval_enabled: bool


class ApprovalDecisionRequest(BaseModel):
    rejection_reason: str | None = Field(default=None, max_length=1000)


class PendingApprovalItemResponse(BaseModel):
    scheduled_email_id: str
    lead_id: str
    lead_name: str
    lead_email: str
    campaign_id: str
    campaign_name: str
    step_number: int
    email_type: str
    subject: str
    body: str
    scheduled_for: datetime
    status: str
    approval_status: str
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None


class EmailDispatchResponse(BaseModel):
    lead_id: str
    campaign_id: str
    status: str
    message: str
    sent_email_id: str | None = None
    scheduled_email_id: str | None = None
    message_id: str | None = None
    sent_at: datetime | None = None
    approval_status: str | None = None
