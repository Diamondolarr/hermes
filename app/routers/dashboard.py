from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.db.session import get_db
from app.models.activity_log import ActivityLog
from app.models.campaign import Campaign
from app.models.email import EmailAccount
from app.models.email_reply import EmailReply
from app.models.lead import Lead
from app.models.meeting import Meeting
from app.models.notification import Notification
from app.models.reply_classification import ReplyClassification
from app.models.scheduled_email import ScheduledEmail
from app.models.sent_email import SentEmail
from app.schemas.dashboard import (
    DashboardActivityItem,
    DashboardCampaignSnapshotItem,
    DashboardNotificationPreviewItem,
    DashboardPendingApprovalItem,
    DashboardRecentReplyItem,
    DashboardSummaryResponse,
)
from app.utils.auth import get_current_user

router = APIRouter()


def _truncate(text: str, limit: int = 120) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 3].rstrip()}..."


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    current=Depends(get_current_user), db: Session = Depends(get_db)
) -> DashboardSummaryResponse:
    user, workspace = current

    leads = (
        db.query(func.count(Lead.id))
        .filter(Lead.workspace_id == workspace.id)
        .scalar()
        or 0
    )
    active_campaigns = (
        db.query(func.count(Campaign.id))
        .filter(Campaign.workspace_id == workspace.id, Campaign.status != "DRAFT")
        .scalar()
        or 0
    )
    emails_sent = (
        db.query(func.count(SentEmail.id))
        .join(Campaign, SentEmail.campaign_id == Campaign.id)
        .filter(Campaign.workspace_id == workspace.id, SentEmail.status == "SENT")
        .scalar()
        or 0
    )
    replies = (
        db.query(func.count(EmailReply.id))
        .join(Lead, EmailReply.lead_id == Lead.id)
        .filter(Lead.workspace_id == workspace.id)
        .scalar()
        or 0
    )
    meetings = (
        db.query(func.count(Meeting.id))
        .join(Lead, Meeting.lead_id == Lead.id)
        .filter(Lead.workspace_id == workspace.id)
        .scalar()
        or 0
    )
    pending_approvals_count = (
        db.query(func.count(ScheduledEmail.id))
        .join(Campaign, ScheduledEmail.campaign_id == Campaign.id)
        .filter(
            Campaign.workspace_id == workspace.id,
            ScheduledEmail.approval_status == "PENDING_APPROVAL",
        )
        .scalar()
        or 0
    )
    unread_notifications_count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .scalar()
        or 0
    )
    connected_email_accounts = (
        db.query(func.count(EmailAccount.id))
        .filter(EmailAccount.workspace_id == workspace.id)
        .scalar()
        or 0
    )

    recent_reply_rows = (
        db.query(EmailReply, Lead, ReplyClassification)
        .join(Lead, EmailReply.lead_id == Lead.id)
        .outerjoin(
            ReplyClassification,
            ReplyClassification.email_reply_id == EmailReply.id,
        )
        .filter(Lead.workspace_id == workspace.id)
        .order_by(desc(EmailReply.received_at))
        .limit(4)
        .all()
    )
    recent_replies = [
        DashboardRecentReplyItem(
            id=reply.id,
            lead_id=lead.id,
            lead_name=lead.name,
            company=lead.company,
            category=classification.category if classification else None,
            preview=_truncate(reply.reply_body),
            received_at=reply.received_at,
        )
        for reply, lead, classification in recent_reply_rows
    ]

    pending_approval_rows = (
        db.query(ScheduledEmail, Lead, Campaign)
        .join(Lead, ScheduledEmail.lead_id == Lead.id)
        .join(Campaign, ScheduledEmail.campaign_id == Campaign.id)
        .filter(
            Campaign.workspace_id == workspace.id,
            ScheduledEmail.approval_status == "PENDING_APPROVAL",
        )
        .order_by(ScheduledEmail.scheduled_for.asc())
        .limit(4)
        .all()
    )
    pending_approvals = [
        DashboardPendingApprovalItem(
            scheduled_email_id=scheduled_email.id,
            lead_id=lead.id,
            lead_name=lead.name,
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            scheduled_for=scheduled_email.scheduled_for,
            step_number=scheduled_email.step_number,
        )
        for scheduled_email, lead, campaign in pending_approval_rows
    ]

    campaign_rows = (
        db.query(Campaign)
        .filter(Campaign.workspace_id == workspace.id, Campaign.status != "DRAFT")
        .order_by(desc(Campaign.created_at))
        .limit(4)
        .all()
    )
    campaign_snapshot: list[DashboardCampaignSnapshotItem] = []
    for campaign in campaign_rows:
        sent_count = (
            db.query(func.count(SentEmail.id))
            .filter(SentEmail.campaign_id == campaign.id, SentEmail.status == "SENT")
            .scalar()
            or 0
        )
        lead_ids = [
            lead_id
            for (lead_id,) in db.query(SentEmail.lead_id)
            .filter(SentEmail.campaign_id == campaign.id)
            .distinct()
            .all()
        ]
        reply_count = (
            db.query(func.count(func.distinct(EmailReply.lead_id)))
            .filter(EmailReply.lead_id.in_(lead_ids))
            .scalar()
            if lead_ids
            else 0
        ) or 0
        reply_rate = (reply_count / sent_count * 100) if sent_count else 0.0
        campaign_snapshot.append(
            DashboardCampaignSnapshotItem(
                campaign_id=campaign.id,
                name=campaign.name,
                status=campaign.status,
                emails_sent=sent_count,
                replies=reply_count,
                reply_rate=round(reply_rate, 1),
            )
        )

    notifications_preview = [
        DashboardNotificationPreviewItem(
            id=notification.id,
            event_type=notification.event_type,
            title=notification.title,
            body=_truncate(notification.body, 140),
            created_at=notification.created_at,
        )
        for notification in db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .order_by(desc(Notification.created_at))
        .limit(4)
        .all()
    ]

    recent_activity = [
        DashboardActivityItem(
            id=activity.id,
            event_type=activity.event_type,
            message=_truncate(activity.message, 140),
            created_at=activity.created_at,
        )
        for activity in db.query(ActivityLog)
        .filter(ActivityLog.workspace_id == workspace.id)
        .order_by(desc(ActivityLog.created_at))
        .limit(4)
        .all()
    ]

    return DashboardSummaryResponse(
        leads=leads,
        active_campaigns=active_campaigns,
        emails_sent=emails_sent,
        replies=replies,
        meetings=meetings,
        pending_approvals_count=pending_approvals_count,
        unread_notifications_count=unread_notifications_count,
        connected_email_accounts=connected_email_accounts,
        recent_replies=recent_replies,
        pending_approvals=pending_approvals,
        active_campaigns_snapshot=campaign_snapshot,
        notifications_preview=notifications_preview,
        recent_activity=recent_activity,
    )
