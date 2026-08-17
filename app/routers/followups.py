from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.schemas.followups import FollowupResponse, FollowupSequenceResponse
from app.services.email_generation import EmailGenerationServiceError
from app.services.followup_generation import FollowupGenerationServiceError
from app.services.email_scheduling import ensure_followups
from app.services.lead_research import LeadResearchServiceError
from app.services.sales_insight import SalesInsightServiceError
from app.utils.auth import get_current_user

router = APIRouter()


@router.post("/generate/{campaign_id}/{lead_id}", response_model=FollowupSequenceResponse)
def generate_followups_endpoint(
    campaign_id: str,
    lead_id: str,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FollowupSequenceResponse:
    _, workspace = current

    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.workspace_id == workspace.id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.workspace_id == workspace.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    try:
        stored_items = ensure_followups(
            db,
            workspace.id,
            lead,
            campaign,
            regenerate=True,
        )
    except EmailGenerationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except FollowupGenerationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except (LeadResearchServiceError, SalesInsightServiceError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    db.commit()
    for item in stored_items:
        db.refresh(item)

    response_items = [
        FollowupResponse(
            id=item.id,
            lead_id=item.lead_id,
            campaign_id=item.campaign_id,
            step_number=item.step_number,
            email_subject=item.email_subject,
            email_body=item.email_body,
            scheduled_date=item.scheduled_date,
        )
        for item in sorted(stored_items, key=lambda row: row.step_number)
    ]

    return FollowupSequenceResponse(
        lead_id=lead.id,
        campaign_id=campaign.id,
        items=response_items,
    )
