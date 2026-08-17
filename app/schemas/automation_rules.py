from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TriggerType = Literal["NO_REPLY_AFTER_DAYS"]
ActionType = Literal["SEND_FOLLOWUP"]


class AutomationRuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    campaign_id: str | None = None
    trigger_type: TriggerType = "NO_REPLY_AFTER_DAYS"
    delay_days: int = Field(ge=1, le=365)
    action_type: ActionType = "SEND_FOLLOWUP"
    is_active: bool = True


class AutomationRuleResponse(BaseModel):
    id: str
    workspace_id: str
    campaign_id: str | None
    name: str
    trigger_type: TriggerType
    delay_days: int
    action_type: ActionType
    is_active: bool
    created_at: datetime


class AutomationRuleExecutionSummary(BaseModel):
    rules_evaluated: int
    leads_considered: int
    actions_scheduled: int
    skipped_existing_schedule: int
    skipped_due_to_reply: int
    skipped_no_followup_available: int
    execution_failures: int
