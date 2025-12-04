import { useEffect, useState } from "react";
import { api, type Delivery, type Endpoint, type Stats } from "../api/client";
import DeliveryLog from "../components/DeliveryLog";
import EndpointList from "../components/EndpointList";
import { formatMs, MicroLabel, Panel } from "../components/ui";

const POLL_MS = 5000;

export default function Dashboard() {
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState(false);

  async function load() {
    try {
      const [eps, dels, st] = await Promise.all([
        api.getEndpoints(),
        api.getDeliveries(50),
        api.getStats(),
      ]);
      setEndpoints(eps);
      setDeliveries(dels);
      setStats(st);
      setError(false);
    } catch {
      setError(true);
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, POLL_MS);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {error && (
        <div className="mb-6 rounded border border-red-500/30 bg-red-500/10 px-4 py-2 font-mono text-xs text-red-400">
          API unreachable — is the server running on :8000?
        </div>
      )}

      <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Events today"
          value={stats ? stats.events_today.toLocaleString() : "—"}
        />
        <StatCard
          label="Delivery success"
          value={stats ? `${stats.delivery_success_rate}%` : "—"}
          tone={
            stats == null
              ? undefined
              : stats.delivery_success_rate >= 99
                ? "good"
                : stats.delivery_success_rate >= 90
                  ? "warn"
                  : "bad"
          }
        />
        <StatCard
          label="Mean delivery latency"
          value={stats ? formatMs(stats.mean_delivery_latency_ms) : "—"}
        />
        <StatCard
          label="Dead letters"
          value={stats ? stats.dead_letter_count.toLocaleString() : "—"}
          tone={stats == null ? undefined : stats.dead_letter_count > 0 ? "bad" : "good"}
        />
      </div>

      <section className="mb-8">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Endpoints
          </h2>
          <span className="font-mono text-xs text-slate-500">{endpoints.length} registered</span>
        </div>
        <EndpointList endpoints={endpoints} />
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Delivery feed
          </h2>
          <span className="flex items-center gap-1.5 font-mono text-[11px] text-emerald-400">
            <span className="live-dot h-1.5 w-1.5 rounded-full bg-emerald-400" />
            live · {POLL_MS / 1000}s
          </span>
        </div>
        <DeliveryLog deliveries={deliveries} />
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "good" | "warn" | "bad";
}) {
  const toneClass =
    tone === "good"
      ? "text-emerald-400"
      : tone === "warn"
        ? "text-amber-400"
        : tone === "bad"
          ? "text-red-400"
          : "text-slate-100";
  return (
    <Panel className="p-4">
      <MicroLabel>{label}</MicroLabel>
      <p className={`mt-2 font-mono text-2xl font-semibold ${toneClass}`}>{value}</p>
    </Panel>
  );
}
