from datetime import datetime

from pydantic import BaseModel


class FollowupResponse(BaseModel):
    id: str
    lead_id: str
    campaign_id: str
    step_number: int
    email_subject: str
    email_body: str
    scheduled_date: datetime


class FollowupSequenceResponse(BaseModel):
    lead_id: str
    campaign_id: str
    items: list[FollowupResponse]
