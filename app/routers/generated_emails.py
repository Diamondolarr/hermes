from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.schemas.generated_emails import GeneratedEmailResponse
from app.services.email_generation import EmailGenerationServiceError
from app.services.insight_pipeline import ensure_generated_email
from app.services.lead_research import LeadResearchServiceError
from app.services.sales_insight import SalesInsightServiceError
from app.utils.auth import get_current_user

router = APIRouter()


@router.post("/generate/{campaign_id}/{lead_id}", response_model=GeneratedEmailResponse)
def generate_email_endpoint(
    campaign_id: str,
    lead_id: str,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneratedEmailResponse:
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
        generated_email = ensure_generated_email(
            db, workspace.id, lead, campaign, regenerate=True
        )
    except EmailGenerationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except (LeadResearchServiceError, SalesInsightServiceError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    db.commit()
    db.refresh(generated_email)

    return GeneratedEmailResponse(
        id=generated_email.id,
        lead_id=generated_email.lead_id,
        campaign_id=generated_email.campaign_id,
        subject=generated_email.subject,
        body=generated_email.body,
        generated_at=generated_email.generated_at,
    )
