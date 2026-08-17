from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.company import Company
from app.models.lead import Lead
from app.schemas.companies import CompanyResearchRequest, CompanyResponse
from app.services.activity_logs import (
    EVENT_RESEARCH_COMPLETED,
    record_activity_log,
)
from app.services.admin_monitoring import record_api_usage, record_api_usage_event
from app.services.company_research import (
    CompanyResearchServiceError,
    normalize_company_website,
    research_company,
    websites_match,
)
from app.utils.auth import get_current_user

router = APIRouter()


def _link_matching_leads(
    db: Session, workspace_id: str, company: Company, company_name: str
) -> int:
    leads = db.query(Lead).filter(Lead.workspace_id == workspace_id).all()
    normalized_name = company_name.strip().lower()
    linked = 0

    for lead in leads:
        matches_name = lead.company.strip().lower() == normalized_name
        matches_website = websites_match(lead.website, company.website)
        if matches_name or matches_website:
            lead.company_id = company.id
            linked += 1

    return linked


@router.post("/research", response_model=CompanyResponse)
def research_company_endpoint(
    payload: CompanyResearchRequest,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyResponse:
    _, workspace = current

    try:
        normalized_website = normalize_company_website(payload.company_website)
    except CompanyResearchServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    try:
        result = research_company(payload.company_name, normalized_website)
    except CompanyResearchServiceError as exc:
        record_api_usage_event(
            workspace_id=workspace.id,
            provider="gemini",
            feature="company_research",
            model_name=settings.gemini_model,
            success=False,
            metadata={"error": str(exc), "company_website": normalized_website},
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    record_api_usage(
        db,
        workspace_id=workspace.id,
        provider="gemini",
        feature="company_research",
        model_name=settings.gemini_model,
        success=True,
        metadata={"company_website": result.website},
    )

    company = (
        db.query(Company)
        .filter(
            Company.workspace_id == workspace.id,
            Company.website == result.website,
        )
        .first()
    )

    if not company and result.website != normalized_website:
        company = (
            db.query(Company)
            .filter(
                Company.workspace_id == workspace.id,
                Company.website == normalized_website,
            )
            .first()
        )

    if company:
        company.name = payload.company_name.strip()
        company.website = result.website
        company.industry = result.industry
        company.description = result.description
        company.product_summary = result.product_summary
        company.research_completed = True
    else:
        company = Company(
            workspace_id=workspace.id,
            name=payload.company_name.strip(),
            website=result.website,
            industry=result.industry,
            description=result.description,
            product_summary=result.product_summary,
            research_completed=True,
        )
        db.add(company)
        db.flush()

    linked_leads = _link_matching_leads(db, workspace.id, company, payload.company_name)
    record_activity_log(
        db,
        workspace_id=workspace.id,
        event_type=EVENT_RESEARCH_COMPLETED,
        message=f"Completed company research for {company.name}.",
        metadata={
            "company_id": company.id,
            "company_name": company.name,
            "website": company.website,
            "industry": company.industry,
            "linked_leads": linked_leads,
        },
    )
    db.commit()

    return CompanyResponse(
        id=company.id,
        workspace_id=company.workspace_id,
        name=company.name,
        website=company.website,
        industry=company.industry,
        description=company.description,
        product_summary=company.product_summary,
        research_completed=company.research_completed,
        linked_leads=linked_leads,
    )
