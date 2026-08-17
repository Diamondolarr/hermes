type PlaceholderPageProps = {
  eyebrow: string;
  title: string;
  description: string;
  bullets: string[];
};

export function PlaceholderPage({ eyebrow, title, description, bullets }: PlaceholderPageProps) {
  return (
    <div className="panel-strong p-6 sm:p-8">
      <p className="eyebrow">{eyebrow}</p>
      <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground">{title}</h1>
      <p className="mt-4 max-w-3xl text-lg leading-7 text-muted">{description}</p>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {bullets.map((bullet, index) => (
          <div key={bullet} className="rounded-[24px] border border-border/70 bg-white/75 p-5">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-soft font-mono text-sm font-semibold text-accent">
              0{index + 1}
            </div>
            <p className="mt-4 text-sm leading-6 text-muted">{bullet}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
