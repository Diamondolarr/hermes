type RecoveryCardProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

export function RecoveryCard({
  eyebrow,
  title,
  description,
  children,
  footer,
}: RecoveryCardProps) {
  return (
    <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-4xl items-center justify-center px-4 py-6">
      <div className="panel-strong soft-ring w-full max-w-xl overflow-hidden p-6 sm:p-8">
        <div className="rounded-[26px] bg-[linear-gradient(135deg,rgba(15,118,110,0.12),rgba(199,113,76,0.08))] p-5">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground">
            {title}
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-muted">{description}</p>
        </div>

        <div className="mt-6 rounded-[28px] border border-border/80 bg-white/76 p-5 sm:p-6">
          {children}
        </div>

        {footer ? <div className="mt-5 text-sm text-muted">{footer}</div> : null}
      </div>
    </div>
  );
}
