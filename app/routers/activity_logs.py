from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.activity_log import ActivityLog
from app.schemas.activity_logs import ActivityLogResponse
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("", response_model=list[ActivityLogResponse])
def list_activity_logs(
    event_type: str | None = None,
    lead_id: str | None = None,
    campaign_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ActivityLogResponse]:
    _, workspace = current

    query = db.query(ActivityLog).filter(ActivityLog.workspace_id == workspace.id)
    if event_type:
        query = query.filter(ActivityLog.event_type == event_type)
    if lead_id:
        query = query.filter(ActivityLog.lead_id == lead_id)
    if campaign_id:
        query = query.filter(ActivityLog.campaign_id == campaign_id)

    rows = query.order_by(ActivityLog.created_at.desc()).limit(limit).all()
    return [
        ActivityLogResponse(
            id=row.id,
            workspace_id=row.workspace_id,
            lead_id=row.lead_id,
            campaign_id=row.campaign_id,
            event_type=row.event_type,
            message=row.message,
            metadata=row.metadata_json or {},
            created_at=row.created_at,
        )
        for row in rows
    ]
