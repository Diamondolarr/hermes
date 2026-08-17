from datetime import datetime

from pydantic import BaseModel


class GeneratedEmailResponse(BaseModel):
    id: str
    lead_id: str
    campaign_id: str
    subject: str
    body: str
    generated_at: datetime
