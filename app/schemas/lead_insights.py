from datetime import datetime

from pydantic import BaseModel


class LeadInsightResponse(BaseModel):
    id: str
    lead_id: str
    role_category: str
    possible_pain_points: list[str]
    recommended_sales_angle: str
    confidence_score: float
    created_at: datetime
    updated_at: datetime
