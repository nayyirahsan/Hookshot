import { Link } from "react-router-dom";
import type { Endpoint } from "../api/client";
import { EmptyState, formatMs, HealthBar, MicroLabel, Panel, relativeTime } from "./ui";

interface Props {
  endpoints: Endpoint[];
}

function lastActivity(endpoint: Endpoint): { label: string; className: string } {
  const success = endpoint.last_success_at ? new Date(endpoint.last_success_at) : null;
  const failure = endpoint.last_failure_at ? new Date(endpoint.last_failure_at) : null;
  if (!success && !failure) return { label: "no deliveries yet", className: "text-slate-500" };
  if (success && (!failure || success > failure)) {
    return {
      label: `ok ${relativeTime(endpoint.last_success_at!)}`,
      className: "text-emerald-400",
    };
  }
  return { label: `failing ${relativeTime(endpoint.last_failure_at!)}`, className: "text-red-400" };
}

export default function EndpointList({ endpoints }: Props) {
  if (endpoints.length === 0) {
    return (
      <Panel>
        <EmptyState
          title="No endpoints registered"
          hint={
            <code className="mt-1 block rounded bg-slate-900 p-2 text-left font-mono text-[10px] leading-relaxed text-slate-400">
              curl -X POST localhost:8000/api/endpoints -H 'Content-Type: application/json' -d
              '{'{'}"url": "https://…", "secret": "…", "event_types": ["order.created"]{'}'}'
            </code>
          }
        />
      </Panel>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {endpoints.map((endpoint) => {
        const activity = lastActivity(endpoint);
        return (
          <Link key={endpoint.id} to={`/endpoints/${endpoint.id}`} className="group">
            <Panel className="h-full p-4 transition group-hover:border-slate-600">
              <div className="flex items-start justify-between gap-2">
                <p className="truncate font-mono text-[13px] text-slate-200" title={endpoint.url}>
                  {endpoint.url.replace(/^https?:\/\//, "")}
                </p>
                {!endpoint.active && (
                  <span className="rounded border border-slate-600 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
                    inactive
                  </span>
                )}
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {endpoint.event_types.slice(0, 3).map((t) => (
                  <span
                    key={t}
                    className="rounded bg-sky-500/10 px-1.5 py-0.5 font-mono text-[10px] text-sky-400"
                  >
                    {t}
                  </span>
                ))}
              </div>
              <div className="mt-4">
                <MicroLabel>Health</MicroLabel>
                <div className="mt-1.5">
                  <HealthBar score={endpoint.health_score} />
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between font-mono text-[11px]">
                <span className={activity.className}>{activity.label}</span>
                <span className="text-slate-500" title="Learned recovery time (EMA)">
                  rec {formatMs(endpoint.ema_recovery_ms)}
                </span>
              </div>
            </Panel>
          </Link>
        );
      })}
    </div>
  );
}
