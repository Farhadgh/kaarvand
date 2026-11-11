import { cn } from "@/lib/cn";
import { statusLabels } from "@/lib/copy";

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("card", className)}>{children}</div>;
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-ink-100 px-5 py-4">
      <div>
        <h2 className="text-base font-bold text-ink-900">{title}</h2>
        {subtitle ? <p className="muted mt-0.5">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "default" | "warning" | "danger" | "success";
}) {
  const tones = {
    default: "text-ink-900",
    warning: "text-amber-600",
    danger: "text-rose-600",
    success: "text-emerald-600",
  } as const;

  return (
    <div className="card card-body">
      <p className="text-sm text-ink-500">{label}</p>
      <p className={cn("mt-2 text-2xl font-bold tabular", tones[tone])}>{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-400">{hint}</p> : null}
    </div>
  );
}

const badgeTones: Record<string, string> = {
  completed: "bg-emerald-50 text-emerald-700",
  ok: "bg-emerald-50 text-emerald-700",
  online: "bg-emerald-50 text-emerald-700",
  published: "bg-emerald-50 text-emerald-700",
  running: "bg-brand-50 text-brand-700",
  paired: "bg-brand-50 text-brand-700",
  waiting_approval: "bg-amber-50 text-amber-700",
  pending: "bg-amber-50 text-amber-700",
  queued: "bg-ink-100 text-ink-600",
  draft: "bg-ink-100 text-ink-600",
  offline: "bg-ink-100 text-ink-600",
  failed: "bg-rose-50 text-rose-700",
  error: "bg-rose-50 text-rose-700",
  cancelled: "bg-ink-100 text-ink-600",
  high: "bg-rose-50 text-rose-700",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-emerald-50 text-emerald-700",
};

export function Badge({
  value,
  label,
  className,
}: {
  value: string;
  label?: string;
  className?: string;
}) {
  return (
    <span className={cn("badge", badgeTones[value] ?? "bg-ink-100 text-ink-600", className)}>
      {label ?? statusLabels[value] ?? value}
    </span>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <div className="mb-1 flex h-12 w-12 items-center justify-center rounded-full bg-ink-100 text-ink-400">
        ∅
      </div>
      <p className="font-medium text-ink-800">{title}</p>
      {description ? <p className="muted max-w-md">{description}</p> : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {message}
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-ink-400">{hint}</span> : null}
    </label>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-8 text-sm text-ink-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-300 border-t-brand-600" />
      {label ?? "در حال بارگذاری…"}
    </div>
  );
}

export function ProgressBar({ value, max }: { value: number; max: number }) {
  const percent = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  const tone = percent >= 90 ? "bg-rose-500" : percent >= 70 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-ink-100">
      <div className={cn("h-full rounded-full", tone)} style={{ width: `${percent}%` }} />
    </div>
  );
}

export function KeyValue({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <span className="text-sm text-ink-500">{label}</span>
      <span className="text-sm font-medium text-ink-800">{children}</span>
    </div>
  );
}
