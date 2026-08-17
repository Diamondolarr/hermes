from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ActivityLogResponse(BaseModel):
    id: str
    workspace_id: str
    lead_id: str | None
    campaign_id: str | None
    event_type: str
    message: str
    metadata: dict[str, Any]
    created_at: datetime
