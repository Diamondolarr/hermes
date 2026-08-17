export const mainNavigation = [
  {
    label: "Dashboard",
    href: "/dashboard",
    description: "KPIs, recent replies, approvals, and campaign pulse.",
    shortcut: "01",
  },
  {
    label: "Leads",
    href: "/leads",
    description: "Import, filter, and inspect every prospect profile.",
    shortcut: "02",
  },
  {
    label: "Campaigns",
    href: "/campaigns",
    description: "Create, track, schedule, and analyze outbound programs.",
    shortcut: "03",
  },
  {
    label: "Inbox",
    href: "/inbox",
    description: "Work replies with classification and AI-assisted responses.",
    shortcut: "04",
  },
  {
    label: "Approvals",
    href: "/approvals",
    description: "Review pending emails before they go live.",
    shortcut: "05",
  },
  {
    label: "Notifications",
    href: "/notifications",
    description: "Monitor replies, errors, meetings, and system events.",
    shortcut: "06",
  },
  {
    label: "Settings",
    href: "/settings",
    description: "Tune user preferences, workspace controls, and integrations.",
    shortcut: "07",
  },
  {
    label: "Admin",
    href: "/admin",
    description: "Internal usage, abuse alerts, and cross-workspace monitoring.",
    shortcut: "08",
  },
] as const;
