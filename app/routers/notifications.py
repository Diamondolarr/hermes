from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.notification import Notification
from app.schemas.notifications import (
    NotificationListItem,
    NotificationMarkReadResponse,
)
from app.utils.auth import get_current_user

router = APIRouter()


def _to_notification_item(notification: Notification) -> NotificationListItem:
    return NotificationListItem(
        id=notification.id,
        event_type=notification.event_type,
        channel=notification.channel,
        title=notification.title,
        body=notification.body,
        status=notification.status,
        resource_type=notification.resource_type,
        resource_id=notification.resource_id,
        metadata=notification.metadata_json or {},
        created_at=notification.created_at,
        delivered_at=notification.delivered_at,
        read_at=notification.read_at,
    )


@router.get("", response_model=list[NotificationListItem])
def list_notifications(
    channel: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationListItem]:
    user, workspace = current

    query = db.query(Notification).filter(
        Notification.workspace_id == workspace.id,
        Notification.user_id == user.id,
    )
    if channel:
        query = query.filter(Notification.channel == channel)
    if event_type:
        query = query.filter(Notification.event_type == event_type)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))

    rows = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .all()
    )
    return [_to_notification_item(row) for row in rows]


@router.post("/{notification_id}/read", response_model=NotificationMarkReadResponse)
def mark_notification_read(
    notification_id: str,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationMarkReadResponse:
    user, workspace = current

    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.workspace_id == workspace.id,
            Notification.user_id == user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")

    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)

    return NotificationMarkReadResponse(**_to_notification_item(notification).model_dump())
