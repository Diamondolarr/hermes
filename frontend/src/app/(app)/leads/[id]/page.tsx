"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  createLeadNote,
  generateLeadEmail,
  generateLeadInsight,
  generateSalesInsight,
  getLeadDetail,
  runCompanyResearch,
  scheduleLeadOutreach,
} from "@/features/leads/api";
import { useAuth } from "@/lib/auth-context";

type LeadDetailTab = "overview" | "research" | "outreach" | "conversation" | "notes";

const tabs: { id: LeadDetailTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "research", label: "Research" },
  { id: "outreach", label: "Outreach" },
  { id: "conversation", label: "Conversation" },
  { id: "notes", label: "Notes" },
];

function formatDateTime(value?: string | null) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDate(value?: string | null) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function statusTone(status: string) {
  switch (status) {
    case "REPLIED":
    case "MEETING_SCHEDULED":
      return "accent" as const;
    case "CONTACTED":
      return "warm" as const;
    case "CLOSED":
      return "ink" as const;
    default:
      return "neutral" as const;
  }
}

function meetingTone(status: string) {
  switch (status) {
    case "BOOKED":
    case "COMPLETED":
      return "accent" as const;
    case "LINK_SENT":
      return "warm" as const;
    case "CANCELED":
      return "danger" as const;
    default:
      return "neutral" as const;
  }
}

function campaignStatusTone(status: string) {
  switch (status) {
    case "ACTIVE":
      return "accent" as const;
    case "PAUSED":
      return "warning" as const;
    case "COMPLETED":
      return "ink" as const;
    default:
      return "neutral" as const;
  }
}

function summarizeTypes(types: string[]) {
  return types
    .map((value) => value.replaceAll("_", " "))
    .map((value) => value.charAt(0).toUpperCase() + value.slice(1))
    .join(", ");
}

function SectionCard({
  eyebrow,
  title,
  children,
  action,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="panel p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2 className="mt-2 text-2xl font-semibold text-foreground">{title}</h2>
        </div>
        {action}
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function KeyValue({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="rounded-[22px] border border-border/70 bg-white/70 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-muted">{label}</p>
      <div className="mt-2 text-sm leading-6 text-foreground">{value}</div>
    </div>
  );
}

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { session } = useAuth();
  const accessToken = session?.accessToken ?? null;
  const leadId = params.id;

  const [activeTab, setActiveTab] = useState<LeadDetailTab>("overview");
  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [noteDraft, setNoteDraft] = useState("");

  const detailQuery = useQuery({
    queryKey: ["lead-detail", leadId],
    queryFn: () => getLeadDetail(accessToken as string, leadId),
    enabled: Boolean(accessToken && leadId),
  });

  const detail = detailQuery.data;

  useEffect(() => {
    if (!detail?.available_campaigns.length) {
      setSelectedCampaignId("");
      return;
    }

    setSelectedCampaignId((current) => {
      if (current && detail.available_campaigns.some((campaign) => campaign.id === current)) {
        return current;
      }
      return detail.available_campaigns[0]?.id ?? "";
    });
  }, [detail?.available_campaigns]);

  const selectedCampaign = useMemo(
    () => detail?.available_campaigns.find((campaign) => campaign.id === selectedCampaignId) ?? null,
    [detail?.available_campaigns, selectedCampaignId],
  );

  async function refreshLeadSurface() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["lead-detail", leadId] }),
      queryClient.invalidateQueries({ queryKey: ["leads"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] }),
    ]);
  }

  const researchMutation = useMutation({
    mutationFn: async () => {
      if (!accessToken || !detail) {
        throw new Error("We need an authenticated session to run research.");
      }

      if (detail.lead.company && detail.lead.website) {
        await runCompanyResearch(accessToken, {
          companyName: detail.lead.company,
          companyWebsite: detail.lead.website,
        });
      }

      await generateLeadInsight(accessToken, leadId);
      await generateSalesInsight(accessToken, leadId);
    },
    onSuccess: refreshLeadSurface,
  });

  const emailMutation = useMutation({
    mutationFn: async () => {
      if (!accessToken) {
        throw new Error("We need an authenticated session to generate email.");
      }
      if (!selectedCampaignId) {
        throw new Error("Choose a campaign before generating an email.");
      }
      return generateLeadEmail(accessToken, selectedCampaignId, leadId);
    },
    onSuccess: refreshLeadSurface,
  });

  const scheduleMutation = useMutation({
    mutationFn: async () => {
      if (!accessToken) {
        throw new Error("We need an authenticated session to schedule outreach.");
      }
      if (!selectedCampaignId) {
        throw new Error("Choose a campaign before scheduling outreach.");
      }
      return scheduleLeadOutreach(accessToken, selectedCampaignId, leadId);
    },
    onSuccess: refreshLeadSurface,
  });

  const noteMutation = useMutation({
    mutationFn: async () => {
      if (!accessToken) {
        throw new Error("We need an authenticated session to save a note.");
      }

      const content = noteDraft.trim();
      if (!content) {
        throw new Error("Write a short note before saving.");
      }

      return createLeadNote(accessToken, leadId, content);
    },
    onSuccess: async () => {
      setNoteDraft("");
      await refreshLeadSurface();
    },
  });

  if (detailQuery.isLoading) {
    return (
      <div className="panel-strong flex min-h-[calc(100vh-10rem)] items-center justify-center p-8 text-center">
        <div>
          <p className="eyebrow">Lead Surface</p>
          <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground">
            Loading the lead workspace.
          </h1>
          <p className="mt-4 max-w-xl text-lg text-muted">
            We are pulling research, outreach, conversation history, and notes into one place now.
          </p>
        </div>
      </div>
    );
  }

  if (detailQuery.isError || !detail) {
    return (
      <div className="panel-strong flex min-h-[calc(100vh-10rem)] items-center justify-center p-8 text-center">
        <div>
          <p className="eyebrow">Lead Surface</p>
          <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground">
            We hit a lead detail snag.
          </h1>
          <p className="mt-4 max-w-xl text-lg text-muted">
            {detailQuery.error?.message ?? "We could not load this lead record."}
          </p>
          <button
            className="primary-button mt-6 inline-flex h-11 items-center px-5 font-semibold"
            type="button"
            onClick={() => detailQuery.refetch()}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="panel-strong p-6 sm:p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="eyebrow">Lead Surface</p>
            <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground sm:text-5xl">
              {detail.lead.name}
            </h1>
            <p className="mt-4 max-w-2xl text-lg leading-7 text-muted">
              This page pulls company research, lead insight, outreach drafts, conversation history, and internal memory into one operating surface.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              className="primary-button inline-flex h-11 items-center px-5 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
              type="button"
              disabled={researchMutation.isPending}
              onClick={() => researchMutation.mutate()}
            >
              {researchMutation.isPending ? "Running research..." : "Run research"}
            </button>
            <button
              className="secondary-button inline-flex h-11 items-center px-5 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
              type="button"
              disabled={emailMutation.isPending || !selectedCampaignId}
              onClick={() => emailMutation.mutate()}
            >
              {emailMutation.isPending ? "Generating..." : "Generate email"}
            </button>
            <button
              className="secondary-button inline-flex h-11 items-center px-5 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
              type="button"
              disabled={scheduleMutation.isPending || !selectedCampaignId}
              onClick={() => scheduleMutation.mutate()}
            >
              {scheduleMutation.isPending ? "Scheduling..." : "Schedule outreach"}
            </button>
            <Link
              href={`/inbox?leadId=${detail.lead.id}`}
              className="secondary-button inline-flex h-11 items-center px-5 font-semibold"
            >
              Open inbox context
            </Link>
          </div>
        </div>

        {researchMutation.isError ? (
          <div className="mt-5 rounded-[22px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            {researchMutation.error.message}
          </div>
        ) : null}
        {emailMutation.isError ? (
          <div className="mt-5 rounded-[22px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            {emailMutation.error.message}
          </div>
        ) : null}
        {scheduleMutation.isError ? (
          <div className="mt-5 rounded-[22px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            {scheduleMutation.error.message}
          </div>
        ) : null}
      </section>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.55fr_0.95fr]">
        <aside className="space-y-4">
          <section className="panel p-5">
            <p className="eyebrow">Summary Rail</p>
            <h2 className="mt-2 text-2xl font-semibold text-foreground">Lead identity</h2>
            <div className="mt-5 space-y-4">
              <div className="rounded-[24px] border border-border/70 bg-white/75 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-lg font-semibold text-foreground">{detail.lead.name}</p>
                    <p className="mt-1 text-sm text-muted">{detail.lead.role}</p>
                  </div>
                  <StatusBadge tone={statusTone(detail.lead.status)}>{detail.lead.status}</StatusBadge>
                </div>
                <div className="mt-4 space-y-2 text-sm text-muted">
                  <p>{detail.lead.email}</p>
                  <p>{detail.lead.company}</p>
                  <p>Created {formatDate(detail.lead.created_at)}</p>
                  <p>Last activity {formatDateTime(detail.lead.last_activity_at)}</p>
                </div>
              </div>

              <KeyValue label="Company" value={detail.lead.company} />
              <KeyValue
                label="Website"
                value={
                  detail.lead.website ? (
                    <a
                      href={detail.lead.website}
                      target="_blank"
                      rel="noreferrer"
                      className="text-accent underline decoration-accent/30 underline-offset-4"
                    >
                      {detail.lead.website}
                    </a>
                  ) : (
                    "No website captured yet"
                  )
                }
              />
              <KeyValue
                label="LinkedIn"
                value={
                  detail.lead.linkedin_url ? (
                    <a
                      href={detail.lead.linkedin_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-accent underline decoration-accent/30 underline-offset-4"
                    >
                      Open profile
                    </a>
                  ) : (
                    "No LinkedIn URL captured yet"
                  )
                }
              />
              <div className="rounded-[22px] border border-border/70 bg-white/70 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted">Meeting status</p>
                <div className="mt-3">
                  {detail.meeting ? (
                    <div className="space-y-3">
                      <StatusBadge tone={meetingTone(detail.meeting.status)}>{detail.meeting.status}</StatusBadge>
                      <p className="text-sm text-muted">
                        {detail.meeting.scheduled_time
                          ? `Scheduled ${formatDateTime(detail.meeting.scheduled_time)}`
                          : "Meeting link is ready to share."}
                      </p>
                      <a
                        href={detail.meeting.meeting_link}
                        target="_blank"
                        rel="noreferrer"
                        className="secondary-button inline-flex h-10 items-center px-4 text-sm font-semibold"
                      >
                        Open meeting link
                      </a>
                    </div>
                  ) : (
                    <p className="text-sm text-muted">No meeting signal yet. Once interest shows up, the scheduling path will appear here.</p>
                  )}
                </div>
              </div>
            </div>
          </section>

          <section className="panel p-5">
            <p className="eyebrow">Quick Actions</p>
            <h2 className="mt-2 text-2xl font-semibold text-foreground">Work the record</h2>
            <div className="mt-5 grid gap-3">
              <button
                className="primary-button inline-flex h-11 items-center justify-center px-5 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                type="button"
                disabled={researchMutation.isPending}
                onClick={() => researchMutation.mutate()}
              >
                Run research
              </button>
              <button
                className="secondary-button inline-flex h-11 items-center justify-center px-5 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                type="button"
                disabled={emailMutation.isPending || !selectedCampaignId}
                onClick={() => emailMutation.mutate()}
              >
                Generate email
              </button>
              <button
                className="secondary-button inline-flex h-11 items-center justify-center px-5 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                type="button"
                disabled={scheduleMutation.isPending || !selectedCampaignId}
                onClick={() => scheduleMutation.mutate()}
              >
                Schedule outreach
              </button>
              <Link
                href={`/inbox?leadId=${detail.lead.id}`}
                className="secondary-button inline-flex h-11 items-center justify-center px-5 font-semibold"
              >
                Open inbox context
              </Link>
            </div>
          </section>
        </aside>

        <main className="space-y-4">
          <section className="panel p-4">
            <div className="flex flex-wrap gap-2">
              {tabs.map((tab) => {
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    className={
                      isActive
                        ? "primary-button inline-flex h-11 items-center px-5 text-sm font-semibold"
                        : "secondary-button inline-flex h-11 items-center px-5 text-sm font-semibold"
                    }
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </section>

          {activeTab === "overview" ? (
            <div className="space-y-4">
              <SectionCard eyebrow="Overview" title="Lead summary">
                <div className="grid gap-4 md:grid-cols-2">
                  <KeyValue label="Role" value={detail.lead.role} />
                  <KeyValue label="Status" value={<StatusBadge tone={statusTone(detail.lead.status)}>{detail.lead.status}</StatusBadge>} />
                  <KeyValue label="Company" value={detail.lead.company} />
                  <KeyValue label="Last activity" value={formatDateTime(detail.lead.last_activity_at)} />
                </div>
              </SectionCard>

              <SectionCard eyebrow="Company" title="Company summary">
                {detail.company_research ? (
                  <div className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <KeyValue label="Industry" value={detail.company_research.industry || "Not detected yet"} />
                      <KeyValue
                        label="Research state"
                        value={
                          <StatusBadge tone={detail.company_research.research_completed ? "accent" : "warning"}>
                            {detail.company_research.research_completed ? "Research completed" : "In progress"}
                          </StatusBadge>
                        }
                      />
                    </div>
                    <div className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                      <p className="text-sm font-semibold text-foreground">Description</p>
                      <p className="mt-3 text-sm leading-7 text-muted">{detail.company_research.description || "No description yet."}</p>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    No company research yet. Run research to pull the website, industry, and product story into this record.
                  </div>
                )}
              </SectionCard>

              <SectionCard eyebrow="Sales Insight" title="Preview the current angle">
                {detail.sales_insight ? (
                  <div className="space-y-4">
                    <div className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                      <p className="text-sm font-semibold text-foreground">Sales angle</p>
                      <p className="mt-3 text-sm leading-7 text-muted">{detail.sales_insight.sales_angle}</p>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <KeyValue label="Value proposition" value={detail.sales_insight.value_proposition} />
                      <KeyValue label="Personalization notes" value={detail.sales_insight.personalization_notes} />
                    </div>
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    No sales insight yet. Once research runs, this becomes the best quick read before writing or scheduling outreach.
                  </div>
                )}
              </SectionCard>
            </div>
          ) : null}

          {activeTab === "research" ? (
            <div className="space-y-4">
              <SectionCard eyebrow="Company Research" title="What we know about the company">
                {detail.company_research ? (
                  <div className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <KeyValue label="Industry" value={detail.company_research.industry || "Not detected yet"} />
                      <KeyValue label="Website" value={detail.company_research.website || "No website captured"} />
                    </div>
                    <div className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                      <p className="text-sm font-semibold text-foreground">Company description</p>
                      <p className="mt-3 text-sm leading-7 text-muted">{detail.company_research.description || "No company description yet."}</p>
                    </div>
                    <div className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                      <p className="text-sm font-semibold text-foreground">Product or service summary</p>
                      <p className="mt-3 text-sm leading-7 text-muted">{detail.company_research.product_summary || "No product summary yet."}</p>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    Company research has not been generated for this lead yet.
                  </div>
                )}
              </SectionCard>

              <SectionCard eyebrow="Lead Research" title="What we know about the contact">
                {detail.lead_insight ? (
                  <div className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <KeyValue label="Role category" value={detail.lead_insight.role_category} />
                      <KeyValue
                        label="Confidence"
                        value={`${Math.round(detail.lead_insight.confidence_score * 100)}%`}
                      />
                    </div>
                    <div className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                      <p className="text-sm font-semibold text-foreground">Likely pain points</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {detail.lead_insight.possible_pain_points.length > 0 ? (
                          detail.lead_insight.possible_pain_points.map((point) => (
                            <StatusBadge key={point} tone="warm">
                              {point}
                            </StatusBadge>
                          ))
                        ) : (
                          <p className="text-sm text-muted">No pain points captured yet.</p>
                        )}
                      </div>
                    </div>
                    <div className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                      <p className="text-sm font-semibold text-foreground">Recommended sales angle</p>
                      <p className="mt-3 text-sm leading-7 text-muted">{detail.lead_insight.recommended_sales_angle}</p>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    Lead insight has not been generated yet.
                  </div>
                )}
              </SectionCard>

              <SectionCard eyebrow="Sales Insight" title="Angle, value, and personalization">
                {detail.sales_insight ? (
                  <div className="grid gap-4">
                    <KeyValue label="Sales angle" value={detail.sales_insight.sales_angle} />
                    <KeyValue label="Value proposition" value={detail.sales_insight.value_proposition} />
                    <KeyValue label="Personalization notes" value={detail.sales_insight.personalization_notes} />
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    Sales insight has not been generated yet.
                  </div>
                )}
              </SectionCard>
            </div>
          ) : null}

          {activeTab === "outreach" ? (
            <div className="space-y-4">
              <SectionCard eyebrow="Campaigns" title="Campaign association">
                {detail.campaign_associations.length > 0 ? (
                  <div className="space-y-3">
                    {detail.campaign_associations.map((association) => (
                      <div key={association.campaign_id} className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-foreground">{association.campaign_name}</p>
                            <p className="mt-1 text-sm text-muted">
                              {summarizeTypes(association.association_types)}
                            </p>
                          </div>
                          <StatusBadge tone={campaignStatusTone(association.campaign_status)}>
                            {association.campaign_status}
                          </StatusBadge>
                        </div>
                        <p className="mt-3 text-sm text-muted">
                          Last activity {formatDateTime(association.last_activity_at)}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    No campaign touchpoints yet. Pick a campaign on the right rail to generate or schedule outreach.
                  </div>
                )}
              </SectionCard>

              <SectionCard eyebrow="Drafts" title="Generated email">
                {detail.generated_emails.length > 0 ? (
                  <div className="space-y-4">
                    {detail.generated_emails.map((email) => (
                      <div key={email.id} className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-foreground">{email.subject}</p>
                            <p className="mt-1 text-sm text-muted">{email.campaign_name}</p>
                          </div>
                          <p className="text-xs uppercase tracking-[0.18em] text-muted">
                            {formatDateTime(email.generated_at)}
                          </p>
                        </div>
                        <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-muted">{email.body}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    No generated email yet. Choose a campaign and use the action bar to create the first draft.
                  </div>
                )}
              </SectionCard>

              <SectionCard eyebrow="Sequence" title="Follow-up sequence">
                {detail.followups.length > 0 ? (
                  <div className="space-y-3">
                    {detail.followups.map((followup) => (
                      <div key={followup.id} className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-foreground">
                              Step {followup.step_number}: {followup.email_subject}
                            </p>
                            <p className="mt-1 text-sm text-muted">{followup.campaign_name}</p>
                          </div>
                          <p className="text-xs uppercase tracking-[0.18em] text-muted">
                            {formatDateTime(followup.scheduled_date)}
                          </p>
                        </div>
                        <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-muted">{followup.email_body}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    No follow-up sequence yet. It will appear here once we generate or schedule outreach for a campaign.
                  </div>
                )}
              </SectionCard>
            </div>
          ) : null}

          {activeTab === "conversation" ? (
            <div className="space-y-4">
              <SectionCard eyebrow="Sent Emails" title="Outbound history">
                {detail.sent_emails.length > 0 ? (
                  <div className="space-y-3">
                    {detail.sent_emails.map((email) => (
                      <div key={email.id} className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-foreground">{email.subject || "Outbound email sent"}</p>
                            <p className="mt-1 text-sm text-muted">{email.campaign_name}</p>
                          </div>
                          <StatusBadge tone={email.status === "SENT" ? "accent" : "warning"}>{email.status}</StatusBadge>
                        </div>
                        {email.body ? <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-muted">{email.body}</p> : null}
                        <p className="mt-4 text-xs uppercase tracking-[0.18em] text-muted">{formatDateTime(email.sent_at)}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    No outbound history yet.
                  </div>
                )}
              </SectionCard>

              <SectionCard eyebrow="Replies" title="Inbound conversation">
                {detail.replies.length > 0 ? (
                  <div className="space-y-4">
                    {detail.replies.map((reply) => (
                      <div key={reply.id} className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-foreground">Reply received</p>
                            <p className="mt-1 text-sm text-muted">{formatDateTime(reply.received_at)}</p>
                          </div>
                          <StatusBadge tone={reply.category === "INTERESTED" ? "accent" : "neutral"}>
                            {reply.category ?? "UNCLASSIFIED"}
                          </StatusBadge>
                        </div>
                        <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-muted">{reply.body}</p>

                        {reply.generated_reply ? (
                          <div className="mt-5 rounded-[20px] border border-border/70 bg-[rgba(15,118,110,0.06)] p-4">
                            <p className="text-xs uppercase tracking-[0.18em] text-muted">Suggested reply</p>
                            <p className="mt-2 text-sm font-semibold text-foreground">{reply.generated_reply.subject}</p>
                            <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-muted">{reply.generated_reply.body}</p>
                            <p className="mt-3 text-xs uppercase tracking-[0.18em] text-muted">
                              Goal: {reply.generated_reply.reply_goal.replaceAll("_", " ")}
                            </p>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    No replies yet. Once the inbox catches a response, this thread becomes the working conversation surface.
                  </div>
                )}
              </SectionCard>

              <SectionCard eyebrow="Memory" title="Semantic memory items">
                {detail.memory_items.length > 0 ? (
                  <div className="space-y-3">
                    {detail.memory_items.map((memory) => (
                      <div key={memory.id} className="rounded-[24px] border border-border/70 bg-white/75 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <StatusBadge tone="neutral">{memory.source_type.replaceAll("_", " ")}</StatusBadge>
                          <p className="text-xs uppercase tracking-[0.18em] text-muted">{formatDateTime(memory.created_at)}</p>
                        </div>
                        <p className="mt-3 text-sm leading-7 text-muted">{memory.content}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    No memory items yet. Sent emails, replies, and notes will begin to appear here as the conversation grows.
                  </div>
                )}
              </SectionCard>
            </div>
          ) : null}

          {activeTab === "notes" ? (
            <div className="space-y-4">
              <SectionCard eyebrow="Notes" title="Capture internal context">
                <div className="space-y-4">
                  <label className="block space-y-2">
                    <span className="text-sm font-semibold text-foreground">Add note</span>
                    <textarea
                      className="field min-h-36 resize-y"
                      placeholder="Capture budget timing, objections, meeting context, or anything the next teammate should know."
                      value={noteDraft}
                      onChange={(event) => setNoteDraft(event.target.value)}
                    />
                  </label>
                  <div className="flex items-center gap-3">
                    <button
                      className="primary-button inline-flex h-11 items-center px-5 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                      type="button"
                      disabled={noteMutation.isPending}
                      onClick={() => noteMutation.mutate()}
                    >
                      {noteMutation.isPending ? "Saving..." : "Save note"}
                    </button>
                    {noteMutation.isError ? (
                      <p className="text-sm text-rose-800">{noteMutation.error.message}</p>
                    ) : null}
                  </div>
                </div>
              </SectionCard>

              <SectionCard eyebrow="Timeline" title="Notes timeline">
                {detail.notes.length > 0 ? (
                  <div className="space-y-3">
                    {detail.notes.map((note) => (
                      <div key={note.id} className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold text-foreground">Internal note</p>
                          <p className="text-xs uppercase tracking-[0.18em] text-muted">{formatDateTime(note.created_at)}</p>
                        </div>
                        <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-muted">{note.content}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    No notes yet. This is the best place for handoff context and soft signals that do not belong in the lead fields.
                  </div>
                )}
              </SectionCard>
            </div>
          ) : null}
        </main>

        <aside className="space-y-4">
          <section className="panel p-5">
            <p className="eyebrow">Action Rail</p>
            <h2 className="mt-2 text-2xl font-semibold text-foreground">Campaign context</h2>
            <div className="mt-5 space-y-4">
              <label className="block space-y-2">
                <span className="text-sm font-semibold text-foreground">Choose campaign</span>
                <select
                  className="field"
                  value={selectedCampaignId}
                  onChange={(event) => setSelectedCampaignId(event.target.value)}
                >
                  {detail.available_campaigns.length > 0 ? (
                    detail.available_campaigns.map((campaign) => (
                      <option key={campaign.id} value={campaign.id}>
                        {campaign.name}
                      </option>
                    ))
                  ) : (
                    <option value="">No campaigns available</option>
                  )}
                </select>
              </label>

              {selectedCampaign ? (
                <div className="rounded-[24px] border border-border/70 bg-white/75 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-foreground">{selectedCampaign.name}</p>
                      <p className="mt-1 text-sm text-muted">Tone: {selectedCampaign.message_tone}</p>
                    </div>
                    <StatusBadge tone={campaignStatusTone(selectedCampaign.status)}>{selectedCampaign.status}</StatusBadge>
                  </div>
                </div>
              ) : (
                <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-5 text-sm text-muted">
                  No campaigns yet. Create one before generating or scheduling outreach from this lead surface.
                </div>
              )}

              <div className="grid gap-3">
                <button
                  className="secondary-button inline-flex h-11 items-center justify-center px-5 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                  type="button"
                  disabled={emailMutation.isPending || !selectedCampaignId}
                  onClick={() => emailMutation.mutate()}
                >
                  Generate email in selected campaign
                </button>
                <button
                  className="secondary-button inline-flex h-11 items-center justify-center px-5 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                  type="button"
                  disabled={scheduleMutation.isPending || !selectedCampaignId}
                  onClick={() => scheduleMutation.mutate()}
                >
                  Schedule outreach in selected campaign
                </button>
              </div>
            </div>
          </section>

          <section className="panel p-5">
            <p className="eyebrow">Timeline</p>
            <h2 className="mt-2 text-2xl font-semibold text-foreground">Recent activity</h2>
            <div className="mt-5 space-y-3">
              {detail.timeline.length > 0 ? (
                detail.timeline.map((item) => (
                  <div key={`${item.item_type}-${item.created_at}-${item.title}`} className="rounded-[24px] border border-border/70 bg-white/75 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <StatusBadge tone="neutral">{item.title}</StatusBadge>
                      <p className="text-xs uppercase tracking-[0.18em] text-muted">{formatDateTime(item.created_at)}</p>
                    </div>
                    <p className="mt-3 text-sm leading-7 text-muted">{item.content}</p>
                  </div>
                ))
              ) : (
                <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-5 text-sm text-muted">
                  No timeline activity yet.
                </div>
              )}
            </div>
          </section>

          <section className="panel p-5">
            <p className="eyebrow">Scheduled</p>
            <h2 className="mt-2 text-2xl font-semibold text-foreground">Queued sends</h2>
            <div className="mt-5 space-y-3">
              {detail.scheduled_emails.length > 0 ? (
                detail.scheduled_emails.map((item) => (
                  <div key={item.id} className="rounded-[24px] border border-border/70 bg-white/75 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-foreground">{item.campaign_name}</p>
                        <p className="mt-1 text-sm text-muted">
                          {item.email_type.replaceAll("_", " ")} · Step {item.step_number}
                        </p>
                      </div>
                      <StatusBadge tone={item.approval_status === "PENDING_APPROVAL" ? "warning" : "neutral"}>
                        {item.approval_status}
                      </StatusBadge>
                    </div>
                    <p className="mt-3 text-sm text-muted">Scheduled {formatDateTime(item.scheduled_for)}</p>
                  </div>
                ))
              ) : (
                <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-5 text-sm text-muted">
                  Nothing is queued yet for this lead.
                </div>
              )}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
