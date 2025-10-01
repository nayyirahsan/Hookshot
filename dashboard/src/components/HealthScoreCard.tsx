import type { Endpoint } from "../api/client";

interface Props {
  endpoint: Endpoint;
}

function healthColor(score: number): string {
  if (score > 0.8) return "bg-emerald-500";
  if (score > 0.5) return "bg-amber-500";
  return "bg-red-500";
}

export default function HealthScoreCard({ endpoint }: Props) {
  const pct = Math.round(endpoint.health_score * 100);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <h3 className="text-sm font-medium text-slate-400">Health Model</h3>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-slate-500">EMA Recovery</p>
          <p className="font-mono">{(endpoint.ema_recovery_ms / 1000).toFixed(1)}s</p>
        </div>
        <div>
          <p className="text-slate-500">Health Score</p>
          <p className="font-mono">{endpoint.health_score.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-slate-500">Failure Rate</p>
          <p className="font-mono">{(endpoint.failure_rate * 100).toFixed(0)}%</p>
        </div>
        <div>
          <p className="text-slate-500">Consecutive Failures</p>
          <p className="font-mono">{endpoint.consecutive_failures}</p>
        </div>
      </div>
      <div className="mt-4">
        <div className="h-2 w-full rounded-full bg-slate-800">
          <div
            className={`h-2 rounded-full ${healthColor(endpoint.health_score)}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
