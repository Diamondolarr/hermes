from datetime import datetime

from pydantic import BaseModel


class LeadDetailLeadSummary(BaseModel):
    id: str
    name: str
    email: str
    company: str
    role: str
    website: str
    linkedin_url: str
    status: str
    created_at: datetime
    last_activity_at: datetime


class LeadDetailCompanyResearch(BaseModel):
    id: str
    name: str
    website: str
    industry: str
    description: str
    product_summary: str
    research_completed: bool


class LeadDetailLeadInsight(BaseModel):
    id: str
    role_category: str
    possible_pain_points: list[str]
    recommended_sales_angle: str
    confidence_score: float
    created_at: datetime
    updated_at: datetime


class LeadDetailSalesInsight(BaseModel):
    id: str
    sales_angle: str
    value_proposition: str
    personalization_notes: str
    created_at: datetime
    updated_at: datetime


class LeadDetailCampaignOption(BaseModel):
    id: str
    name: str
    status: str
    message_tone: str


class LeadDetailCampaignAssociation(BaseModel):
    campaign_id: str
    campaign_name: str
    campaign_status: str
    association_types: list[str]
    last_activity_at: datetime


class LeadDetailGeneratedEmail(BaseModel):
    id: str
    campaign_id: str
    campaign_name: str
    subject: str
    body: str
    generated_at: datetime


class LeadDetailFollowup(BaseModel):
    id: str
    campaign_id: str
    campaign_name: str
    step_number: int
    email_subject: str
    email_body: str
    scheduled_date: datetime


class LeadDetailScheduledEmail(BaseModel):
    id: str
    campaign_id: str
    campaign_name: str
    step_number: int
    email_type: str
    scheduled_for: datetime
    status: str
    approval_status: str


class LeadDetailSentEmail(BaseModel):
    id: str
    campaign_id: str
    campaign_name: str
    subject: str | None
    body: str | None
    status: str
    sent_at: datetime
    message_id: str | None
    thread_id: str | None


class LeadDetailGeneratedReply(BaseModel):
    id: str
    subject: str
    body: str
    reply_goal: str
    created_at: datetime


class LeadDetailReply(BaseModel):
    id: str
    body: str
    received_at: datetime
    category: str | None
    confidence_score: float | None
    reason: str | None
    generated_reply: LeadDetailGeneratedReply | None


class LeadDetailNote(BaseModel):
    id: str
    content: str
    created_at: datetime


class LeadDetailMemoryItem(BaseModel):
    id: str
    source_type: str
    source_id: str
    content: str
    created_at: datetime


class LeadDetailMeeting(BaseModel):
    id: str
    meeting_link: str
    status: str
    scheduled_time: datetime | None
    created_at: datetime


class LeadDetailTimelineItem(BaseModel):
    item_type: str
    title: str
    content: str
    created_at: datetime


class LeadDetailResponse(BaseModel):
    lead: LeadDetailLeadSummary
    company_research: LeadDetailCompanyResearch | None
    lead_insight: LeadDetailLeadInsight | None
    sales_insight: LeadDetailSalesInsight | None
    meeting: LeadDetailMeeting | None
    available_campaigns: list[LeadDetailCampaignOption]
    campaign_associations: list[LeadDetailCampaignAssociation]
    generated_emails: list[LeadDetailGeneratedEmail]
    followups: list[LeadDetailFollowup]
    scheduled_emails: list[LeadDetailScheduledEmail]
    sent_emails: list[LeadDetailSentEmail]
    replies: list[LeadDetailReply]
    notes: list[LeadDetailNote]
    memory_items: list[LeadDetailMemoryItem]
    timeline: list[LeadDetailTimelineItem]
