"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { mainNavigation } from "@/lib/navigation";

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="panel hidden min-h-full flex-col overflow-hidden p-4 lg:flex">
      <div className="rounded-[24px] bg-[linear-gradient(135deg,rgba(15,118,110,0.16),rgba(23,33,31,0.04))] p-5">
        <p className="eyebrow">AI SDR</p>
        <h1 className="heading-display mt-3 text-2xl font-semibold text-foreground">Northline Ops</h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          A warm command center for lead research, outreach, replies, approvals, and campaign visibility.
        </p>
      </div>

      <nav className="mt-6 space-y-2">
        {mainNavigation.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded-[22px] border px-4 py-3 transition ${
                active
                  ? "border-transparent bg-surface-ink text-white shadow-[0_18px_40px_-24px_rgba(17,32,30,0.85)]"
                  : "border-transparent bg-white/45 text-foreground hover:border-border/70 hover:bg-white/80"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold">{item.label}</span>
                <span
                  className={`rounded-full px-2 py-1 font-mono text-[11px] ${
                    active ? "bg-white/12 text-white/85" : "bg-accent-soft text-accent"
                  }`}
                >
                  {item.shortcut}
                </span>
              </div>
              <p className={`mt-1 text-sm leading-5 ${active ? "text-white/75" : "text-muted"}`}>{item.description}</p>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto rounded-[24px] border border-border/70 bg-white/70 p-4">
        <p className="text-sm font-semibold text-foreground">Human approval mode</p>
        <p className="mt-2 text-sm leading-6 text-muted">
          Two emails are waiting for approval before the next sending window opens.
        </p>
        <Link
          href="/approvals"
          className="secondary-button mt-4 inline-flex h-10 items-center px-4 text-sm font-semibold"
        >
          Open approvals
        </Link>
      </div>
    </aside>
  );
}
