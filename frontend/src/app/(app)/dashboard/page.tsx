"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { MetricCard } from "@/components/ui/metric-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { getDashboardSummary } from "@/features/dashboard/api";
import { useAuth } from "@/lib/auth-context";

function formatCount(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function DashboardPage() {
  const { session } = useAuth();
  const accessToken = session?.accessToken ?? null;

  const dashboardQuery = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => getDashboardSummary(accessToken as string),
    enabled: Boolean(accessToken),
  });

  if (dashboardQuery.isLoading) {
    return (
      <div className="panel-strong flex min-h-[calc(100vh-10rem)] items-center justify-center p-8 text-center">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground">
            Loading the command center.
          </h1>
          <p className="mt-4 max-w-lg text-lg text-muted">
            We are pulling live campaign, reply, approval, and notification data into the dashboard now.
          </p>
        </div>
      </div>
    );
  }

  if (dashboardQuery.isError || !dashboardQuery.data) {
    return (
      <div className="panel-strong flex min-h-[calc(100vh-10rem)] items-center justify-center p-8 text-center">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground">
            We hit a dashboard snag.
          </h1>
          <p className="mt-4 max-w-xl text-lg text-muted">
            {dashboardQuery.error?.message ?? "We could not load the dashboard summary."}
          </p>
          <button
            className="primary-button mt-6 inline-flex h-11 items-center px-5 font-semibold"
            type="button"
            onClick={() => dashboardQuery.refetch()}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  const data = dashboardQuery.data;
  const metrics = [
    {
      label: "Leads",
      value: formatCount(data.leads),
      change: `${data.connected_email_accounts} connected inbox${data.connected_email_accounts === 1 ? "" : "es"}`,
      tone: "accent" as const,
    },
    {
      label: "Active campaigns",
      value: formatCount(data.active_campaigns),
      change: `${data.active_campaigns_snapshot.length} showing in snapshot`,
      tone: "ink" as const,
    },
    {
      label: "Emails sent",
      value: formatCount(data.emails_sent),
      change: `${formatCount(data.pending_approvals_count)} approvals waiting`,
      tone: "ink" as const,
    },
    {
      label: "Replies",
      value: formatCount(data.replies),
      change: `${formatCount(data.unread_notifications_count)} unread alerts`,
      tone: "warm" as const,
    },
    {
      label: "Meetings",
      value: formatCount(data.meetings),
      change: data.meetings > 0 ? "Meeting pipeline is moving" : "No meetings logged yet",
      tone: "accent" as const,
    },
  ];

  const quickActions = [
    {
      label: "Import leads",
      href: "/leads",
      variant: "primary",
      description: "Bring fresh prospects into the workspace and start research fast.",
    },
    {
      label: "Create campaign",
      href: "/campaigns",
      variant: "secondary",
      description: "Launch a new outbound motion with campaign settings and sequence logic.",
    },
    {
      label: data.connected_email_accounts > 0 ? "Gmail connected" : "Connect Gmail",
      href: "/settings",
      variant: "secondary",
      description: "Head to settings to connect or review the sending inbox integration.",
    },
    {
      label: "Review approvals",
      href: "/approvals",
      variant: "secondary",
      description: "Open the human approval queue for anything waiting on review.",
    },
  ] as const;

  return (
    <div className="space-y-8">
      <section className="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
        <div className="panel-strong relative overflow-hidden p-6 sm:p-8">
          <div className="absolute inset-y-0 right-0 hidden w-1/3 bg-[radial-gradient(circle_at_top,rgba(15,118,110,0.22),transparent_68%)] lg:block" />
          <p className="eyebrow">Dashboard</p>
          <div className="mt-4 flex flex-col gap-5 lg:max-w-2xl">
            <h1 className="heading-display text-4xl font-semibold text-foreground sm:text-5xl">
              Run the whole outbound motion from one warm command center.
            </h1>
            <p className="max-w-2xl text-lg leading-7 text-muted">
              The dashboard now pulls live workspace data so the top strip feels like a real operating surface, not just a mock layout.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/leads" className="primary-button inline-flex h-11 items-center px-5 font-semibold">
                Import leads
              </Link>
              <Link href="/campaigns" className="secondary-button inline-flex h-11 items-center px-5 font-semibold">
                Create campaign
              </Link>
              <Link href="/settings" className="secondary-button inline-flex h-11 items-center px-5 font-semibold">
                Connect Gmail
              </Link>
              <Link href="/approvals" className="secondary-button inline-flex h-11 items-center px-5 font-semibold">
                Review approvals
              </Link>
            </div>
          </div>
        </div>

        <div className="panel p-6">
          <p className="eyebrow">Live Queue</p>
          <div className="mt-6 space-y-4">
            <div className="rounded-[22px] border border-border/70 bg-white/80 p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-foreground">Pending approvals</p>
                <StatusBadge tone="warning">{data.pending_approvals_count} waiting</StatusBadge>
              </div>
              <p className="mt-2 text-sm text-muted">
                Human approval mode currently has {data.pending_approvals.length} item{data.pending_approvals.length === 1 ? "" : "s"} surfaced in the review queue.
              </p>
            </div>
            <div className="rounded-[22px] border border-border/70 bg-white/80 p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-foreground">Notifications</p>
                <StatusBadge tone="accent">{data.unread_notifications_count} unread</StatusBadge>
              </div>
              <p className="mt-2 text-sm text-muted">
                Replies, meetings, campaign completions, and system errors all feed this preview layer.
              </p>
            </div>
            <div className="rounded-[22px] border border-border/70 bg-white/80 p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-foreground">Inbox connectivity</p>
                <StatusBadge tone={data.connected_email_accounts > 0 ? "accent" : "warning"}>
                  {data.connected_email_accounts > 0 ? "Connected" : "Needs setup"}
                </StatusBadge>
              </div>
              <p className="mt-2 text-sm text-muted">
                {data.connected_email_accounts > 0
                  ? `You currently have ${data.connected_email_accounts} connected inbox${data.connected_email_accounts === 1 ? "" : "es"}.`
                  : "Connect Gmail to unlock sending, polling, and reply detection from the dashboard flow."}
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="grid gap-4">
          <div className="panel p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="eyebrow">Campaign Pulse</p>
                <h2 className="mt-2 text-2xl font-semibold text-foreground">Active campaigns snapshot</h2>
              </div>
              <Link href="/campaigns" className="secondary-button inline-flex h-10 items-center px-4 text-sm font-semibold">
                View campaigns
              </Link>
            </div>

            <div className="mt-6 space-y-3">
              {data.active_campaigns_snapshot.length > 0 ? data.active_campaigns_snapshot.map((campaign) => (
                <div
                  key={campaign.campaign_id}
                  className="grid gap-3 rounded-[24px] border border-border/70 bg-white/75 p-4 md:grid-cols-[1.35fr_0.55fr_0.45fr_0.45fr_0.45fr] md:items-center"
                >
                  <div>
                    <p className="text-sm font-semibold text-foreground">{campaign.name}</p>
                    <p className="mt-1 text-sm text-muted">Live snapshot with campaign status, sends, replies, and reply-rate context.</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted">Status</p>
                    <p className="mt-1 text-sm font-semibold text-foreground">{campaign.status}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted">Sent</p>
                    <p className="mt-1 text-sm font-semibold text-foreground">{formatCount(campaign.emails_sent)}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted">Replies</p>
                    <p className="mt-1 text-sm font-semibold text-foreground">{formatCount(campaign.replies)}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted">Rate</p>
                    <p className="mt-1 text-sm font-semibold text-foreground">{campaign.reply_rate.toFixed(1)}%</p>
                  </div>
                </div>
              )) : (
                <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                  No active campaigns yet. Create a campaign to bring this section to life.
                </div>
              )}
            </div>
          </div>

          <div className="panel p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="eyebrow">Activity</p>
                <h2 className="mt-2 text-2xl font-semibold text-foreground">Recent activity</h2>
              </div>
              <Link href="/activity" className="secondary-button inline-flex h-10 items-center px-4 text-sm font-semibold">
                View activity
              </Link>
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-2">
              {data.recent_activity.length > 0 ? data.recent_activity.map((item) => (
                <div key={item.id} className="rounded-[22px] border border-border/70 bg-white/75 p-4">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div className="h-2 w-14 rounded-full bg-accent/25" />
                    <span className="text-xs uppercase tracking-[0.18em] text-muted">{formatDateTime(item.created_at)}</span>
                  </div>
                  <p className="text-sm font-semibold text-foreground">{item.event_type.replaceAll("_", " ")}</p>
                  <p className="mt-2 text-sm leading-6 text-muted">{item.message}</p>
                </div>
              )) : (
                <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                  Activity will appear here as research, sends, replies, and automations begin to flow.
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="grid gap-4">
          <div className="panel p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="eyebrow">Inbox</p>
                <h2 className="mt-2 text-2xl font-semibold text-foreground">Recent replies</h2>
              </div>
              <Link href="/inbox" className="secondary-button inline-flex h-10 items-center px-4 text-sm font-semibold">
                Open inbox
              </Link>
            </div>

            <div className="mt-5 space-y-3">
              {data.recent_replies.length > 0 ? data.recent_replies.map((reply) => (
                <div key={reply.id} className="rounded-[22px] border border-border/70 bg-white/75 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-foreground">{reply.lead_name}</p>
                      <p className="text-sm text-muted">{reply.company}</p>
                    </div>
                    <StatusBadge tone="accent">{reply.category ?? "UNCLASSIFIED"}</StatusBadge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-muted">{reply.preview}</p>
                  <p className="mt-3 text-xs uppercase tracking-[0.18em] text-muted">{formatDateTime(reply.received_at)}</p>
                </div>
              )) : (
                <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                  No replies yet. Once the inbox starts moving, this panel will become the fastest way into conversation work.
                </div>
              )}
            </div>
          </div>

          <div className="panel p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="eyebrow">Review Queue</p>
                <h2 className="mt-2 text-2xl font-semibold text-foreground">Pending approvals</h2>
              </div>
              <StatusBadge tone="warning">Human mode</StatusBadge>
            </div>

            <div className="mt-5 space-y-3">
              {data.pending_approvals.length > 0 ? data.pending_approvals.map((approval) => (
                <div key={approval.scheduled_email_id} className="rounded-[22px] border border-border/70 bg-white/75 p-4">
                  <p className="text-sm font-semibold text-foreground">{approval.lead_name}</p>
                  <p className="mt-1 text-sm text-muted">{approval.campaign_name}</p>
                  <div className="mt-3 flex items-center justify-between gap-3 text-xs uppercase tracking-[0.18em] text-muted">
                    <span>Step 0{approval.step_number}</span>
                    <span>{formatDateTime(approval.scheduled_for)}</span>
                  </div>
                </div>
              )) : (
                <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                  No pending approvals right now. When approval mode catches a draft, it will appear here.
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="panel p-6">
              <p className="eyebrow">Notifications</p>
              <h2 className="mt-2 text-2xl font-semibold text-foreground">Preview</h2>
              <div className="mt-5 space-y-3">
                {data.notifications_preview.length > 0 ? data.notifications_preview.map((notification) => (
                  <div key={notification.id} className="rounded-[22px] border border-border/70 bg-white/75 p-4">
                    <p className="text-sm font-semibold text-foreground">{notification.title}</p>
                    <p className="mt-2 text-sm leading-6 text-muted">{notification.body}</p>
                    <p className="mt-3 text-xs uppercase tracking-[0.18em] text-muted">{formatDateTime(notification.created_at)}</p>
                  </div>
                )) : (
                  <div className="rounded-[24px] border border-dashed border-border/80 bg-white/70 p-6 text-sm text-muted">
                    No unread notifications right now.
                  </div>
                )}
              </div>
            </div>

            <div className="panel p-6">
              <p className="eyebrow">Quick Actions</p>
              <h2 className="mt-2 text-2xl font-semibold text-foreground">Move fast</h2>
              <div className="mt-5 space-y-3">
                {quickActions.map((action) => (
                  <Link
                    key={action.label}
                    href={action.href}
                    className={`block rounded-[22px] border p-4 transition ${
                      action.variant === "primary"
                        ? "border-transparent bg-surface-ink text-white shadow-[0_20px_44px_-28px_rgba(17,32,30,0.85)]"
                        : "border-border/70 bg-white/75 text-foreground hover:bg-white"
                    }`}
                  >
                    <p className="text-sm font-semibold">{action.label}</p>
                    <p className={`mt-2 text-sm leading-6 ${action.variant === "primary" ? "text-white/72" : "text-muted"}`}>
                      {action.description}
                    </p>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
