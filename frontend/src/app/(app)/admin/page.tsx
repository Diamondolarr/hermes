import { PlaceholderPage } from "@/components/ui/placeholder-page";

export default function AdminPage() {
  return (
    <PlaceholderPage
      eyebrow="Admin"
      title="Admin monitoring shell"
      description="This route is reserved for internal usage reporting, abuse alerts, and system-wide campaign visibility."
      bullets={[
        "System usage and provider consumption.",
        "Abuse alerts and operational exceptions.",
        "Cross-workspace monitoring for internal teams.",
      ]}
    />
  );
}
