from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreateRequest(BaseModel):
    lead_id: str
    content: str = Field(min_length=1, max_length=5000)


class NoteResponse(BaseModel):
    id: str
    workspace_id: str
    lead_id: str
    content: str
    created_at: datetime


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    lead_id: str | None = None
    limit: int = Field(default=5, ge=1, le=20)


class MemorySearchItem(BaseModel):
    id: str
    workspace_id: str
    lead_id: str
    source_type: str
    source_id: str
    content: str
    score: float
    created_at: datetime


class MemorySearchResponse(BaseModel):
    items: list[MemorySearchItem]
