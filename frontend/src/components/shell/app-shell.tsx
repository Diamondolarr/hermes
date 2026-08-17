import { AppSidebar } from "@/components/shell/app-sidebar";
import { AppTopbar } from "@/components/shell/app-topbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen p-3 sm:p-4">
      <div className="grid min-h-[calc(100vh-2rem)] gap-4 lg:grid-cols-[280px_1fr]">
        <AppSidebar />
        <div className="flex min-h-full flex-col gap-4">
          <AppTopbar />
          <main className="flex-1">{children}</main>
        </div>
      </div>
    </div>
  );
}
