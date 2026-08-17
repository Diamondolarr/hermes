type AuthShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  asideTitle: string;
  asideDescription: string;
  asideItems: string[];
  children: React.ReactNode;
  footer?: React.ReactNode;
};

export function AuthShell({
  eyebrow,
  title,
  description,
  asideTitle,
  asideDescription,
  asideItems,
  children,
  footer,
}: AuthShellProps) {
  return (
    <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-7xl items-center justify-center">
      <div className="grid w-full gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="panel-strong soft-ring overflow-hidden p-6 sm:p-8 lg:p-10">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="heading-display mt-4 max-w-xl text-4xl font-semibold text-foreground sm:text-5xl">
            {title}
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-7 text-muted">{description}</p>

          <div className="mt-8 rounded-[28px] border border-border/80 bg-white/75 p-5 sm:p-6">
            {children}
          </div>

          {footer ? <div className="mt-5 text-sm text-muted">{footer}</div> : null}
        </section>

        <aside className="panel relative overflow-hidden p-6 sm:p-8 lg:p-10">
          <div className="absolute inset-x-0 top-0 h-44 bg-[radial-gradient(circle_at_top,rgba(15,118,110,0.24),transparent_70%)]" />
          <div className="relative">
            <p className="eyebrow">Interface Direction</p>
            <h2 className="heading-display mt-4 text-3xl font-semibold text-foreground">{asideTitle}</h2>
            <p className="mt-4 max-w-lg text-base leading-7 text-muted">{asideDescription}</p>

            <div className="mt-8 space-y-4">
              {asideItems.map((item, index) => (
                <div
                  key={item}
                  className="flex gap-4 rounded-[24px] border border-border/70 bg-white/70 p-4"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent-soft font-mono text-sm font-semibold text-accent">
                    0{index + 1}
                  </div>
                  <p className="text-sm leading-6 text-muted">{item}</p>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
