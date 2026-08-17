from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.campaign import Campaign
from app.models.generated_email import GeneratedEmail
from app.models.lead import Lead
from app.models.lead_insight import LeadInsight
from app.models.onboarding import CompanyProfile, IdealCustomerProfile
from app.models.sales_insight import SalesInsight
from app.services.activity_logs import EVENT_EMAIL_GENERATED, record_activity_log
from app.services.admin_monitoring import record_api_usage, record_api_usage_event
from app.services.email_generation import generate_email
from app.services.lead_research import generate_lead_insight
from app.services.sales_insight import generate_sales_insight


def ensure_lead_insight(db: Session, lead: Lead) -> LeadInsight:
    insight = db.query(LeadInsight).filter(LeadInsight.lead_id == lead.id).first()
    if insight:
        return insight

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
    except Exception:
        record_api_usage_event(
            workspace_id=lead.workspace_id,
            provider="gemini",
            feature="lead_research",
            model_name=settings.gemini_model,
            success=False,
            metadata={"lead_id": lead.id},
        )
        raise
    record_api_usage(
        db,
        workspace_id=lead.workspace_id,
        provider="gemini",
        feature="lead_research",
        model_name=settings.gemini_model,
        success=True,
        metadata={"lead_id": lead.id},
    )

    insight = LeadInsight(
        lead_id=lead.id,
        role_category=payload.role_category,
        possible_pain_points=payload.possible_pain_points,
        recommended_sales_angle=payload.recommended_sales_angle,
        confidence_score=payload.confidence_score,
    )
    db.add(insight)
    db.flush()
    return insight


def ensure_sales_insight(db: Session, lead: Lead) -> SalesInsight:
    sales_insight = db.query(SalesInsight).filter(SalesInsight.lead_id == lead.id).first()
    if sales_insight:
        return sales_insight

    lead_insight = ensure_lead_insight(db, lead)

    company = lead.company_record
    company_industry = None
    company_description = None
    product_summary = None
    if company and company.research_completed:
        company_industry = company.industry
        company_description = company.description
        product_summary = company.product_summary

    icp = (
        db.query(IdealCustomerProfile)
        .filter(IdealCustomerProfile.workspace_id == lead.workspace_id)
        .first()
    )

    try:
        payload = generate_sales_insight(
            lead_name=lead.name,
            lead_role=lead.role,
            company_name=lead.company,
            company_industry=company_industry,
            company_description=company_description,
            company_product_summary=product_summary,
            role_category=lead_insight.role_category,
            possible_pain_points=lead_insight.possible_pain_points or [],
            recommended_sales_angle=lead_insight.recommended_sales_angle,
            confidence_score=lead_insight.confidence_score,
            icp_target_industry=icp.target_industry if icp else None,
            icp_target_company_size=icp.target_company_size if icp else None,
            icp_target_roles=icp.target_roles if icp else None,
            icp_target_region=icp.target_region if icp else None,
            icp_pain_points=icp.pain_points if icp else None,
        )
    except Exception:
        record_api_usage_event(
            workspace_id=lead.workspace_id,
            provider="gemini",
            feature="sales_insight",
            model_name=settings.gemini_model,
            success=False,
            metadata={"lead_id": lead.id},
        )
        raise
    record_api_usage(
        db,
        workspace_id=lead.workspace_id,
        provider="gemini",
        feature="sales_insight",
        model_name=settings.gemini_model,
        success=True,
        metadata={"lead_id": lead.id},
    )

    sales_insight = SalesInsight(
        lead_id=lead.id,
        sales_angle=payload.sales_angle,
        value_proposition=payload.value_proposition,
        personalization_notes=payload.personalization_notes,
    )
    db.add(sales_insight)
    db.flush()
    return sales_insight


def ensure_generated_email(
    db: Session,
    workspace_id: str,
    lead: Lead,
    campaign: Campaign,
    *,
    regenerate: bool = False,
) -> GeneratedEmail:
    generated_email = (
        db.query(GeneratedEmail)
        .filter(
            GeneratedEmail.lead_id == lead.id,
            GeneratedEmail.campaign_id == campaign.id,
        )
        .first()
    )
    if generated_email and not regenerate:
        return generated_email

    company_profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.workspace_id == workspace_id)
        .first()
    )
    if not company_profile:
        from app.services.email_generation import EmailGenerationServiceError

        raise EmailGenerationServiceError(
            "Complete company profile before generating email.",
            status_code=400,
        )

    sales_insight = ensure_sales_insight(db, lead)
    try:
        payload = generate_email(
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
        )
    except Exception:
        record_api_usage_event(
            workspace_id=workspace_id,
            provider="anthropic",
            feature="email_generation",
            model_name=settings.anthropic_model,
            success=False,
            metadata={"lead_id": lead.id, "campaign_id": campaign.id},
        )
        raise
    record_api_usage(
        db,
        workspace_id=workspace_id,
        provider="anthropic",
        feature="email_generation",
        model_name=settings.anthropic_model,
        success=True,
        metadata={"lead_id": lead.id, "campaign_id": campaign.id},
    )

    if generated_email:
        generated_email.subject = payload.subject
        generated_email.body = payload.body
        generated_email.generated_at = datetime.utcnow()
        event_message = f"Generated email draft for {lead.name} in campaign {campaign.name}."
        generation_mode = "regenerated"
    else:
        generated_email = GeneratedEmail(
            lead_id=lead.id,
            campaign_id=campaign.id,
            subject=payload.subject,
            body=payload.body,
            generated_at=datetime.utcnow(),
        )
        db.add(generated_email)
        event_message = f"Generated email draft for {lead.name} in campaign {campaign.name}."
        generation_mode = "created"
    db.flush()
    record_activity_log(
        db,
        workspace_id=workspace_id,
        lead_id=lead.id,
        campaign_id=campaign.id,
        event_type=EVENT_EMAIL_GENERATED,
        message=event_message,
        metadata={
            "generated_email_id": generated_email.id,
            "subject": generated_email.subject,
            "mode": generation_mode,
        },
    )
    return generated_email
