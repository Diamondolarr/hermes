from typing import Any

from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog

EVENT_EMAIL_GENERATED = "email_generated"
EVENT_EMAIL_SENT = "email_sent"
EVENT_RESEARCH_COMPLETED = "research_completed"
EVENT_REPLY_DETECTED = "reply_detected"


def _normalize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}

    normalized: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            normalized[key] = value
        elif isinstance(value, list):
            normalized[key] = [
                item for item in value if isinstance(item, (str, int, float, bool))
            ]
        else:
            normalized[key] = str(value)
    return normalized


def record_activity_log(
    db: Session,
    *,
    workspace_id: str,
    event_type: str,
    message: str,
    lead_id: str | None = None,
    campaign_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ActivityLog | None:
    try:
        with db.begin_nested():
            entry = ActivityLog(
                workspace_id=workspace_id,
                lead_id=lead_id,
                campaign_id=campaign_id,
                event_type=event_type.strip()[:100],
                message=(message or "").strip()[:1000] or "Activity recorded.",
                metadata_json=_normalize_metadata(metadata),
            )
            db.add(entry)
            db.flush()
        return entry
    except Exception:
        return None
