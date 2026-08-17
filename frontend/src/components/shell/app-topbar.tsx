import Link from "next/link";

export function AppTopbar() {
  return (
    <header className="panel flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
      <div className="flex min-w-0 items-center gap-3">
        <div className="rounded-full bg-accent-soft px-3 py-1 font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent">
          Connected
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground">Gmail linked · Calendly ready</p>
          <p className="truncate text-sm text-muted">
            The shell is built to make system state feel ambient instead of buried.
          </p>
        </div>
      </div>

      <div className="flex flex-1 items-center gap-3 sm:max-w-2xl sm:justify-end">
        <label className="hidden min-w-[260px] flex-1 sm:block">
          <input className="field h-11" type="text" placeholder="Search leads, campaigns, replies..." />
        </label>

        <Link href="/notifications" className="secondary-button inline-flex h-11 items-center px-4 font-semibold">
          5 alerts
        </Link>
        <Link href="/settings" className="secondary-button inline-flex h-11 items-center px-4 font-semibold">
          Settings
        </Link>
        <div className="rounded-full border border-border/70 bg-white/75 px-3 py-2 text-sm font-semibold text-foreground">
          JD
        </div>
      </div>
    </header>
  );
}
