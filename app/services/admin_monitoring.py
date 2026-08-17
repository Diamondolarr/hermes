from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.abuse_alert import AbuseAlert
from app.models.api_usage_log import ApiUsageLog
from app.models.campaign import Campaign
from app.models.email_reply import EmailReply
from app.models.lead import Lead
from app.models.meeting import Meeting
from app.models.reply_classification import ReplyClassification
from app.models.sent_email import SentEmail
from app.models.user import User
from app.models.workspace import Workspace

PROVIDER_INTERNAL = "internal"

ALERT_STATUS_OPEN = "OPEN"
ALERT_STATUS_RESOLVED = "RESOLVED"

ALERT_TYPE_LOGIN_FAILURES = "repeated_login_failures"
ALERT_TYPE_SEND_SPIKE = "high_send_volume_spike"
ALERT_TYPE_UNSUBSCRIBE_RATE = "high_unsubscribe_rate"
ALERT_TYPE_API_FAILURES = "repeated_api_failures"

KNOWN_ALERT_TYPES = {
    ALERT_TYPE_LOGIN_FAILURES,
    ALERT_TYPE_SEND_SPIKE,
    ALERT_TYPE_UNSUBSCRIBE_RATE,
    ALERT_TYPE_API_FAILURES,
}


@dataclass
class AdminOverview:
    total_users: int
    total_workspaces: int
    total_leads: int
    total_campaigns: int
    total_sent_emails: int
    total_replies: int
    total_meetings: int
    open_abuse_alerts: int
    api_requests_last_24h: int
    failed_api_requests_last_24h: int


@dataclass
class CampaignMonitorItem:
    campaign_id: str
    workspace_id: str
    campaign_name: str
    status: str
    emails_sent: int
    emails_replied: int
    reply_rate: float
    meetings_booked: int
    created_at: datetime


@dataclass
class ApiUsageSummaryItem:
    provider: str
    feature: str
    model_name: str | None
    total_requests: int
    failed_requests: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    last_called_at: datetime


def _normalize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    return {str(key): value for key, value in metadata.items()}


def _persist_api_usage(
    db: Session,
    *,
    workspace_id: str | None,
    provider: str,
    feature: str,
    model_name: str | None,
    request_count: int,
    estimated_input_tokens: int | None,
    estimated_output_tokens: int | None,
    success: bool,
    metadata: dict[str, Any] | None,
) -> None:
    db.add(
        ApiUsageLog(
            workspace_id=workspace_id,
            provider=provider.strip(),
            feature=feature.strip(),
            model_name=(model_name or "").strip() or None,
            request_count=max(1, int(request_count or 1)),
            estimated_input_tokens=(
                max(0, int(estimated_input_tokens))
                if estimated_input_tokens is not None
                else None
            ),
            estimated_output_tokens=(
                max(0, int(estimated_output_tokens))
                if estimated_output_tokens is not None
                else None
            ),
            success=bool(success),
            metadata_json=_normalize_metadata(metadata),
        )
    )
    db.flush()


def record_api_usage(
    db: Session,
    *,
    workspace_id: str | None,
    provider: str,
    feature: str,
    model_name: str | None = None,
    request_count: int = 1,
    estimated_input_tokens: int | None = None,
    estimated_output_tokens: int | None = None,
    success: bool = True,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        with db.begin_nested():
            _persist_api_usage(
                db,
                workspace_id=workspace_id,
                provider=provider,
                feature=feature,
                model_name=model_name,
                request_count=request_count,
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
                success=success,
                metadata=metadata,
            )
    except Exception:
        return


def record_api_usage_event(
    *,
    workspace_id: str | None,
    provider: str,
    feature: str,
    model_name: str | None = None,
    request_count: int = 1,
    estimated_input_tokens: int | None = None,
    estimated_output_tokens: int | None = None,
    success: bool = True,
    metadata: dict[str, Any] | None = None,
) -> None:
    db = SessionLocal()
    try:
        _persist_api_usage(
            db,
            workspace_id=workspace_id,
            provider=provider,
            feature=feature,
            model_name=model_name,
            request_count=request_count,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            success=success,
            metadata=metadata,
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def get_admin_overview(db: Session) -> AdminOverview:
    since = datetime.utcnow() - timedelta(hours=24)
    return AdminOverview(
        total_users=int(db.query(func.count(User.id)).scalar() or 0),
        total_workspaces=int(db.query(func.count(Workspace.id)).scalar() or 0),
        total_leads=int(db.query(func.count(Lead.id)).scalar() or 0),
        total_campaigns=int(db.query(func.count(Campaign.id)).scalar() or 0),
        total_sent_emails=int(
            db.query(func.count(SentEmail.id))
            .filter(SentEmail.status == "SENT")
            .scalar()
            or 0
        ),
        total_replies=int(db.query(func.count(EmailReply.id)).scalar() or 0),
        total_meetings=int(db.query(func.count(Meeting.id)).scalar() or 0),
        open_abuse_alerts=int(
            db.query(func.count(AbuseAlert.id))
            .filter(AbuseAlert.status == ALERT_STATUS_OPEN)
            .scalar()
            or 0
        ),
        api_requests_last_24h=int(
            db.query(func.count(ApiUsageLog.id))
            .filter(ApiUsageLog.created_at >= since)
            .scalar()
            or 0
        ),
        failed_api_requests_last_24h=int(
            db.query(func.count(ApiUsageLog.id))
            .filter(ApiUsageLog.created_at >= since, ApiUsageLog.success.is_(False))
            .scalar()
            or 0
        ),
    )


def _campaign_metrics(db: Session, campaign: Campaign) -> CampaignMonitorItem:
    sent_rows = (
        db.query(SentEmail)
        .filter(SentEmail.campaign_id == campaign.id, SentEmail.status == "SENT")
        .all()
    )
    emails_sent = len(sent_rows)
    lead_ids = {row.lead_id for row in sent_rows}
    thread_keys = {
        (row.thread_id, row.email_account_id)
        for row in sent_rows
        if row.thread_id and row.email_account_id
    }

    replies = (
        db.query(EmailReply).filter(EmailReply.lead_id.in_(lead_ids)).all()
        if lead_ids
        else []
    )

    replied_leads: set[str] = set()
    for reply in replies:
        if (reply.thread_id, reply.email_account_id) in thread_keys:
            replied_leads.add(reply.lead_id)
        elif reply.lead_id in lead_ids:
            replied_leads.add(reply.lead_id)

    meetings_booked = int(
        db.query(func.count(func.distinct(Meeting.lead_id)))
        .filter(
            Meeting.status == "BOOKED",
            Meeting.lead_id.in_(list(lead_ids) or [""]),
        )
        .scalar()
        or 0
    )

    return CampaignMonitorItem(
        campaign_id=campaign.id,
        workspace_id=campaign.workspace_id,
        campaign_name=campaign.name,
        status=campaign.status,
        emails_sent=emails_sent,
        emails_replied=len(replied_leads),
        reply_rate=round((len(replied_leads) / emails_sent), 4) if emails_sent else 0.0,
        meetings_booked=meetings_booked,
        created_at=campaign.created_at,
    )


def list_monitored_campaigns(
    db: Session,
    *,
    status_filter: str | None = None,
    limit: int = 100,
) -> list[CampaignMonitorItem]:
    query = db.query(Campaign).order_by(Campaign.created_at.desc())
    if status_filter:
        query = query.filter(Campaign.status == status_filter)
    campaigns = query.limit(max(1, min(limit, 200))).all()
    return [_campaign_metrics(db, campaign) for campaign in campaigns]


def summarize_api_usage(db: Session, *, days: int = 7) -> list[ApiUsageSummaryItem]:
    since = datetime.utcnow() - timedelta(days=max(1, min(days, 90)))
    rows = (
        db.query(
            ApiUsageLog.provider,
            ApiUsageLog.feature,
            ApiUsageLog.model_name,
            func.sum(ApiUsageLog.request_count),
            func.sum(case((ApiUsageLog.success.is_(False), ApiUsageLog.request_count), else_=0)),
            func.sum(func.coalesce(ApiUsageLog.estimated_input_tokens, 0)),
            func.sum(func.coalesce(ApiUsageLog.estimated_output_tokens, 0)),
            func.max(ApiUsageLog.created_at),
        )
        .filter(ApiUsageLog.created_at >= since)
        .group_by(ApiUsageLog.provider, ApiUsageLog.feature, ApiUsageLog.model_name)
        .order_by(
            func.sum(ApiUsageLog.request_count).desc(),
            func.max(ApiUsageLog.created_at).desc(),
        )
        .all()
    )
    return [
        ApiUsageSummaryItem(
            provider=provider,
            feature=feature,
            model_name=model_name,
            total_requests=int(total_requests or 0),
            failed_requests=int(failed_requests or 0),
            estimated_input_tokens=int(input_tokens or 0),
            estimated_output_tokens=int(output_tokens or 0),
            last_called_at=last_called_at,
        )
        for (
            provider,
            feature,
            model_name,
            total_requests,
            failed_requests,
            input_tokens,
            output_tokens,
            last_called_at,
        ) in rows
    ]


def _upsert_alert(
    db: Session,
    *,
    dedupe_key: str,
    workspace_id: str | None,
    alert_type: str,
    severity: str,
    title: str,
    description: str,
    metadata: dict[str, Any] | None,
) -> None:
    now = datetime.utcnow()
    alert = db.query(AbuseAlert).filter(AbuseAlert.dedupe_key == dedupe_key).first()
    if alert:
        alert.workspace_id = workspace_id
        alert.alert_type = alert_type
        alert.severity = severity
        alert.status = ALERT_STATUS_OPEN
        alert.title = title
        alert.description = description
        alert.metadata_json = _normalize_metadata(metadata)
        alert.last_seen_at = now
        alert.resolved_at = None
        return

    db.add(
        AbuseAlert(
            workspace_id=workspace_id,
            alert_type=alert_type,
            severity=severity,
            status=ALERT_STATUS_OPEN,
            dedupe_key=dedupe_key,
            title=title,
            description=description,
            metadata_json=_normalize_metadata(metadata),
            created_at=now,
            last_seen_at=now,
        )
    )


def _build_login_failure_alerts(db: Session) -> list[dict[str, Any]]:
    since = datetime.utcnow() - timedelta(minutes=15)
    rows = (
        db.query(ApiUsageLog)
        .filter(
            ApiUsageLog.provider == PROVIDER_INTERNAL,
            ApiUsageLog.feature == "auth_login",
            ApiUsageLog.success.is_(False),
            ApiUsageLog.created_at >= since,
        )
        .all()
    )
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        ip_address = (row.metadata_json or {}).get("ip_address") or "unknown"
        bucket = grouped.setdefault(
            ip_address,
            {"count": 0, "email_samples": set(), "last_seen_at": row.created_at},
        )
        bucket["count"] += int(row.request_count or 1)
        email_value = (row.metadata_json or {}).get("email")
        if email_value:
            bucket["email_samples"].add(email_value)
        if row.created_at > bucket["last_seen_at"]:
            bucket["last_seen_at"] = row.created_at

    alerts: list[dict[str, Any]] = []
    for ip_address, bucket in grouped.items():
        if bucket["count"] < 10:
            continue
        alerts.append(
            {
                "dedupe_key": f"{ALERT_TYPE_LOGIN_FAILURES}:{ip_address}",
                "workspace_id": None,
                "alert_type": ALERT_TYPE_LOGIN_FAILURES,
                "severity": "HIGH",
                "title": f"Repeated login failures from {ip_address}",
                "description": (
                    f"{bucket['count']} failed login attempts were recorded from {ip_address} in the last 15 minutes."
                ),
                "metadata": {
                    "ip_address": ip_address,
                    "attempt_count": bucket["count"],
                    "email_samples": sorted(bucket["email_samples"])[:5],
                    "last_seen_at": bucket["last_seen_at"].isoformat(),
                },
            }
        )
    return alerts


def _build_send_spike_alerts(db: Session) -> list[dict[str, Any]]:
    since = datetime.utcnow() - timedelta(hours=1)
    rows = (
        db.query(Campaign.workspace_id, func.count(SentEmail.id))
        .select_from(SentEmail)
        .join(Campaign, Campaign.id == SentEmail.campaign_id)
        .filter(SentEmail.status == "SENT", SentEmail.sent_at >= since)
        .group_by(Campaign.workspace_id)
        .all()
    )
    return [
        {
            "dedupe_key": f"{ALERT_TYPE_SEND_SPIKE}:{workspace_id}",
            "workspace_id": workspace_id,
            "alert_type": ALERT_TYPE_SEND_SPIKE,
            "severity": "MEDIUM",
            "title": "High outbound email spike detected",
            "description": f"Workspace {workspace_id} sent {int(sent_count)} emails in the last hour.",
            "metadata": {
                "workspace_id": workspace_id,
                "sent_count_last_hour": int(sent_count),
            },
        }
        for workspace_id, sent_count in rows
        if int(sent_count or 0) >= 100
    ]


def _build_unsubscribe_alerts(db: Session) -> list[dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=7)
    rows = (
        db.query(
            Lead.workspace_id,
            func.count(ReplyClassification.id),
            func.sum(case((ReplyClassification.category == "UNSUBSCRIBE", 1), else_=0)),
        )
        .select_from(ReplyClassification)
        .join(Lead, Lead.id == ReplyClassification.lead_id)
        .filter(ReplyClassification.created_at >= since)
        .group_by(Lead.workspace_id)
        .all()
    )

    alerts: list[dict[str, Any]] = []
    for workspace_id, total_count, unsubscribe_count in rows:
        total = int(total_count or 0)
        unsubscribes = int(unsubscribe_count or 0)
        if total < 5:
            continue
        rate = unsubscribes / total if total else 0.0
        if rate < 0.3:
            continue
        alerts.append(
            {
                "dedupe_key": f"{ALERT_TYPE_UNSUBSCRIBE_RATE}:{workspace_id}",
                "workspace_id": workspace_id,
                "alert_type": ALERT_TYPE_UNSUBSCRIBE_RATE,
                "severity": "HIGH",
                "title": "High unsubscribe rate detected",
                "description": (
                    f"Workspace {workspace_id} has an unsubscribe rate of {rate * 100:.1f}% over the last 7 days."
                ),
                "metadata": {
                    "workspace_id": workspace_id,
                    "unsubscribe_rate": round(rate, 4),
                    "reply_count": total,
                    "unsubscribe_count": unsubscribes,
                },
            }
        )
    return alerts


def _build_api_failure_alerts(db: Session) -> list[dict[str, Any]]:
    since = datetime.utcnow() - timedelta(minutes=30)
    rows = (
        db.query(ApiUsageLog)
        .filter(ApiUsageLog.success.is_(False), ApiUsageLog.created_at >= since)
        .all()
    )
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.provider == PROVIDER_INTERNAL and row.feature in {"auth_login", "rate_limit"}:
            continue
        workspace_value = row.workspace_id or "global"
        key = f"{workspace_value}:{row.provider}:{row.feature}"
        bucket = grouped.setdefault(
            key,
            {
                "workspace_id": row.workspace_id,
                "provider": row.provider,
                "feature": row.feature,
                "model_name": row.model_name,
                "count": 0,
                "last_seen_at": row.created_at,
            },
        )
        bucket["count"] += int(row.request_count or 1)
        if row.created_at > bucket["last_seen_at"]:
            bucket["last_seen_at"] = row.created_at

    alerts: list[dict[str, Any]] = []
    for key, bucket in grouped.items():
        if bucket["count"] < 5:
            continue
        alerts.append(
            {
                "dedupe_key": f"{ALERT_TYPE_API_FAILURES}:{key}",
                "workspace_id": bucket["workspace_id"],
                "alert_type": ALERT_TYPE_API_FAILURES,
                "severity": "MEDIUM",
                "title": f"Repeated {bucket['provider']} failures detected",
                "description": (
                    f"{bucket['count']} failed {bucket['provider']} calls were recorded for {bucket['feature']} in the last 30 minutes."
                ),
                "metadata": {
                    "workspace_id": bucket["workspace_id"],
                    "provider": bucket["provider"],
                    "feature": bucket["feature"],
                    "model_name": bucket["model_name"],
                    "failure_count": bucket["count"],
                    "last_seen_at": bucket["last_seen_at"].isoformat(),
                },
            }
        )
    return alerts


def sync_abuse_alerts(db: Session) -> list[AbuseAlert]:
    detected = (
        _build_login_failure_alerts(db)
        + _build_send_spike_alerts(db)
        + _build_unsubscribe_alerts(db)
        + _build_api_failure_alerts(db)
    )
    active_keys = {item["dedupe_key"] for item in detected}

    for item in detected:
        _upsert_alert(
            db,
            dedupe_key=item["dedupe_key"],
            workspace_id=item["workspace_id"],
            alert_type=item["alert_type"],
            severity=item["severity"],
            title=item["title"],
            description=item["description"],
            metadata=item["metadata"],
        )

    now = datetime.utcnow()
    open_alerts = (
        db.query(AbuseAlert)
        .filter(
            AbuseAlert.status == ALERT_STATUS_OPEN,
            AbuseAlert.alert_type.in_(KNOWN_ALERT_TYPES),
        )
        .all()
    )
    for alert in open_alerts:
        if alert.dedupe_key not in active_keys:
            alert.status = ALERT_STATUS_RESOLVED
            alert.resolved_at = now

    db.flush()
    return (
        db.query(AbuseAlert)
        .order_by(AbuseAlert.last_seen_at.desc(), AbuseAlert.created_at.desc())
        .all()
    )
