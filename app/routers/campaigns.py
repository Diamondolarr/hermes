from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.schemas.campaigns import (
    CampaignAnalyticsResponse,
    CampaignCreateRequest,
    CampaignInsightResponse,
    CampaignResponse,
)
from app.schemas.scheduled_emails import (
    ScheduledEmailResponse,
    ScheduledSequenceResponse,
)
from app.services.campaign_analytics import get_campaign_analytics
from app.services.campaign_insights import generate_campaign_insight
from app.services.cache import cache_get_json, cache_set_json
from app.services.email_generation import EmailGenerationServiceError
from app.services.email_scheduling import (
    SchedulingServiceError,
    build_send_time_window,
    parse_send_time_window,
    schedule_campaign_for_lead,
    validate_send_timezone,
)
from app.services.followup_generation import FollowupGenerationServiceError
from app.services.lead_research import LeadResearchServiceError
from app.services.sales_insight import SalesInsightServiceError
from app.services.user_settings import get_or_create_user_settings
from app.utils.auth import get_current_user

router = APIRouter()


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: CampaignCreateRequest,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    user, workspace = current
    user_settings = get_or_create_user_settings(db, user)
    message_tone = (payload.message_tone or user_settings.default_email_tone).strip()
    daily_send_limit = payload.daily_send_limit or user_settings.daily_send_limit
    send_timezone_value = (payload.send_timezone or user_settings.timezone).strip()
    try:
        window_start, window_end = parse_send_time_window(payload.send_time_window)
        send_timezone = validate_send_timezone(send_timezone_value)
    except SchedulingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    campaign = Campaign(
        workspace_id=workspace.id,
        name=payload.campaign_name.strip(),
        target_icp=payload.target_icp.strip(),
        message_tone=message_tone,
        cta_type=payload.cta_type.strip(),
        daily_send_limit=daily_send_limit,
        send_time_window_start=window_start,
        send_time_window_end=window_end,
        send_timezone=send_timezone,
        followup_delay_days=payload.followup_delay_days,
        status="DRAFT",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return CampaignResponse(
        id=campaign.id,
        workspace_id=campaign.workspace_id,
        name=campaign.name,
        target_icp=campaign.target_icp,
        message_tone=campaign.message_tone,
        cta_type=campaign.cta_type,
        daily_send_limit=campaign.daily_send_limit,
        send_time_window=build_send_time_window(
            campaign.send_time_window_start, campaign.send_time_window_end
        ),
        send_timezone=campaign.send_timezone,
        followup_delay_days=campaign.followup_delay_days,
        status=campaign.status,
        created_at=campaign.created_at,
    )


@router.get("/{campaign_id}/analytics", response_model=CampaignAnalyticsResponse)
def get_campaign_analytics_endpoint(
    campaign_id: str,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignAnalyticsResponse:
    _, workspace = current

    cache_key = f"campaign:analytics:{workspace.id}:{campaign_id}"
    cached = cache_get_json(cache_key)
    if cached:
        return CampaignAnalyticsResponse(**cached)

    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.workspace_id == workspace.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    analytics = get_campaign_analytics(db, campaign)
    response = CampaignAnalyticsResponse(
        campaign_id=analytics.campaign_id,
        campaign_name=analytics.campaign_name,
        status=analytics.status,
        emails_sent=analytics.emails_sent,
        emails_replied=analytics.emails_replied,
        reply_rate=analytics.reply_rate,
        meetings_booked=analytics.meetings_booked,
        conversion_rate=analytics.conversion_rate,
        ai_summary=analytics.ai_summary,
        ai_recommendations=analytics.ai_recommendations,
    )
    cache_set_json(
        cache_key,
        response.model_dump(mode="json"),
        settings.campaign_analytics_cache_ttl_seconds,
    )
    return response


@router.post(
    "/{campaign_id}/insights/generate",
    response_model=CampaignInsightResponse,
)
def generate_campaign_insight_endpoint(
    campaign_id: str,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignInsightResponse:
    _, workspace = current

    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.workspace_id == workspace.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    insight = generate_campaign_insight(db, campaign)
    db.commit()
    db.refresh(insight)

    return CampaignInsightResponse(
        id=insight.id,
        campaign_id=insight.campaign_id,
        best_subject_line=insight.best_subject_line,
        best_send_time=insight.best_send_time,
        best_industry_response=insight.best_industry_response,
        summary=insight.summary,
        recommendations=insight.recommendations,
        generated_at=insight.generated_at,
    )


@router.post(
    "/{campaign_id}/schedule/{lead_id}",
    response_model=ScheduledSequenceResponse,
)
def schedule_campaign_sequence(
    campaign_id: str,
    lead_id: str,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScheduledSequenceResponse:
    _, workspace = current

    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.workspace_id == workspace.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.workspace_id == workspace.id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    try:
        items = schedule_campaign_for_lead(
            db,
            workspace.id,
            lead,
            campaign,
            human_approval_enabled=workspace.human_approval_enabled,
        )
    except (
        SchedulingServiceError,
        EmailGenerationServiceError,
        FollowupGenerationServiceError,
        LeadResearchServiceError,
        SalesInsightServiceError,
    ) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    db.commit()
    for item in items:
        db.refresh(item)
    db.refresh(campaign)

    return ScheduledSequenceResponse(
        lead_id=lead.id,
        campaign_id=campaign.id,
        items=[
            ScheduledEmailResponse(
                id=item.id,
                lead_id=item.lead_id,
                campaign_id=item.campaign_id,
                step_number=item.step_number,
                email_type=item.email_type,
                scheduled_for=item.scheduled_for,
                status=item.status,
                approval_status=item.approval_status,
                created_at=item.created_at,
            )
            for item in items
        ],
    )
