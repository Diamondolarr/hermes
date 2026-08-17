import { apiRequest } from "@/lib/api";

export type LeadListItem = {
  id: string;
  name: string;
  email: string;
  company: string;
  role: string;
  status: string;
  research_state: string;
  last_activity_at: string;
  created_at: string;
};

export type LeadListResponse = {
  items: LeadListItem[];
  total: number;
};

export type LeadImportError = {
  row_number: number;
  message: string;
};

export type LeadImportResponse = {
  total_rows: number;
  inserted: number;
  updated: number;
  skipped: number;
  errors: LeadImportError[];
};

export type LeadListFilters = {
  search?: string;
  status?: string;
  company?: string;
  role?: string;
};

export type LeadDetailLeadSummary = {
  id: string;
  name: string;
  email: string;
  company: string;
  role: string;
  website: string;
  linkedin_url: string;
  status: string;
  created_at: string;
  last_activity_at: string;
};

export type LeadDetailCompanyResearch = {
  id: string;
  name: string;
  website: string;
  industry: string;
  description: string;
  product_summary: string;
  research_completed: boolean;
};

export type LeadDetailLeadInsight = {
  id: string;
  role_category: string;
  possible_pain_points: string[];
  recommended_sales_angle: string;
  confidence_score: number;
  created_at: string;
  updated_at: string;
};

export type LeadDetailSalesInsight = {
  id: string;
  sales_angle: string;
  value_proposition: string;
  personalization_notes: string;
  created_at: string;
  updated_at: string;
};

export type LeadDetailMeeting = {
  id: string;
  meeting_link: string;
  status: string;
  scheduled_time: string | null;
  created_at: string;
};

export type LeadDetailCampaignOption = {
  id: string;
  name: string;
  status: string;
  message_tone: string;
};

export type LeadDetailCampaignAssociation = {
  campaign_id: string;
  campaign_name: string;
  campaign_status: string;
  association_types: string[];
  last_activity_at: string;
};

export type LeadDetailGeneratedEmail = {
  id: string;
  campaign_id: string;
  campaign_name: string;
  subject: string;
  body: string;
  generated_at: string;
};

export type LeadDetailFollowup = {
  id: string;
  campaign_id: string;
  campaign_name: string;
  step_number: number;
  email_subject: string;
  email_body: string;
  scheduled_date: string;
};

export type LeadDetailScheduledEmail = {
  id: string;
  campaign_id: string;
  campaign_name: string;
  step_number: number;
  email_type: string;
  scheduled_for: string;
  status: string;
  approval_status: string;
};

export type LeadDetailSentEmail = {
  id: string;
  campaign_id: string;
  campaign_name: string;
  subject: string | null;
  body: string | null;
  status: string;
  sent_at: string;
  message_id: string | null;
  thread_id: string | null;
};

export type LeadDetailGeneratedReply = {
  id: string;
  subject: string;
  body: string;
  reply_goal: string;
  created_at: string;
};

export type LeadDetailReply = {
  id: string;
  body: string;
  received_at: string;
  category: string | null;
  confidence_score: number | null;
  reason: string | null;
  generated_reply: LeadDetailGeneratedReply | null;
};

export type LeadDetailNote = {
  id: string;
  content: string;
  created_at: string;
};

export type LeadDetailMemoryItem = {
  id: string;
  source_type: string;
  source_id: string;
  content: string;
  created_at: string;
};

export type LeadDetailTimelineItem = {
  item_type: string;
  title: string;
  content: string;
  created_at: string;
};

export type LeadDetailResponse = {
  lead: LeadDetailLeadSummary;
  company_research: LeadDetailCompanyResearch | null;
  lead_insight: LeadDetailLeadInsight | null;
  sales_insight: LeadDetailSalesInsight | null;
  meeting: LeadDetailMeeting | null;
  available_campaigns: LeadDetailCampaignOption[];
  campaign_associations: LeadDetailCampaignAssociation[];
  generated_emails: LeadDetailGeneratedEmail[];
  followups: LeadDetailFollowup[];
  scheduled_emails: LeadDetailScheduledEmail[];
  sent_emails: LeadDetailSentEmail[];
  replies: LeadDetailReply[];
  notes: LeadDetailNote[];
  memory_items: LeadDetailMemoryItem[];
  timeline: LeadDetailTimelineItem[];
};

export type LeadNoteResponse = {
  id: string;
  workspace_id: string;
  lead_id: string;
  content: string;
  created_at: string;
};

function buildLeadQuery(filters: LeadListFilters) {
  const params = new URLSearchParams();

  if (filters.search) params.set("search", filters.search);
  if (filters.status) params.set("status", filters.status);
  if (filters.company) params.set("company", filters.company);
  if (filters.role) params.set("role", filters.role);

  const query = params.toString();
  return query ? `/leads?${query}` : "/leads";
}

export function getLeads(accessToken: string, filters: LeadListFilters) {
  return apiRequest<LeadListResponse>(buildLeadQuery(filters), {
    method: "GET",
    accessToken,
  });
}

export function importLeads(accessToken: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);

  return apiRequest<LeadImportResponse>("/leads/import", {
    method: "POST",
    accessToken,
    body: formData,
    skipJsonContentType: true,
  });
}

export function getLeadDetail(accessToken: string, leadId: string) {
  return apiRequest<LeadDetailResponse>(`/leads/${leadId}/detail`, {
    method: "GET",
    accessToken,
  });
}

export function runCompanyResearch(
  accessToken: string,
  payload: { companyName: string; companyWebsite: string },
) {
  return apiRequest(`/companies/research`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({
      company_name: payload.companyName,
      company_website: payload.companyWebsite,
    }),
  });
}

export function generateLeadInsight(accessToken: string, leadId: string) {
  return apiRequest(`/lead-insights/generate/${leadId}`, {
    method: "POST",
    accessToken,
  });
}

export function generateSalesInsight(accessToken: string, leadId: string) {
  return apiRequest(`/sales-insights/generate/${leadId}`, {
    method: "POST",
    accessToken,
  });
}

export function generateLeadEmail(
  accessToken: string,
  campaignId: string,
  leadId: string,
) {
  return apiRequest(`/generated-emails/generate/${campaignId}/${leadId}`, {
    method: "POST",
    accessToken,
  });
}

export function scheduleLeadOutreach(
  accessToken: string,
  campaignId: string,
  leadId: string,
) {
  return apiRequest(`/campaigns/${campaignId}/schedule/${leadId}`, {
    method: "POST",
    accessToken,
  });
}

export function createLeadNote(
  accessToken: string,
  leadId: string,
  content: string,
) {
  return apiRequest<LeadNoteResponse>(`/memory/notes`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({
      lead_id: leadId,
      content,
    }),
  });
}
