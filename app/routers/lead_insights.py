from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.lead import Lead
from app.models.lead_insight import LeadInsight
from app.schemas.lead_insights import LeadInsightResponse
from app.services.admin_monitoring import record_api_usage, record_api_usage_event
from app.services.lead_research import (
    LeadResearchServiceError,
    generate_lead_insight,
)
from app.core.config import settings
from app.utils.auth import get_current_user

router = APIRouter()


@router.post("/generate/{lead_id}", response_model=LeadInsightResponse)
def generate_lead_insight_endpoint(
    lead_id: str,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadInsightResponse:
    _, workspace = current

    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.workspace_id == workspace.id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    company = lead.company_record
    company_industry = None
    company_description = None
    product_summary = None
    if company and company.research_completed:
        company_industry = company.industry
        company_description = company.description
        product_summary = company.product_summary

    try:
        payload = generate_lead_insight(
            lead_name=lead.name,
            lead_role=lead.role,
            company_name=lead.company,
            company_industry=company_industry,
            company_description=company_description,
            product_summary=product_summary,
        )
    except LeadResearchServiceError as exc:
        record_api_usage_event(
            workspace_id=workspace.id,
            provider="gemini",
            feature="lead_research",
            model_name=settings.gemini_model,
            success=False,
            metadata={"lead_id": lead.id},
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    record_api_usage(
        db,
        workspace_id=workspace.id,
        provider="gemini",
        feature="lead_research",
        model_name=settings.gemini_model,
        success=True,
        metadata={"lead_id": lead.id},
    )

    insight = db.query(LeadInsight).filter(LeadInsight.lead_id == lead.id).first()
    if insight:
        insight.role_category = payload.role_category
        insight.possible_pain_points = payload.possible_pain_points
        insight.recommended_sales_angle = payload.recommended_sales_angle
        insight.confidence_score = payload.confidence_score
    else:
        insight = LeadInsight(
            lead_id=lead.id,
            role_category=payload.role_category,
            possible_pain_points=payload.possible_pain_points,
            recommended_sales_angle=payload.recommended_sales_angle,
            confidence_score=payload.confidence_score,
        )
        db.add(insight)
        db.flush()

    db.commit()
    db.refresh(insight)

    return LeadInsightResponse(
        id=insight.id,
        lead_id=insight.lead_id,
        role_category=insight.role_category,
        possible_pain_points=insight.possible_pain_points,
        recommended_sales_angle=insight.recommended_sales_angle,
        confidence_score=insight.confidence_score,
        created_at=insight.created_at,
        updated_at=insight.updated_at,
    )
