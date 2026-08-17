from pydantic import BaseModel, Field


class CompanyResearchRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    company_website: str = Field(min_length=1, max_length=255)


class CompanyResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    website: str
    industry: str
    description: str
    product_summary: str
    research_completed: bool
    linked_leads: int
