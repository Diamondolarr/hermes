from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.abuse_alert import AbuseAlert
from app.schemas.admin import (
    AbuseAlertResponse,
    AdminApiUsageSummaryResponse,
    AdminCampaignMonitorResponse,
    AdminOverviewResponse,
)
from app.services.admin_monitoring import (
    get_admin_overview,
    list_monitored_campaigns,
    summarize_api_usage,
    sync_abuse_alerts,
)
from app.services.cache import cache_get_json, cache_set_json
from app.utils.auth import get_current_admin

router = APIRouter()


@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview_endpoint(
    _: tuple = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    cache_key = "admin:overview"
    cached = cache_get_json(cache_key)
    if cached:
        return AdminOverviewResponse(**cached)

    overview = get_admin_overview(db)
    response = AdminOverviewResponse(
        total_users=overview.total_users,
        total_workspaces=overview.total_workspaces,
        total_leads=overview.total_leads,
        total_campaigns=overview.total_campaigns,
        total_sent_emails=overview.total_sent_emails,
        total_replies=overview.total_replies,
        total_meetings=overview.total_meetings,
        open_abuse_alerts=overview.open_abuse_alerts,
        api_requests_last_24h=overview.api_requests_last_24h,
        failed_api_requests_last_24h=overview.failed_api_requests_last_24h,
    )
    cache_set_json(
        cache_key,
        response.model_dump(mode="json"),
        settings.admin_overview_cache_ttl_seconds,
    )
    return response


@router.get("/campaigns", response_model=list[AdminCampaignMonitorResponse])
def list_admin_campaigns(
    status_filter: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _: tuple = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[AdminCampaignMonitorResponse]:
    items = list_monitored_campaigns(db, status_filter=status_filter, limit=limit)
    return [
        AdminCampaignMonitorResponse(
            campaign_id=item.campaign_id,
            workspace_id=item.workspace_id,
            campaign_name=item.campaign_name,
            status=item.status,
            emails_sent=item.emails_sent,
            emails_replied=item.emails_replied,
            reply_rate=item.reply_rate,
            meetings_booked=item.meetings_booked,
            created_at=item.created_at,
        )
        for item in items
    ]


@router.get("/usage", response_model=list[AdminApiUsageSummaryResponse])
def get_admin_usage(
    days: int = Query(default=7, ge=1, le=90),
    _: tuple = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[AdminApiUsageSummaryResponse]:
    cache_key = f"admin:usage:{days}"
    cached = cache_get_json(cache_key)
    if cached:
        return [AdminApiUsageSummaryResponse(**item) for item in cached]

    items = summarize_api_usage(db, days=days)
    response = [
        AdminApiUsageSummaryResponse(
            provider=item.provider,
            feature=item.feature,
            model_name=item.model_name,
            total_requests=item.total_requests,
            failed_requests=item.failed_requests,
            estimated_input_tokens=item.estimated_input_tokens,
            estimated_output_tokens=item.estimated_output_tokens,
            last_called_at=item.last_called_at,
        )
        for item in items
    ]
    cache_set_json(
        cache_key,
        [item.model_dump(mode="json") for item in response],
        settings.admin_usage_cache_ttl_seconds,
    )
    return response


@router.get("/abuse-alerts", response_model=list[AbuseAlertResponse])
def get_abuse_alerts(
    status_filter: str | None = Query(default=None),
    refresh: bool = Query(default=True),
    _: tuple = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[AbuseAlertResponse]:
    alerts = sync_abuse_alerts(db) if refresh else db.query(AbuseAlert).all()
    db.commit()
    rows = alerts
    if status_filter:
        rows = [alert for alert in rows if alert.status == status_filter]
    rows.sort(key=lambda item: (item.last_seen_at, item.created_at), reverse=True)

    return [
        AbuseAlertResponse(
            id=alert.id,
            workspace_id=alert.workspace_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            status=alert.status,
            dedupe_key=alert.dedupe_key,
            title=alert.title,
            description=alert.description,
            metadata=alert.metadata_json or {},
            created_at=alert.created_at,
            last_seen_at=alert.last_seen_at,
            resolved_at=alert.resolved_at,
        )
        for alert in rows
    ]
