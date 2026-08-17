import { PlaceholderPage } from "@/components/ui/placeholder-page";

export default function CampaignsPage() {
  return (
    <PlaceholderPage
      eyebrow="Campaigns"
      title="Campaign workspace shell"
      description="This route is reserved for campaign list views, creation, scheduling controls, analytics, and automation tabs."
      bullets={[
        "Campaign list with performance snapshots.",
        "Create-campaign flow with defaults from user settings.",
        "Analytics and automation controls in one place.",
      ]}
    />
  );
}
