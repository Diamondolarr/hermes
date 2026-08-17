import { RequireAuth } from "@/components/auth/require-auth";

export default function WizardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <RequireAuth>{children}</RequireAuth>;
}
