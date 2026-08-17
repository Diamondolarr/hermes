"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getLeads, importLeads, type LeadListFilters } from "@/features/leads/api";
import { useAuth } from "@/lib/auth-context";
import { StatusBadge } from "@/components/ui/status-badge";

const statusOptions = ["", "NEW", "RESEARCHED", "CONTACTED", "REPLIED", "MEETING_SCHEDULED", "CLOSED"];

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusTone(status: string) {
  switch (status) {
    case "REPLIED":
    case "MEETING_SCHEDULED":
      return "accent" as const;
    case "CLOSED":
      return "ink" as const;
    case "CONTACTED":
      return "warm" as const;
    default:
      return "neutral" as const;
  }
}

function researchTone(state: string) {
  switch (state) {
    case "Lead researched":
      return "accent" as const;
    case "Company researched":
      return "warm" as const;
    default:
      return "neutral" as const;
  }
}

export default function LeadsPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const { session } = useAuth();
  const accessToken = session?.accessToken ?? null;
  const [filters, setFilters] = useState<LeadListFilters>({
    search: "",
    status: "",
    company: "",
    role: "",
  });

  const normalizedFilters = useMemo(
    () => ({
      search: filters.search?.trim() || undefined,
      status: filters.status || undefined,
      company: filters.company?.trim() || undefined,
      role: filters.role?.trim() || undefined,
    }),
    [filters],
  );

  const leadsQuery = useQuery({
    queryKey: ["leads", normalizedFilters],
    queryFn: () => getLeads(accessToken as string, normalizedFilters),
    enabled: Boolean(accessToken),
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => importLeads(accessToken as string, file),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  const leads = leadsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <section className="panel-strong p-6 sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="eyebrow">Lead Management Hub</p>
            <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground sm:text-5xl">
              Keep lead operations dense, breathable, and easy to act on.
            </h1>
            <p className="mt-4 max-w-2xl text-lg leading-7 text-muted">
              This page is now a real working surface: search, filter, import, scan research state, and jump straight into a lead record.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  importMutation.mutate(file);
                }
                event.currentTarget.value = "";
              }}
            />
            <button
              className="primary-button inline-flex h-11 items-center px-5 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
              type="button"
              disabled={importMutation.isPending}
              onClick={() => fileInputRef.current?.click()}
            >
              {importMutation.isPending ? "Importing CSV..." : "Import CSV"}
            </button>
          </div>
        </div>

        {importMutation.isSuccess ? (
          <div className="mt-6 rounded-[24px] border border-emerald-200 bg-emerald-50 p-5">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge tone="accent">Import complete</StatusBadge>
              <p className="text-sm font-semibold text-emerald-900">
                {importMutation.data.inserted} inserted, {importMutation.data.updated} updated, {importMutation.data.skipped} skipped.
              </p>
            </div>
            {importMutation.data.errors.length > 0 ? (
              <div className="mt-4 space-y-2 text-sm text-emerald-900">
                {importMutation.data.errors.slice(0, 3).map((error) => (
                  <p key={`${error.row_number}-${error.message}`}>
                    Row {error.row_number}: {error.message}
                  </p>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {importMutation.isError ? (
          <div className="mt-6 rounded-[24px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-800">
            {importMutation.error.message}
          </div>
        ) : null}
      </section>

      <section className="panel p-5 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Filters</p>
            <h2 className="mt-2 text-2xl font-semibold text-foreground">Find the right leads fast</h2>
          </div>
          <button
            className="secondary-button inline-flex h-11 items-center px-5 font-semibold"
            type="button"
            onClick={() => setFilters({ search: "", status: "", company: "", role: "" })}
          >
            Clear filters
          </button>
        </div>

        <div className="mt-5 grid gap-4 xl:grid-cols-[1.3fr_0.7fr_0.8fr_0.8fr]">
          <label className="block space-y-2">
            <span className="text-sm font-semibold text-foreground">Search</span>
            <input
              className="field"
              type="text"
              placeholder="Search by name, email, company, or role"
              value={filters.search}
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
            />
          </label>

          <label className="block space-y-2">
            <span className="text-sm font-semibold text-foreground">Status</span>
            <select
              className="field"
              value={filters.status}
              onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}
            >
              {statusOptions.map((option) => (
                <option key={option || "all"} value={option}>
                  {option || "All statuses"}
                </option>
              ))}
            </select>
          </label>

          <label className="block space-y-2">
            <span className="text-sm font-semibold text-foreground">Company</span>
            <input
              className="field"
              type="text"
              placeholder="Filter by company"
              value={filters.company}
              onChange={(event) => setFilters((current) => ({ ...current, company: event.target.value }))}
            />
          </label>

          <label className="block space-y-2">
            <span className="text-sm font-semibold text-foreground">Role</span>
            <input
              className="field"
              type="text"
              placeholder="Filter by role"
              value={filters.role}
              onChange={(event) => setFilters((current) => ({ ...current, role: event.target.value }))}
            />
          </label>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="flex items-center justify-between border-b border-border/70 px-5 py-4 sm:px-6">
          <div>
            <p className="eyebrow">Leads</p>
            <h2 className="mt-2 text-2xl font-semibold text-foreground">{leadsQuery.data?.total ?? 0} records</h2>
          </div>
          <p className="text-sm text-muted">Use row actions to open an individual lead.</p>
        </div>

        {leadsQuery.isLoading ? (
          <div className="p-6 text-sm text-muted">Loading leads...</div>
        ) : leadsQuery.isError ? (
          <div className="p-6 text-sm text-rose-800">{leadsQuery.error.message}</div>
        ) : leads.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border/70 bg-white/40 text-xs uppercase tracking-[0.18em] text-muted">
                  <th className="px-5 py-4 font-semibold sm:px-6">Name</th>
                  <th className="px-5 py-4 font-semibold sm:px-6">Email</th>
                  <th className="px-5 py-4 font-semibold sm:px-6">Company</th>
                  <th className="px-5 py-4 font-semibold sm:px-6">Role</th>
                  <th className="px-5 py-4 font-semibold sm:px-6">Status</th>
                  <th className="px-5 py-4 font-semibold sm:px-6">Research state</th>
                  <th className="px-5 py-4 font-semibold sm:px-6">Last activity</th>
                  <th className="px-5 py-4 font-semibold sm:px-6">Actions</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.id} className="border-b border-border/50 bg-white/60 align-top transition hover:bg-white/85">
                    <td className="px-5 py-4 sm:px-6">
                      <div>
                        <p className="text-sm font-semibold text-foreground">{lead.name}</p>
                        <p className="mt-1 text-sm text-muted">Created {formatDateTime(lead.created_at)}</p>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-sm text-muted sm:px-6">{lead.email}</td>
                    <td className="px-5 py-4 text-sm text-muted sm:px-6">{lead.company}</td>
                    <td className="px-5 py-4 text-sm text-muted sm:px-6">{lead.role}</td>
                    <td className="px-5 py-4 sm:px-6">
                      <StatusBadge tone={statusTone(lead.status)}>{lead.status}</StatusBadge>
                    </td>
                    <td className="px-5 py-4 sm:px-6">
                      <StatusBadge tone={researchTone(lead.research_state)}>{lead.research_state}</StatusBadge>
                    </td>
                    <td className="px-5 py-4 text-sm text-muted sm:px-6">{formatDateTime(lead.last_activity_at)}</td>
                    <td className="px-5 py-4 sm:px-6">
                      <Link href={`/leads/${lead.id}`} className="secondary-button inline-flex h-10 items-center px-4 text-sm font-semibold">
                        Open lead
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center">
            <p className="eyebrow">No Leads Yet</p>
            <h3 className="mt-3 text-2xl font-semibold text-foreground">Start with a CSV import.</h3>
            <p className="mt-3 text-sm leading-6 text-muted">
              Once leads are imported, this hub becomes the place to scan status, research progress, and last activity before diving into a record.
            </p>
            <button
              className="primary-button mt-6 inline-flex h-11 items-center px-5 font-semibold"
              type="button"
              onClick={() => fileInputRef.current?.click()}
            >
              Import CSV
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
