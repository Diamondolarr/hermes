"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      const next = pathname ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${next}`);
    }
  }, [pathname, router, status]);

  if (status !== "authenticated") {
    return (
      <div className="min-h-screen p-4">
        <div className="panel-strong flex min-h-[calc(100vh-2rem)] items-center justify-center p-8 text-center">
          <div>
            <p className="eyebrow">Preparing Workspace</p>
            <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground">
              Getting your command center ready.
            </h1>
            <p className="mt-4 max-w-md text-lg text-muted">
              We&apos;re checking your session so the app only opens when your workspace is ready.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
