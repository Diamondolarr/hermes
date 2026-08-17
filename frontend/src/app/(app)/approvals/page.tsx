import { PlaceholderPage } from "@/components/ui/placeholder-page";

export default function ApprovalsPage() {
  return (
    <PlaceholderPage
      eyebrow="Approvals"
      title="Approval queue shell"
      description="This route will hold the review queue for drafts that require a human before they can be sent."
      bullets={[
        "Pending approvals list with scheduled timestamps.",
        "Draft subject and body preview.",
        "Approve and reject controls with reason capture.",
      ]}
    />
  );
}
