from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.lead import Lead
from app.models.sales_insight import SalesInsight
from app.schemas.sales_insights import SalesInsightResponse
from app.services.insight_pipeline import ensure_sales_insight
from app.services.lead_research import LeadResearchServiceError
from app.services.sales_insight import SalesInsightServiceError
from app.utils.auth import get_current_user

router = APIRouter()


@router.post("/generate/{lead_id}", response_model=SalesInsightResponse)
def generate_sales_insight_endpoint(
    lead_id: str,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SalesInsightResponse:
    _, workspace = current

    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.workspace_id == workspace.id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    try:
        sales_insight = ensure_sales_insight(db, lead)
    except (LeadResearchServiceError, SalesInsightServiceError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    db.commit()
    db.refresh(sales_insight)

    return SalesInsightResponse(
        id=sales_insight.id,
        lead_id=sales_insight.lead_id,
        sales_angle=sales_insight.sales_angle,
        value_proposition=sales_insight.value_proposition,
        personalization_notes=sales_insight.personalization_notes,
        created_at=sales_insight.created_at,
        updated_at=sales_insight.updated_at,
    )
