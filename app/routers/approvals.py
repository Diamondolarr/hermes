from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.models.scheduled_email import ScheduledEmail
from app.schemas.approvals import (
    ApprovalDecisionRequest,
    HumanApprovalSettingsRequest,
    HumanApprovalSettingsResponse,
    PendingApprovalItemResponse,
)
from app.utils.auth import get_current_user

router = APIRouter()


def _build_pending_item_response(
    item: ScheduledEmail, lead: Lead, campaign: Campaign
) -> PendingApprovalItemResponse:
    return PendingApprovalItemResponse(
        scheduled_email_id=item.id,
        lead_id=lead.id,
        lead_name=lead.name,
        lead_email=lead.email,
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        step_number=item.step_number,
        email_type=item.email_type,
        subject=item.draft_subject or "",
        body=item.draft_body or "",
        scheduled_for=item.scheduled_for,
        status=item.status,
        approval_status=item.approval_status,
        approved_at=item.approved_at,
        rejected_at=item.rejected_at,
        rejection_reason=item.rejection_reason,
    )


@router.get("/settings", response_model=HumanApprovalSettingsResponse)
def get_human_approval_settings(
    current=Depends(get_current_user),
) -> HumanApprovalSettingsResponse:
    _, workspace = current
    return HumanApprovalSettingsResponse(
        human_approval_enabled=workspace.human_approval_enabled
    )


@router.post("/settings", response_model=HumanApprovalSettingsResponse)
def update_human_approval_settings(
    payload: HumanApprovalSettingsRequest,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HumanApprovalSettingsResponse:
    _, workspace = current
    workspace.human_approval_enabled = payload.human_approval_enabled
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return HumanApprovalSettingsResponse(
        human_approval_enabled=workspace.human_approval_enabled
    )


@router.get("/pending", response_model=list[PendingApprovalItemResponse])
def list_pending_approvals(
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PendingApprovalItemResponse]:
    _, workspace = current

    rows = (
        db.query(ScheduledEmail, Lead, Campaign)
        .join(Lead, Lead.id == ScheduledEmail.lead_id)
        .join(Campaign, Campaign.id == ScheduledEmail.campaign_id)
        .filter(
            Campaign.workspace_id == workspace.id,
            ScheduledEmail.approval_status == "PENDING_APPROVAL",
            ScheduledEmail.status != "SENT",
        )
        .order_by(ScheduledEmail.scheduled_for.asc())
        .all()
    )

    return [
        _build_pending_item_response(item, lead, campaign)
        for item, lead, campaign in rows
    ]


@router.post("/{scheduled_email_id}/approve", response_model=PendingApprovalItemResponse)
def approve_scheduled_email(
    scheduled_email_id: str,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PendingApprovalItemResponse:
    user, workspace = current

    row = (
        db.query(ScheduledEmail, Lead, Campaign)
        .join(Lead, Lead.id == ScheduledEmail.lead_id)
        .join(Campaign, Campaign.id == ScheduledEmail.campaign_id)
        .filter(
            ScheduledEmail.id == scheduled_email_id,
            Campaign.workspace_id == workspace.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Scheduled email not found.")

    item, lead, campaign = row
    if item.status == "SENT":
        raise HTTPException(status_code=400, detail="Email has already been sent.")

    item.approval_status = "APPROVED"
    item.approved_by_user_id = user.id
    item.approved_at = datetime.utcnow()
    item.rejected_by_user_id = None
    item.rejected_at = None
    item.rejection_reason = None
    db.commit()
    db.refresh(item)

    return _build_pending_item_response(item, lead, campaign)


@router.post("/{scheduled_email_id}/reject", response_model=PendingApprovalItemResponse)
def reject_scheduled_email(
    scheduled_email_id: str,
    payload: ApprovalDecisionRequest,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PendingApprovalItemResponse:
    user, workspace = current

    row = (
        db.query(ScheduledEmail, Lead, Campaign)
        .join(Lead, Lead.id == ScheduledEmail.lead_id)
        .join(Campaign, Campaign.id == ScheduledEmail.campaign_id)
        .filter(
            ScheduledEmail.id == scheduled_email_id,
            Campaign.workspace_id == workspace.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Scheduled email not found.")

    item, lead, campaign = row
    if item.status == "SENT":
        raise HTTPException(status_code=400, detail="Email has already been sent.")

    item.approval_status = "REJECTED"
    item.approved_by_user_id = None
    item.approved_at = None
    item.rejected_by_user_id = user.id
    item.rejected_at = datetime.utcnow()
    item.rejection_reason = (payload.rejection_reason or "").strip() or None
    db.commit()
    db.refresh(item)

    return _build_pending_item_response(item, lead, campaign)
