from datetime import datetime

from pydantic import BaseModel


class LeadImportError(BaseModel):
    row_number: int
    message: str


class LeadImportResponse(BaseModel):
    total_rows: int
    inserted: int
    updated: int
    skipped: int
    errors: list[LeadImportError]


class LeadListItem(BaseModel):
    id: str
    name: str
    email: str
    company: str
    role: str
    status: str
    research_state: str
    last_activity_at: datetime
    created_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadListItem]
    total: int
