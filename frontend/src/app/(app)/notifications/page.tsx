import { PlaceholderPage } from "@/components/ui/placeholder-page";

export default function NotificationsPage() {
  return (
    <PlaceholderPage
      eyebrow="Notifications"
      title="Notification center shell"
      description="This route is set up for dashboard notifications, unread filters, and channel-aware event tracking."
      bullets={[
        "Reply, meeting, campaign, and error notifications.",
        "Unread filtering and quick actions.",
        "A clean bridge between system events and user attention.",
      ]}
    />
  );
}
