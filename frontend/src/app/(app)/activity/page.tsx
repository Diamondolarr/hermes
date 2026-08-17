import { PlaceholderPage } from "@/components/ui/placeholder-page";

export default function ActivityPage() {
  return (
    <PlaceholderPage
      eyebrow="Activity"
      title="Activity log shell"
      description="This route is ready for the full activity timeline and filters once we expand beyond the dashboard preview."
      bullets={[
        "Workspace activity timeline.",
        "Lead and campaign filters.",
        "Operational breadcrumbs for sends, research, replies, and automations.",
      ]}
    />
  );
}
