import { apiRequest } from "@/lib/api";

export type DashboardRecentReplyItem = {
  id: string;
  lead_id: string;
  lead_name: string;
  company: string;
  category: string | null;
  preview: string;
  received_at: string;
};

export type DashboardPendingApprovalItem = {
  scheduled_email_id: string;
  lead_id: string;
  lead_name: string;
  campaign_id: string;
  campaign_name: string;
  scheduled_for: string;
  step_number: number;
};

export type DashboardCampaignSnapshotItem = {
  campaign_id: string;
  name: string;
  status: string;
  emails_sent: number;
  replies: number;
  reply_rate: number;
};

export type DashboardNotificationPreviewItem = {
  id: string;
  event_type: string;
  title: string;
  body: string;
  created_at: string;
};

export type DashboardActivityItem = {
  id: string;
  event_type: string;
  message: string;
  created_at: string;
};

export type DashboardSummaryResponse = {
  leads: number;
  active_campaigns: number;
  emails_sent: number;
  replies: number;
  meetings: number;
  pending_approvals_count: number;
  unread_notifications_count: number;
  connected_email_accounts: number;
  recent_replies: DashboardRecentReplyItem[];
  pending_approvals: DashboardPendingApprovalItem[];
  active_campaigns_snapshot: DashboardCampaignSnapshotItem[];
  notifications_preview: DashboardNotificationPreviewItem[];
  recent_activity: DashboardActivityItem[];
};

export function getDashboardSummary(accessToken: string) {
  return apiRequest<DashboardSummaryResponse>("/dashboard/summary", {
    method: "GET",
    accessToken,
  });
}
