from datetime import datetime

from pydantic import BaseModel


class ScheduledEmailResponse(BaseModel):
    id: str
    lead_id: str
    campaign_id: str
    step_number: int
    email_type: str
    scheduled_for: datetime
    status: str
    approval_status: str
    created_at: datetime


class ScheduledSequenceResponse(BaseModel):
    lead_id: str
    campaign_id: str
    items: list[ScheduledEmailResponse]
