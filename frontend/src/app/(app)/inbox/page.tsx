import { PlaceholderPage } from "@/components/ui/placeholder-page";

export default function InboxPage() {
  return (
    <PlaceholderPage
      eyebrow="Inbox"
      title="Reply management shell"
      description="This route is ready for the three-pane inbox: thread list, conversation context, and AI-assisted next actions."
      bullets={[
        "Classification-aware reply queue.",
        "Suggested responses and meeting-link actions.",
        "Lead and company context without leaving the inbox.",
      ]}
    />
  );
}
