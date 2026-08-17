from pydantic import BaseModel, Field


class CompanyProfileRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    company_website: str = Field(min_length=1, max_length=255)
    product_description: str = Field(min_length=1, max_length=1000)
    industry: str = Field(min_length=1, max_length=255)
    target_market: str = Field(min_length=1, max_length=255)


class CompanyProfileResponse(CompanyProfileRequest):
    pass


class IdealCustomerProfileRequest(BaseModel):
    target_industry: str = Field(min_length=1, max_length=255)
    target_company_size: str = Field(min_length=1, max_length=255)
    target_roles: list[str] = Field(min_length=1)
    target_region: str = Field(min_length=1, max_length=255)
    pain_points: list[str] = Field(min_length=1)


class IdealCustomerProfileResponse(IdealCustomerProfileRequest):
    pass


class OnboardingStatusResponse(BaseModel):
    workspace_id: str
    onboarding_completed: bool
    next_step: str
