from datetime import datetime

from pydantic import BaseModel


class SalesInsightResponse(BaseModel):
    id: str
    lead_id: str
    sales_angle: str
    value_proposition: str
    personalization_notes: str
    created_at: datetime
    updated_at: datetime
