import csv
import io
from datetime import datetime
from typing import Dict, List

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.activity_log import ActivityLog
from app.models.campaign import Campaign
from app.models.company import Company
from app.models.conversation_memory import ConversationMemory
from app.models.email_reply import EmailReply
from app.models.followup import Followup
from app.models.generated_email import GeneratedEmail
from app.models.lead import Lead
from app.models.note import Note
from app.models.scheduled_email import ScheduledEmail
from app.models.sent_email import SentEmail
from app.schemas.lead_detail import (
    LeadDetailCampaignAssociation,
    LeadDetailCampaignOption,
    LeadDetailCompanyResearch,
    LeadDetailFollowup,
    LeadDetailGeneratedEmail,
    LeadDetailGeneratedReply,
    LeadDetailLeadInsight,
    LeadDetailLeadSummary,
    LeadDetailMeeting,
    LeadDetailMemoryItem,
    LeadDetailNote,
    LeadDetailReply,
    LeadDetailResponse,
    LeadDetailSalesInsight,
    LeadDetailScheduledEmail,
    LeadDetailSentEmail,
    LeadDetailTimelineItem,
)
from app.schemas.leads import (
    LeadImportError,
    LeadImportResponse,
    LeadListItem,
    LeadListResponse,
)
from app.services.company_research import websites_match
from app.utils.auth import get_current_user

router = APIRouter()

MAX_ROWS = 10_000
MAX_FILE_BYTES = 20 * 1024 * 1024
BATCH_SIZE = 500
REQUIRED_COLUMNS = {
    "name",
    "email",
    "company",
    "role",
    "website",
    "linkedin_url",
}


def _normalize_field(value: str) -> str:
    return value.strip()


def _normalize_email(value: str) -> str:
    email = validate_email(value, check_deliverability=False).email
    return email.strip().lower()


def _resolve_company_id(
    companies: List[Company], company_name: str, website: str
) -> str | None:
    normalized_name = company_name.strip().lower()
    for company in companies:
        if company.name.strip().lower() == normalized_name:
            return company.id
        if websites_match(company.website, website):
            return company.id
    return None


def _research_state(lead: Lead) -> str:
    if lead.insight:
        return "Lead researched"
    if lead.company_record and lead.company_record.research_completed:
        return "Company researched"
    return "Not started"


def _truncate(value: str, limit: int = 240) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3].rstrip()}..."


@router.get("", response_model=LeadListResponse)
def list_leads(
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    company: str | None = Query(default=None),
    role: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadListResponse:
    _, workspace = current

    query = db.query(Lead).filter(Lead.workspace_id == workspace.id)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            Lead.name.ilike(pattern)
            | Lead.email.ilike(pattern)
            | Lead.company.ilike(pattern)
            | Lead.role.ilike(pattern)
        )

    if status_filter:
        query = query.filter(Lead.status == status_filter.strip().upper())

    if company:
        query = query.filter(Lead.company.ilike(f"%{company.strip()}%"))

    if role:
        query = query.filter(Lead.role.ilike(f"%{role.strip()}%"))

    leads = query.order_by(Lead.created_at.desc()).limit(limit).all()
    total = query.count()

    lead_ids = [lead.id for lead in leads]
    if not lead_ids:
        return LeadListResponse(items=[], total=0)

    activity_rows = (
        db.query(ActivityLog.lead_id, func.max(ActivityLog.created_at))
        .filter(ActivityLog.lead_id.in_(lead_ids))
        .group_by(ActivityLog.lead_id)
        .all()
    )
    sent_rows = (
        db.query(SentEmail.lead_id, func.max(SentEmail.sent_at))
        .filter(SentEmail.lead_id.in_(lead_ids))
        .group_by(SentEmail.lead_id)
        .all()
    )
    reply_rows = (
        db.query(EmailReply.lead_id, func.max(EmailReply.received_at))
        .filter(EmailReply.lead_id.in_(lead_ids))
        .group_by(EmailReply.lead_id)
        .all()
    )

    activity_map = {lead_id: timestamp for lead_id, timestamp in activity_rows}
    sent_map = {lead_id: timestamp for lead_id, timestamp in sent_rows}
    reply_map = {lead_id: timestamp for lead_id, timestamp in reply_rows}

    def last_activity_for(lead: Lead) -> datetime:
        candidates = [
            lead.created_at,
            activity_map.get(lead.id),
            sent_map.get(lead.id),
            reply_map.get(lead.id),
        ]
        return max(candidate for candidate in candidates if candidate is not None)

    items = [
        LeadListItem(
            id=lead.id,
            name=lead.name,
            email=lead.email,
            company=lead.company,
            role=lead.role,
            status=lead.status,
            research_state=_research_state(lead),
            last_activity_at=last_activity_for(lead),
            created_at=lead.created_at,
        )
        for lead in leads
    ]
    items.sort(key=lambda item: item.last_activity_at, reverse=True)

    return LeadListResponse(items=items, total=total)


@router.get("/{lead_id}/detail", response_model=LeadDetailResponse)
def get_lead_detail(
    lead_id: str,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadDetailResponse:
    _, workspace = current

    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.workspace_id == workspace.id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    activity_logs = (
        db.query(ActivityLog)
        .filter(ActivityLog.lead_id == lead.id)
        .order_by(ActivityLog.created_at.desc())
        .all()
    )
    sent_emails = (
        db.query(SentEmail)
        .filter(SentEmail.lead_id == lead.id)
        .order_by(SentEmail.sent_at.desc())
        .all()
    )
    replies = (
        db.query(EmailReply)
        .filter(EmailReply.lead_id == lead.id)
        .order_by(EmailReply.received_at.desc())
        .all()
    )
    notes = (
        db.query(Note)
        .filter(Note.lead_id == lead.id)
        .order_by(Note.created_at.desc())
        .all()
    )
    memory_items = (
        db.query(ConversationMemory)
        .filter(ConversationMemory.lead_id == lead.id)
        .order_by(ConversationMemory.created_at.desc())
        .limit(12)
        .all()
    )
    generated_emails = (
        db.query(GeneratedEmail)
        .filter(GeneratedEmail.lead_id == lead.id)
        .order_by(GeneratedEmail.generated_at.desc())
        .all()
    )
    followups = (
        db.query(Followup)
        .filter(Followup.lead_id == lead.id)
        .order_by(Followup.step_number.asc(), Followup.scheduled_date.asc())
        .all()
    )
    scheduled_emails = (
        db.query(ScheduledEmail)
        .filter(ScheduledEmail.lead_id == lead.id)
        .order_by(ScheduledEmail.scheduled_for.desc())
        .all()
    )
    campaigns = (
        db.query(Campaign)
        .filter(Campaign.workspace_id == workspace.id)
        .order_by(Campaign.created_at.desc())
        .all()
    )
    campaigns_by_id = {campaign.id: campaign for campaign in campaigns}

    last_activity_candidates = [lead.created_at]
    if activity_logs:
        last_activity_candidates.append(activity_logs[0].created_at)
    if sent_emails:
        last_activity_candidates.append(sent_emails[0].sent_at)
    if replies:
        last_activity_candidates.append(replies[0].received_at)
    if notes:
        last_activity_candidates.append(notes[0].created_at)
    if scheduled_emails:
        last_activity_candidates.append(scheduled_emails[0].scheduled_for)

    association_map: dict[str, dict[str, object]] = {}

    def _track_campaign(
        campaign_id: str | None, association_type: str, timestamp: datetime
    ) -> None:
        if not campaign_id or campaign_id not in campaigns_by_id:
            return
        bucket = association_map.setdefault(
            campaign_id,
            {
                "campaign": campaigns_by_id[campaign_id],
                "types": set(),
                "last_activity_at": timestamp,
            },
        )
        bucket["types"].add(association_type)
        if timestamp > bucket["last_activity_at"]:
            bucket["last_activity_at"] = timestamp

    for item in generated_emails:
        _track_campaign(item.campaign_id, "generated_email", item.generated_at)
    for item in followups:
        _track_campaign(item.campaign_id, "followup", item.scheduled_date)
    for item in scheduled_emails:
        _track_campaign(item.campaign_id, "scheduled_email", item.scheduled_for)
    for item in sent_emails:
        _track_campaign(item.campaign_id, "sent_email", item.sent_at)

    company_research = None
    if lead.company_record:
        company_research = LeadDetailCompanyResearch(
            id=lead.company_record.id,
            name=lead.company_record.name,
            website=lead.company_record.website,
            industry=lead.company_record.industry,
            description=lead.company_record.description,
            product_summary=lead.company_record.product_summary,
            research_completed=lead.company_record.research_completed,
        )

    lead_insight = None
    if lead.insight:
        lead_insight = LeadDetailLeadInsight(
            id=lead.insight.id,
            role_category=lead.insight.role_category,
            possible_pain_points=lead.insight.possible_pain_points,
            recommended_sales_angle=lead.insight.recommended_sales_angle,
            confidence_score=lead.insight.confidence_score,
            created_at=lead.insight.created_at,
            updated_at=lead.insight.updated_at,
        )

    sales_insight = None
    if lead.sales_insight:
        sales_insight = LeadDetailSalesInsight(
            id=lead.sales_insight.id,
            sales_angle=lead.sales_insight.sales_angle,
            value_proposition=lead.sales_insight.value_proposition,
            personalization_notes=lead.sales_insight.personalization_notes,
            created_at=lead.sales_insight.created_at,
            updated_at=lead.sales_insight.updated_at,
        )

    meeting = None
    if lead.meeting:
        meeting = LeadDetailMeeting(
            id=lead.meeting.id,
            meeting_link=lead.meeting.meeting_link,
            status=lead.meeting.status,
            scheduled_time=lead.meeting.scheduled_time,
            created_at=lead.meeting.created_at,
        )

    generated_email_items = [
        LeadDetailGeneratedEmail(
            id=item.id,
            campaign_id=item.campaign_id,
            campaign_name=campaigns_by_id[item.campaign_id].name
            if item.campaign_id in campaigns_by_id
            else "Unknown campaign",
            subject=item.subject,
            body=item.body,
            generated_at=item.generated_at,
        )
        for item in generated_emails
    ]

    followup_items = [
        LeadDetailFollowup(
            id=item.id,
            campaign_id=item.campaign_id,
            campaign_name=campaigns_by_id[item.campaign_id].name
            if item.campaign_id in campaigns_by_id
            else "Unknown campaign",
            step_number=item.step_number,
            email_subject=item.email_subject,
            email_body=item.email_body,
            scheduled_date=item.scheduled_date,
        )
        for item in followups
    ]

    scheduled_email_items = [
        LeadDetailScheduledEmail(
            id=item.id,
            campaign_id=item.campaign_id,
            campaign_name=campaigns_by_id[item.campaign_id].name
            if item.campaign_id in campaigns_by_id
            else "Unknown campaign",
            step_number=item.step_number,
            email_type=item.email_type,
            scheduled_for=item.scheduled_for,
            status=item.status,
            approval_status=item.approval_status,
        )
        for item in scheduled_emails
    ]

    sent_email_items = [
        LeadDetailSentEmail(
            id=item.id,
            campaign_id=item.campaign_id,
            campaign_name=campaigns_by_id[item.campaign_id].name
            if item.campaign_id in campaigns_by_id
            else "Unknown campaign",
            subject=item.email_subject,
            body=item.email_body,
            status=item.status,
            sent_at=item.sent_at,
            message_id=item.message_id,
            thread_id=item.thread_id,
        )
        for item in sent_emails
    ]

    reply_items = [
        LeadDetailReply(
            id=item.id,
            body=item.reply_body,
            received_at=item.received_at,
            category=item.classification.category if item.classification else None,
            confidence_score=item.classification.confidence_score
            if item.classification
            else None,
            reason=item.classification.reason if item.classification else None,
            generated_reply=LeadDetailGeneratedReply(
                id=item.generated_reply.id,
                subject=item.generated_reply.subject,
                body=item.generated_reply.body,
                reply_goal=item.generated_reply.reply_goal,
                created_at=item.generated_reply.created_at,
            )
            if item.generated_reply
            else None,
        )
        for item in replies
    ]

    note_items = [
        LeadDetailNote(
            id=item.id,
            content=item.content,
            created_at=item.created_at,
        )
        for item in notes
    ]

    memory_response_items = [
        LeadDetailMemoryItem(
            id=item.id,
            source_type=item.source_type,
            source_id=item.source_id,
            content=_truncate(item.content, 320),
            created_at=item.created_at,
        )
        for item in memory_items
    ]

    timeline: list[LeadDetailTimelineItem] = []
    for item in sent_emails[:6]:
        timeline.append(
            LeadDetailTimelineItem(
                item_type="sent_email",
                title="Email sent",
                content=item.email_subject or "Outbound email sent",
                created_at=item.sent_at,
            )
        )
    for item in replies[:6]:
        timeline.append(
            LeadDetailTimelineItem(
                item_type="reply",
                title="Reply received",
                content=_truncate(item.reply_body, 160),
                created_at=item.received_at,
            )
        )
    for item in notes[:6]:
        timeline.append(
            LeadDetailTimelineItem(
                item_type="note",
                title="Internal note",
                content=_truncate(item.content, 160),
                created_at=item.created_at,
            )
        )
    for item in activity_logs[:6]:
        timeline.append(
            LeadDetailTimelineItem(
                item_type=item.event_type,
                title=item.event_type.replace("_", " ").title(),
                content=_truncate(item.message, 160),
                created_at=item.created_at,
            )
        )

    timeline.sort(key=lambda item: item.created_at, reverse=True)

    campaign_associations = sorted(
        [
            LeadDetailCampaignAssociation(
                campaign_id=campaign_id,
                campaign_name=bucket["campaign"].name,
                campaign_status=bucket["campaign"].status,
                association_types=sorted(bucket["types"]),
                last_activity_at=bucket["last_activity_at"],
            )
            for campaign_id, bucket in association_map.items()
        ],
        key=lambda item: item.last_activity_at,
        reverse=True,
    )

    return LeadDetailResponse(
        lead=LeadDetailLeadSummary(
            id=lead.id,
            name=lead.name,
            email=lead.email,
            company=lead.company,
            role=lead.role,
            website=lead.website,
            linkedin_url=lead.linkedin_url,
            status=lead.status,
            created_at=lead.created_at,
            last_activity_at=max(last_activity_candidates),
        ),
        company_research=company_research,
        lead_insight=lead_insight,
        sales_insight=sales_insight,
        meeting=meeting,
        available_campaigns=[
            LeadDetailCampaignOption(
                id=campaign.id,
                name=campaign.name,
                status=campaign.status,
                message_tone=campaign.message_tone,
            )
            for campaign in campaigns
        ],
        campaign_associations=campaign_associations,
        generated_emails=generated_email_items,
        followups=followup_items,
        scheduled_emails=scheduled_email_items,
        sent_emails=sent_email_items,
        replies=reply_items,
        notes=note_items,
        memory_items=memory_response_items,
        timeline=timeline[:12],
    )


@router.post("/import", response_model=LeadImportResponse)
async def import_leads(
    file: UploadFile = File(...),
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadImportResponse:
    _, workspace = current

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large.",
        )

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV header is missing.")

    reader.fieldnames = [field.strip().lower() for field in reader.fieldnames]
    missing = REQUIRED_COLUMNS.difference(set(reader.fieldnames))
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise HTTPException(status_code=400, detail=f"Missing columns: {missing_list}.")

    sanitized_rows: List[Dict[str, str]] = []
    errors: List[LeadImportError] = []
    total_rows = 0

    for row_index, row in enumerate(reader, start=2):
        total_rows += 1
        if total_rows > MAX_ROWS:
            raise HTTPException(
                status_code=400, detail=f"Row limit exceeded ({MAX_ROWS})."
            )

        def _get(field: str) -> str:
            return _normalize_field(row.get(field, "") or "")

        name = _get("name")
        email_raw = _get("email")
        company = _get("company")
        role = _get("role")
        website = _get("website")
        linkedin_url = _get("linkedin_url")

        if not all([name, email_raw, company, role, website, linkedin_url]):
            errors.append(
                LeadImportError(
                    row_number=row_index, message="Missing required field."
                )
            )
            continue

        try:
            email = _normalize_email(email_raw)
        except EmailNotValidError:
            errors.append(
                LeadImportError(row_number=row_index, message="Invalid email.")
            )
            continue

        sanitized_rows.append(
            {
                "name": name,
                "email": email,
                "company": company,
                "role": role,
                "website": website,
                "linkedin_url": linkedin_url,
            }
        )

    existing_map: Dict[str, Lead] = {}
    companies = db.query(Company).filter(Company.workspace_id == workspace.id).all()
    if sanitized_rows:
        email_list = [row["email"] for row in sanitized_rows]
        existing = (
            db.query(Lead)
            .filter(Lead.workspace_id == workspace.id, Lead.email.in_(email_list))
            .all()
        )
        existing_map = {lead.email: lead for lead in existing}

    inserted = 0
    updated = 0
    pending = 0

    for row in sanitized_rows:
        company_id = _resolve_company_id(companies, row["company"], row["website"])
        existing = existing_map.get(row["email"])
        if existing:
            existing.name = row["name"]
            existing.company = row["company"]
            existing.role = row["role"]
            existing.website = row["website"]
            existing.linkedin_url = row["linkedin_url"]
            existing.company_id = company_id
            updated += 1
        else:
            lead = Lead(
                workspace_id=workspace.id,
                company_id=company_id,
                name=row["name"],
                email=row["email"],
                company=row["company"],
                role=row["role"],
                website=row["website"],
                linkedin_url=row["linkedin_url"],
                status="NEW",
            )
            db.add(lead)
            existing_map[row["email"]] = lead
            inserted += 1

        pending += 1
        if pending >= BATCH_SIZE:
            db.commit()
            pending = 0

    if pending:
        db.commit()

    skipped = len(errors)
    return LeadImportResponse(
        total_rows=total_rows,
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )
