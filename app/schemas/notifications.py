from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    channel: str
    title: str
    body: str
    status: str
    resource_type: str | None
    resource_id: str | None
    metadata_json: dict
    created_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None


class NotificationListItem(BaseModel):
    id: str
    event_type: str
    channel: str
    title: str
    body: str
    status: str
    resource_type: str | None
    resource_id: str | None
    metadata: dict
    created_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None


class NotificationMarkReadResponse(NotificationListItem):
    pass
