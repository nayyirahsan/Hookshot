import type { Endpoint } from "../api/client";
import { formatMs, HealthBar, MicroLabel, Panel, relativeTime } from "./ui";

interface Props {
  endpoint: Endpoint;
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div title={hint}>
      <MicroLabel>{label}</MicroLabel>
      <p className="mt-1 font-mono text-lg text-slate-200">{value}</p>
    </div>
  );
}

export default function HealthScoreCard({ endpoint }: Props) {
  return (
    <Panel className="p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-300">Adaptive health model</h3>
        <span className="font-mono text-[11px] text-slate-500">
          score {endpoint.health_score.toFixed(2)}
        </span>
      </div>
      <div className="mt-3">
        <HealthBar score={endpoint.health_score} />
      </div>
      <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5">
        <Metric
          label="Learned recovery (EMA)"
          value={formatMs(endpoint.ema_recovery_ms)}
          hint="Exponential moving average of how long this endpoint's outages last. Retries are scheduled on a probe grid around this estimate."
        />
        <Metric
          label="First retry probe"
          value={formatMs(Math.max(endpoint.ema_recovery_ms * 0.5, 1000))}
          hint="On a fresh failure, the first retry lands at 0.5 x the learned recovery time"
        />
        <Metric label="Failure rate" value={`${(endpoint.failure_rate * 100).toFixed(0)}%`} />
        <Metric label="Consecutive failures" value={String(endpoint.consecutive_failures)} />
        <Metric
          label="Last success"
          value={endpoint.last_success_at ? relativeTime(endpoint.last_success_at) : "never"}
        />
        <Metric
          label="Last failure"
          value={endpoint.last_failure_at ? relativeTime(endpoint.last_failure_at) : "never"}
        />
      </div>
    </Panel>
  );
}
