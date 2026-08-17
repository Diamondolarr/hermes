import { PlaceholderPage } from "@/components/ui/placeholder-page";

export default function SettingsPage() {
  return (
    <PlaceholderPage
      eyebrow="Settings"
      title="User and workspace settings shell"
      description="This route is where we’ll connect user defaults, integrations, workspace controls, and security preferences."
      bullets={[
        "Daily send limit, tone, timezone, and notifications.",
        "Gmail and Calendly integration cards.",
        "Workspace-level approval and security controls.",
      ]}
    />
  );
}
