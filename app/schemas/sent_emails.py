from datetime import datetime

from pydantic import BaseModel


class SentEmailResponse(BaseModel):
    id: str
    lead_id: str
    campaign_id: str
    message_id: str | None
    sent_at: datetime
    status: str
