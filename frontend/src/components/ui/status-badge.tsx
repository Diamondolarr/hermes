type StatusBadgeProps = {
  children: React.ReactNode;
  tone?: "accent" | "warning" | "danger" | "ink" | "neutral" | "warm";
};

const toneClasses: Record<NonNullable<StatusBadgeProps["tone"]>, string> = {
  accent: "bg-accent-soft text-accent",
  warning: "bg-amber-100 text-amber-800",
  danger: "bg-rose-100 text-rose-800",
  ink: "bg-[rgba(17,32,30,0.08)] text-foreground",
  neutral: "bg-white/75 text-foreground",
  warm: "bg-[rgba(199,113,76,0.14)] text-[var(--warm)]",
};

export function StatusBadge({ children, tone = "neutral" }: StatusBadgeProps) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${toneClasses[tone]}`}>
      {children}
    </span>
  );
}
