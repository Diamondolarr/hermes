import { StatusBadge } from "@/components/ui/status-badge";

type MetricCardProps = {
  label: string;
  value: string;
  change: string;
  tone: "accent" | "warm" | "ink";
};

const toneMap = {
  accent: "bg-accent-soft",
  warm: "bg-[rgba(199,113,76,0.12)]",
  ink: "bg-[rgba(17,32,30,0.08)]",
};

export function MetricCard({ label, value, change, tone }: MetricCardProps) {
  return (
    <article className="panel p-5">
      <div className={`rounded-[22px] p-4 ${toneMap[tone]}`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="eyebrow">{label}</p>
            <p className="heading-display mt-3 text-4xl font-semibold text-foreground">{value}</p>
          </div>
          <StatusBadge tone={tone}>{tone === "warm" ? "Focus" : "Healthy"}</StatusBadge>
        </div>
        <p className="mt-5 text-sm leading-6 text-muted">{change}</p>
      </div>
    </article>
  );
}
