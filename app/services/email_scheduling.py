from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.campaign import Campaign
from app.models.followup import Followup
from app.models.lead import Lead
from app.models.onboarding import CompanyProfile
from app.models.scheduled_email import ScheduledEmail
from app.services.admin_monitoring import record_api_usage, record_api_usage_event
from app.services.followup_generation import (
    FollowupGenerationServiceError,
    generate_followup_sequence,
)
from app.services.insight_pipeline import ensure_generated_email, ensure_sales_insight

INITIAL_EMAIL_TYPE = "INITIAL"
FOLLOWUP_EMAIL_TYPE = "FOLLOWUP"
ACTIVE_SCHEDULE_STATUSES = ("PENDING", "QUEUED", "SENT")


class SchedulingServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def default_approval_status(human_approval_enabled: bool) -> str:
    return "PENDING_APPROVAL" if human_approval_enabled else "APPROVED"


def parse_send_time_window(window: str) -> tuple[str, str]:
    parts = [part.strip() for part in window.split("-", maxsplit=1)]
    if len(parts) != 2:
        raise SchedulingServiceError(
            "Send time window must use HH:MM-HH:MM format.", status_code=400
        )

    start_raw, end_raw = parts
    start_time = _parse_time_value(start_raw)
    end_time = _parse_time_value(end_raw)
    if end_time <= start_time:
        raise SchedulingServiceError(
            "Send time window end must be later than start.", status_code=400
        )
    return start_time.strftime("%H:%M"), end_time.strftime("%H:%M")


def build_send_time_window(start: str, end: str) -> str:
    return f"{start}-{end}"


def validate_send_timezone(value: str) -> str:
    cleaned = value.strip()
    _get_timezone(cleaned)
    return cleaned


def _parse_time_value(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise SchedulingServiceError(
            "Time values must use HH:MM format.", status_code=400
        ) from exc


def _get_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise SchedulingServiceError(
            f"Unknown timezone `{name}`.", status_code=400
        ) from exc


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _to_local(value: datetime, tz: ZoneInfo) -> datetime:
    return _as_utc_naive(value).replace(tzinfo=timezone.utc).astimezone(tz)


def _local_window_for_date(
    *, target_date: date, tz: ZoneInfo, start_value: str, end_value: str
) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(target_date, _parse_time_value(start_value), tzinfo=tz)
    end_dt = datetime.combine(target_date, _parse_time_value(end_value), tzinfo=tz)
    return start_dt, end_dt


def _count_scheduled_for_local_day(
    db: Session,
    campaign: Campaign,
    *,
    target_date: date,
) -> int:
    tz = _get_timezone(campaign.send_timezone)
    day_start_local = datetime.combine(target_date, time.min, tzinfo=tz)
    day_end_local = day_start_local + timedelta(days=1)
    day_start_utc = day_start_local.astimezone(timezone.utc).replace(tzinfo=None)
    day_end_utc = day_end_local.astimezone(timezone.utc).replace(tzinfo=None)

    return (
        db.query(func.count(ScheduledEmail.id))
        .filter(
            ScheduledEmail.campaign_id == campaign.id,
            ScheduledEmail.scheduled_for >= day_start_utc,
            ScheduledEmail.scheduled_for < day_end_utc,
            ScheduledEmail.status.in_(ACTIVE_SCHEDULE_STATUSES),
            ScheduledEmail.approval_status != "REJECTED",
        )
        .scalar()
        or 0
    )


def resolve_next_send_time(
    db: Session,
    campaign: Campaign,
    *,
    earliest_time: datetime | None = None,
) -> datetime:
    tz = _get_timezone(campaign.send_timezone)
    local_earliest = _to_local(earliest_time or datetime.utcnow(), tz)
    window_start_value = campaign.send_time_window_start
    window_end_value = campaign.send_time_window_end
    daily_limit = max(campaign.daily_send_limit, 1)

    candidate_date = local_earliest.date()
    while True:
        window_start_local, window_end_local = _local_window_for_date(
            target_date=candidate_date,
            tz=tz,
            start_value=window_start_value,
            end_value=window_end_value,
        )

        if local_earliest > window_end_local:
            candidate_date += timedelta(days=1)
            continue

        scheduled_count = _count_scheduled_for_local_day(
            db, campaign, target_date=candidate_date
        )
        if scheduled_count >= daily_limit:
            candidate_date += timedelta(days=1)
            local_earliest = datetime.combine(candidate_date, time.min, tzinfo=tz)
            continue

        window_duration = window_end_local - window_start_local
        slot_spacing = window_duration / daily_limit
        slot_time = window_start_local + (slot_spacing * scheduled_count)
        candidate_local = max(local_earliest, slot_time, window_start_local)
        if candidate_local > window_end_local:
            candidate_date += timedelta(days=1)
            local_earliest = datetime.combine(candidate_date, time.min, tzinfo=tz)
            continue

        return candidate_local.astimezone(timezone.utc).replace(tzinfo=None)


def ensure_followups(
    db: Session,
    workspace_id: str,
    lead: Lead,
    campaign: Campaign,
    *,
    start_date: datetime | None = None,
    regenerate: bool = False,
) -> list[Followup]:
    existing_items = (
        db.query(Followup)
        .filter(Followup.lead_id == lead.id, Followup.campaign_id == campaign.id)
        .all()
    )
    if existing_items and not regenerate:
        return sorted(existing_items, key=lambda row: row.step_number)

    company_profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.workspace_id == workspace_id)
        .first()
    )
    if not company_profile:
        raise FollowupGenerationServiceError(
            "Complete company profile before generating follow-ups.",
            status_code=400,
        )

    initial_email = ensure_generated_email(db, workspace_id, lead, campaign)
    sales_insight = ensure_sales_insight(db, lead)
    try:
        drafts = generate_followup_sequence(
            lead_name=lead.name,
            lead_role=lead.role,
            lead_company=lead.company,
            company_name=company_profile.company_name,
            product_description=company_profile.product_description,
            company_industry=company_profile.industry,
            target_market=company_profile.target_market,
            sales_angle=sales_insight.sales_angle,
            value_proposition=sales_insight.value_proposition,
            personalization_notes=sales_insight.personalization_notes,
            message_tone=campaign.message_tone,
            cta_type=campaign.cta_type,
            target_icp=campaign.target_icp,
            initial_subject=initial_email.subject,
            initial_body=initial_email.body,
            start_date=start_date,
            followup_delay_days=campaign.followup_delay_days,
        )
    except Exception:
        record_api_usage_event(
            workspace_id=workspace_id,
            provider="anthropic",
            feature="followup_generation",
            model_name=settings.anthropic_model,
            success=False,
            metadata={"lead_id": lead.id, "campaign_id": campaign.id},
        )
        raise
    record_api_usage(
        db,
        workspace_id=workspace_id,
        provider="anthropic",
        feature="followup_generation",
        model_name=settings.anthropic_model,
        success=True,
        metadata={"lead_id": lead.id, "campaign_id": campaign.id},
    )

    existing_by_step = {item.step_number: item for item in existing_items}
    valid_steps = {draft.step_number for draft in drafts}

    for item in existing_items:
        if item.step_number not in valid_steps:
            db.delete(item)

    stored_items: list[Followup] = []
    for draft in drafts:
        followup = existing_by_step.get(draft.step_number)
        if followup:
            followup.email_subject = draft.email_subject
            followup.email_body = draft.email_body
            followup.scheduled_date = draft.scheduled_date
        else:
            followup = Followup(
                lead_id=lead.id,
                campaign_id=campaign.id,
                step_number=draft.step_number,
                email_subject=draft.email_subject,
                email_body=draft.email_body,
                scheduled_date=draft.scheduled_date,
            )
            db.add(followup)
            db.flush()
        stored_items.append(followup)

    return sorted(stored_items, key=lambda row: row.step_number)


def schedule_campaign_for_lead(
    db: Session,
    workspace_id: str,
    lead: Lead,
    campaign: Campaign,
    *,
    human_approval_enabled: bool = False,
) -> list[ScheduledEmail]:
    existing_items = (
        db.query(ScheduledEmail)
        .filter(ScheduledEmail.lead_id == lead.id, ScheduledEmail.campaign_id == campaign.id)
        .all()
    )
    sent_steps = {item.step_number for item in existing_items if item.status == "SENT"}
    for item in existing_items:
        if item.status != "SENT":
            db.delete(item)
    db.flush()

    initial_send_time = resolve_next_send_time(db, campaign)
    generated_email = ensure_generated_email(db, workspace_id, lead, campaign)
    followups = ensure_followups(
        db,
        workspace_id,
        lead,
        campaign,
        start_date=initial_send_time,
        regenerate=True,
    )

    scheduled_items: list[ScheduledEmail] = []
    if 0 not in sent_steps:
        initial_item = ScheduledEmail(
            lead_id=lead.id,
            campaign_id=campaign.id,
            step_number=0,
            email_type=INITIAL_EMAIL_TYPE,
            draft_subject=generated_email.subject,
            draft_body=generated_email.body,
            scheduled_for=initial_send_time,
            status="PENDING",
            approval_status=default_approval_status(human_approval_enabled),
        )
        db.add(initial_item)
        db.flush()
        scheduled_items.append(initial_item)

    for followup in followups:
        if followup.step_number in sent_steps:
            continue

        scheduled_for = resolve_next_send_time(
            db, campaign, earliest_time=followup.scheduled_date
        )
        followup.scheduled_date = scheduled_for
        item = ScheduledEmail(
            lead_id=lead.id,
            campaign_id=campaign.id,
            step_number=followup.step_number,
            email_type=FOLLOWUP_EMAIL_TYPE,
            draft_subject=followup.email_subject,
            draft_body=followup.email_body,
            scheduled_for=scheduled_for,
            status="PENDING",
            approval_status=default_approval_status(human_approval_enabled),
        )
        db.add(item)
        db.flush()
        scheduled_items.append(item)

    campaign.status = "SCHEDULED"
    return sorted(scheduled_items, key=lambda row: row.step_number)
