import { Link } from "react-router-dom";
import type { Endpoint } from "../api/client";

interface Props {
  endpoints: Endpoint[];
}

function truncateUrl(url: string, max = 40): string {
  return url.length > max ? `${url.slice(0, max)}…` : url;
}

function healthColor(score: number): string {
  if (score > 0.8) return "bg-emerald-500";
  if (score > 0.5) return "bg-amber-500";
  return "bg-red-500";
}

function lastStatus(endpoint: Endpoint): string {
  if (!endpoint.last_success_at && !endpoint.last_failure_at) return "No deliveries";
  if (endpoint.last_success_at && endpoint.last_failure_at) {
    return new Date(endpoint.last_success_at) > new Date(endpoint.last_failure_at)
      ? "Success"
      : "Failed";
  }
  return endpoint.last_success_at ? "Success" : "Failed";
}

export default function EndpointList({ endpoints }: Props) {
  if (endpoints.length === 0) {
    return (
      <p className="text-slate-500">No endpoints registered yet.</p>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {endpoints.map((endpoint) => (
        <Link
          key={endpoint.id}
          to={`/endpoints/${endpoint.id}`}
          className="rounded-xl border border-slate-800 bg-slate-900 p-4 transition hover:border-slate-600"
        >
          <p className="truncate font-mono text-sm" title={endpoint.url}>
            {truncateUrl(endpoint.url)}
          </p>
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Health</span>
              <span>{(endpoint.health_score * 100).toFixed(0)}%</span>
            </div>
            <div className="mt-1 h-2 w-full rounded-full bg-slate-800">
              <div
                className={`h-2 rounded-full ${healthColor(endpoint.health_score)}`}
                style={{ width: `${endpoint.health_score * 100}%` }}
              />
            </div>
          </div>
          <div className="mt-3 flex justify-between text-xs text-slate-500">
            <span>Last: {lastStatus(endpoint)}</span>
            <span>Failures: {endpoint.consecutive_failures}</span>
          </div>
        </Link>
      ))}
    </div>
  );
}
