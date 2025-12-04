import type { ReactNode } from "react";

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-hairline bg-panel/80 backdrop-blur-sm ${className}`}>
      {children}
    </div>
  );
}

export function MicroLabel({ children }: { children: ReactNode }) {
  return (
    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
      {children}
    </p>
  );
}

const OUTCOME_STYLES: Record<string, string> = {
  success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
  failure: "bg-red-500/10 text-red-400 border-red-500/25",
  timeout: "bg-amber-500/10 text-amber-400 border-amber-500/25",
  rejected: "bg-orange-500/10 text-orange-400 border-orange-500/25",
};

export function OutcomeBadge({ outcome, statusCode }: { outcome: string; statusCode?: number | null }) {
  const style = OUTCOME_STYLES[outcome] ?? "bg-slate-500/10 text-slate-400 border-slate-500/25";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 font-mono text-[11px] font-medium ${style}`}
    >
      {outcome}
      {statusCode != null && <span className="opacity-60">{statusCode}</span>}
    </span>
  );
}

export function HealthBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score > 0.8 ? "bg-emerald-400" : score > 0.5 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs text-slate-400">{pct}</span>
    </div>
  );
}

export function relativeTime(iso: string): string {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function Timestamp({ iso }: { iso: string }) {
  return (
    <span className="font-mono text-xs text-slate-500" title={new Date(iso).toLocaleString()}>
      {relativeTime(iso)}
    </span>
  );
}

export function formatMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60_000).toFixed(1)}m`;
}

export function EmptyState({ title, hint }: { title: string; hint?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
      <div className="h-8 w-8 rounded border border-dashed border-slate-700" />
      <p className="text-sm text-slate-400">{title}</p>
      {hint && <div className="max-w-xl text-xs text-slate-600">{hint}</div>}
    </div>
  );
}
