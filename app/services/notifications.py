from datetime import datetime

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.meeting import Meeting
from app.models.notification import Notification
from app.models.scheduled_email import ScheduledEmail
from app.models.user import User
from app.services.email import send_email
from app.services.user_settings import get_or_create_user_settings

EVENT_NEW_REPLY = "new_reply"
EVENT_MEETING_SCHEDULED = "meeting_scheduled"
EVENT_CAMPAIGN_FINISHED = "campaign_finished"
EVENT_SYSTEM_ERROR = "system_error"

CHANNEL_DASHBOARD = "dashboard"
CHANNEL_EMAIL = "email"

STATUS_DELIVERED = "DELIVERED"
STATUS_FAILED = "FAILED"

_ACTIVE_CAMPAIGN_SCHEDULE_STATUSES = {"PENDING", "QUEUED"}


def _normalize_metadata(value: dict | None) -> dict:
    if not value:
        return {}

    normalized: dict[str, str | int | float | bool | None | list | dict] = {}
    for key, item in value.items():
        normalized[str(key)] = item
    return normalized


def _get_workspace_users(db: Session, workspace_id: str) -> list[User]:
    return (
        db.query(User)
        .filter(User.workspace_id == workspace_id)
        .order_by(User.created_at.asc())
        .all()
    )


def _find_existing_notification(
    db: Session,
    *,
    user_id: str,
    channel: str,
    event_type: str,
    resource_type: str | None,
    resource_id: str | None,
) -> Notification | None:
    if not resource_type or not resource_id:
        return None

    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.channel == channel,
            Notification.event_type == event_type,
            Notification.resource_type == resource_type,
            Notification.resource_id == resource_id,
        )
        .first()
    )


def _build_notification(
    *,
    workspace_id: str,
    user_id: str,
    event_type: str,
    channel: str,
    title: str,
    body: str,
    status: str,
    resource_type: str | None,
    resource_id: str | None,
    metadata: dict | None,
    delivered: bool,
) -> Notification:
    delivered_at = datetime.utcnow() if delivered else None
    return Notification(
        workspace_id=workspace_id,
        user_id=user_id,
        event_type=event_type,
        channel=channel,
        title=title,
        body=body,
        status=status,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=_normalize_metadata(metadata),
        delivered_at=delivered_at,
    )


def _ensure_dashboard_notification(
    db: Session,
    *,
    workspace_id: str,
    user: User,
    event_type: str,
    title: str,
    body: str,
    metadata: dict | None,
    resource_type: str | None,
    resource_id: str | None,
) -> None:
    existing = _find_existing_notification(
        db,
        user_id=user.id,
        channel=CHANNEL_DASHBOARD,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    if existing:
        return

    notification = _build_notification(
        workspace_id=workspace_id,
        user_id=user.id,
        event_type=event_type,
        channel=CHANNEL_DASHBOARD,
        title=title,
        body=body,
        status=STATUS_DELIVERED,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=metadata,
        delivered=True,
    )
    db.add(notification)
    db.flush()


def _ensure_email_notification(
    db: Session,
    *,
    workspace_id: str,
    user: User,
    event_type: str,
    title: str,
    body: str,
    metadata: dict | None,
    resource_type: str | None,
    resource_id: str | None,
) -> None:
    settings = get_or_create_user_settings(db, user)
    if not settings.notifications_enabled:
        return

    existing = _find_existing_notification(
        db,
        user_id=user.id,
        channel=CHANNEL_EMAIL,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    if existing:
        return

    notification = _build_notification(
        workspace_id=workspace_id,
        user_id=user.id,
        event_type=event_type,
        channel=CHANNEL_EMAIL,
        title=title,
        body=body,
        status=STATUS_DELIVERED,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=metadata,
        delivered=True,
    )
    db.add(notification)
    db.flush()

    try:
        send_email(
            to_email=user.email,
            subject=title,
            body=body,
            sender="AI SDR Notifications",
        )
    except Exception as exc:
        notification.status = STATUS_FAILED
        notification.delivered_at = None
        notification.metadata_json = {
            **notification.metadata_json,
            "delivery_error": str(exc),
        }
        db.flush()


def emit_workspace_notification(
    db: Session,
    *,
    workspace_id: str,
    event_type: str,
    title: str,
    body: str,
    metadata: dict | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> None:
    users = _get_workspace_users(db, workspace_id)
    if not users:
        return

    try:
        with db.begin_nested():
            for user in users:
                _ensure_dashboard_notification(
                    db,
                    workspace_id=workspace_id,
                    user=user,
                    event_type=event_type,
                    title=title,
                    body=body,
                    metadata=metadata,
                    resource_type=resource_type,
                    resource_id=resource_id,
                )
                _ensure_email_notification(
                    db,
                    workspace_id=workspace_id,
                    user=user,
                    event_type=event_type,
                    title=title,
                    body=body,
                    metadata=metadata,
                    resource_type=resource_type,
                    resource_id=resource_id,
                )
    except Exception:
        return


def notify_new_reply(
    db: Session,
    *,
    workspace_id: str,
    lead_id: str,
    lead_name: str,
    lead_email: str,
    reply_id: str,
    message_id: str,
    thread_id: str | None,
    reply_body: str,
) -> None:
    excerpt = reply_body.strip()
    if len(excerpt) > 220:
        excerpt = f"{excerpt[:217].rstrip()}..."

    emit_workspace_notification(
        db,
        workspace_id=workspace_id,
        event_type=EVENT_NEW_REPLY,
        title=f"New reply from {lead_name or lead_email}",
        body=f"{lead_name or lead_email} replied: {excerpt}",
        metadata={
            "lead_id": lead_id,
            "reply_id": reply_id,
            "message_id": message_id,
            "thread_id": thread_id,
            "lead_email": lead_email,
        },
        resource_type="email_reply",
        resource_id=reply_id,
    )


def notify_system_error(
    db: Session,
    *,
    workspace_id: str,
    title: str,
    body: str,
    metadata: dict | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> None:
    emit_workspace_notification(
        db,
        workspace_id=workspace_id,
        event_type=EVENT_SYSTEM_ERROR,
        title=title,
        body=body,
        metadata=metadata,
        resource_type=resource_type,
        resource_id=resource_id,
    )


def _campaign_is_finished(db: Session, campaign: Campaign) -> bool:
    has_any_schedule = (
        db.query(ScheduledEmail.id)
        .filter(ScheduledEmail.campaign_id == campaign.id)
        .first()
        is not None
    )
    if not has_any_schedule:
        return False

    has_active = (
        db.query(ScheduledEmail.id)
        .filter(
            ScheduledEmail.campaign_id == campaign.id,
            ScheduledEmail.status.in_(_ACTIVE_CAMPAIGN_SCHEDULE_STATUSES),
            ScheduledEmail.approval_status != "REJECTED",
        )
        .first()
        is not None
    )
    return not has_active


def emit_campaign_finished_notifications(db: Session) -> int:
    campaigns = db.query(Campaign).order_by(Campaign.created_at.asc()).all()
    emitted = 0

    for campaign in campaigns:
        if not _campaign_is_finished(db, campaign):
            continue

        before_count = (
            db.query(Notification.id)
            .filter(
                Notification.event_type == EVENT_CAMPAIGN_FINISHED,
                Notification.resource_type == "campaign",
                Notification.resource_id == campaign.id,
            )
            .count()
        )
        emit_workspace_notification(
            db,
            workspace_id=campaign.workspace_id,
            event_type=EVENT_CAMPAIGN_FINISHED,
            title=f"Campaign finished: {campaign.name}",
            body=f"Campaign {campaign.name} has no remaining active scheduled emails.",
            metadata={"campaign_id": campaign.id, "campaign_name": campaign.name},
            resource_type="campaign",
            resource_id=campaign.id,
        )
        after_count = (
            db.query(Notification.id)
            .filter(
                Notification.event_type == EVENT_CAMPAIGN_FINISHED,
                Notification.resource_type == "campaign",
                Notification.resource_id == campaign.id,
            )
            .count()
        )
        if after_count > before_count:
            emitted += 1

    return emitted


def emit_booked_meeting_notifications(db: Session) -> int:
    meetings = (
        db.query(Meeting)
        .join(Meeting.lead)
        .filter(Meeting.status == "BOOKED")
        .order_by(Meeting.created_at.asc())
        .all()
    )
    emitted = 0

    for meeting in meetings:
        lead = meeting.lead
        if not lead:
            continue

        before_count = (
            db.query(Notification.id)
            .filter(
                Notification.event_type == EVENT_MEETING_SCHEDULED,
                Notification.resource_type == "meeting",
                Notification.resource_id == meeting.id,
            )
            .count()
        )
        emit_workspace_notification(
            db,
            workspace_id=lead.workspace_id,
            event_type=EVENT_MEETING_SCHEDULED,
            title=f"Meeting scheduled with {lead.name or lead.email}",
            body=(
                f"{lead.name or lead.email} booked a meeting."
                + (
                    f" Scheduled for {meeting.scheduled_time.isoformat()}."
                    if meeting.scheduled_time
                    else ""
                )
            ),
            metadata={
                "meeting_id": meeting.id,
                "lead_id": lead.id,
                "meeting_link": meeting.meeting_link,
                "scheduled_time": (
                    meeting.scheduled_time.isoformat()
                    if meeting.scheduled_time
                    else None
                ),
            },
            resource_type="meeting",
            resource_id=meeting.id,
        )
        after_count = (
            db.query(Notification.id)
            .filter(
                Notification.event_type == EVENT_MEETING_SCHEDULED,
                Notification.resource_type == "meeting",
                Notification.resource_id == meeting.id,
            )
            .count()
        )
        if after_count > before_count:
            emitted += 1

    return emitted
