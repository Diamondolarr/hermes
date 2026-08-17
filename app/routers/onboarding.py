from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.onboarding import CompanyProfile, IdealCustomerProfile
from app.schemas.auth import MessageResponse
from app.schemas.onboarding import (
    CompanyProfileRequest,
    CompanyProfileResponse,
    IdealCustomerProfileRequest,
    IdealCustomerProfileResponse,
    OnboardingStatusResponse,
)
from app.utils.auth import get_current_user

router = APIRouter()


@router.get("/company-profile", response_model=CompanyProfileResponse)
def get_company_profile(
    current=Depends(get_current_user), db: Session = Depends(get_db)
) -> CompanyProfileResponse:
    _, workspace = current
    company_profile = (
        db.query(CompanyProfile).filter(CompanyProfile.workspace_id == workspace.id).first()
    )

    if not company_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found.",
        )

    return CompanyProfileResponse(
        company_name=company_profile.company_name,
        company_website=company_profile.company_website,
        product_description=company_profile.product_description,
        industry=company_profile.industry,
        target_market=company_profile.target_market,
    )


@router.get(
    "/ideal-customer-profile",
    response_model=IdealCustomerProfileResponse,
)
def get_ideal_customer_profile(
    current=Depends(get_current_user), db: Session = Depends(get_db)
) -> IdealCustomerProfileResponse:
    _, workspace = current
    ideal_profile = (
        db.query(IdealCustomerProfile)
        .filter(IdealCustomerProfile.workspace_id == workspace.id)
        .first()
    )

    if not ideal_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ideal customer profile not found.",
        )

    return IdealCustomerProfileResponse(
        target_industry=ideal_profile.target_industry,
        target_company_size=ideal_profile.target_company_size,
        target_roles=ideal_profile.target_roles,
        target_region=ideal_profile.target_region,
        pain_points=ideal_profile.pain_points,
    )


@router.get("/status", response_model=OnboardingStatusResponse)
def onboarding_status(
    current=Depends(get_current_user), db: Session = Depends(get_db)
) -> OnboardingStatusResponse:
    _, workspace = current
    company_profile = (
        db.query(CompanyProfile).filter(CompanyProfile.workspace_id == workspace.id).first()
    )
    ideal_profile = (
        db.query(IdealCustomerProfile)
        .filter(IdealCustomerProfile.workspace_id == workspace.id)
        .first()
    )

    completed = bool(company_profile and ideal_profile)
    if completed and not workspace.onboarding_completed:
        workspace.onboarding_completed = True
        db.commit()
    elif not completed and workspace.onboarding_completed:
        workspace.onboarding_completed = False
        db.commit()

    if completed:
        next_step = "completed"
    elif not company_profile:
        next_step = "company_profile"
    else:
        next_step = "ideal_customer_profile"

    return OnboardingStatusResponse(
        workspace_id=workspace.id,
        onboarding_completed=completed,
        next_step=next_step,
    )


@router.post("/company-profile", response_model=MessageResponse)
def upsert_company_profile(
    payload: CompanyProfileRequest,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    _, workspace = current
    company_profile = (
        db.query(CompanyProfile).filter(CompanyProfile.workspace_id == workspace.id).first()
    )

    if company_profile:
        company_profile.company_name = payload.company_name
        company_profile.company_website = payload.company_website
        company_profile.product_description = payload.product_description
        company_profile.industry = payload.industry
        company_profile.target_market = payload.target_market
    else:
        company_profile = CompanyProfile(
            workspace_id=workspace.id,
            company_name=payload.company_name,
            company_website=payload.company_website,
            product_description=payload.product_description,
            industry=payload.industry,
            target_market=payload.target_market,
        )
        db.add(company_profile)

    db.commit()
    return MessageResponse(message="Company profile saved.")


@router.post("/ideal-customer-profile", response_model=MessageResponse)
def upsert_ideal_customer_profile(
    payload: IdealCustomerProfileRequest,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    _, workspace = current
    company_profile = (
        db.query(CompanyProfile).filter(CompanyProfile.workspace_id == workspace.id).first()
    )
    if not company_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete company profile first.",
        )

    ideal_profile = (
        db.query(IdealCustomerProfile)
        .filter(IdealCustomerProfile.workspace_id == workspace.id)
        .first()
    )

    if ideal_profile:
        ideal_profile.target_industry = payload.target_industry
        ideal_profile.target_company_size = payload.target_company_size
        ideal_profile.target_roles = payload.target_roles
        ideal_profile.target_region = payload.target_region
        ideal_profile.pain_points = payload.pain_points
    else:
        ideal_profile = IdealCustomerProfile(
            workspace_id=workspace.id,
            target_industry=payload.target_industry,
            target_company_size=payload.target_company_size,
            target_roles=payload.target_roles,
            target_region=payload.target_region,
            pain_points=payload.pain_points,
        )
        db.add(ideal_profile)

    workspace.onboarding_completed = True
    db.commit()
    return MessageResponse(message="Ideal customer profile saved.")
