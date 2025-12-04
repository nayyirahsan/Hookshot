import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type Delivery, type Endpoint } from "../api/client";
import HealthScoreCard from "../components/HealthScoreCard";
import { EmptyState, MicroLabel, OutcomeBadge, Panel, Timestamp } from "../components/ui";

const PAGE_SIZE = 20;

export default function EndpointDetail() {
  const { id } = useParams<{ id: string }>();
  const [endpoint, setEndpoint] = useState<Endpoint | null>(null);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!id) return;
    const load = () => api.getEndpoint(id).then(setEndpoint).catch(() => {});
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, [id]);

  useEffect(() => {
    if (!id) return;
    api.getEndpointDeliveries(id, page).then((res) => {
      setDeliveries(res.items);
      setTotal(res.total);
    });
  }, [id, page]);

  if (!endpoint) {
    return <div className="p-8 font-mono text-sm text-slate-500">loading…</div>;
  }

  const chartData = [...deliveries]
    .reverse()
    .filter((d) => d.latency_ms !== null)
    .map((d) => ({
      time: new Date(d.attempted_at).toLocaleTimeString(),
      latency: d.latency_ms,
      outcome: d.outcome,
    }));

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <Link to="/" className="font-mono text-xs text-sky-400 hover:text-sky-300">
        ← overview
      </Link>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-lg text-slate-100">{endpoint.url}</h1>
        <span
          className={`rounded border px-2 py-0.5 font-mono text-[11px] ${
            endpoint.active
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
              : "border-slate-600 text-slate-500"
          }`}
        >
          {endpoint.active ? "active" : "inactive"}
        </span>
        {endpoint.event_types.map((t) => (
          <span
            key={t}
            className="rounded bg-sky-500/10 px-2 py-0.5 font-mono text-[11px] text-sky-400"
          >
            {t}
          </span>
        ))}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <HealthScoreCard endpoint={endpoint} />
        <Panel className="p-5">
          <div className="flex items-baseline justify-between">
            <h3 className="text-sm font-semibold text-slate-300">Delivery latency</h3>
            <MicroLabel>last {chartData.length} attempts</MicroLabel>
          </div>
          <div className="mt-4 h-52">
            {chartData.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1c2430" />
                  <XAxis
                    dataKey="time"
                    stroke="#475569"
                    fontSize={10}
                    tickLine={false}
                    fontFamily="IBM Plex Mono"
                  />
                  <YAxis
                    stroke="#475569"
                    fontSize={10}
                    tickLine={false}
                    fontFamily="IBM Plex Mono"
                    unit="ms"
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#0f141c",
                      border: "1px solid #1c2430",
                      borderRadius: 6,
                      fontFamily: "IBM Plex Mono",
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="latency"
                    stroke="#38bdf8"
                    strokeWidth={1.5}
                    dot={{ r: 2, fill: "#38bdf8", strokeWidth: 0 }}
                    activeDot={{ r: 4 }}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState title="Not enough latency data yet" />
            )}
          </div>
        </Panel>
      </div>

      <section className="mt-8">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Delivery history
          </h2>
          <span className="font-mono text-xs text-slate-500">{total} attempts</span>
        </div>
        <Panel className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-hairline text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                <th className="px-4 py-2.5">Attempt</th>
                <th className="px-4 py-2.5">Event</th>
                <th className="px-4 py-2.5">Outcome</th>
                <th className="px-4 py-2.5 text-right">Latency</th>
                <th className="px-4 py-2.5 text-right">When</th>
              </tr>
            </thead>
            <tbody>
              {deliveries.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <EmptyState title="No deliveries to this endpoint yet" />
                  </td>
                </tr>
              ) : (
                deliveries.map((d) => (
                  <tr key={d.id} className="border-b border-hairline/50 last:border-0">
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-500">
                      #{d.attempt_number}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-300">
                      {d.event_type}
                    </td>
                    <td className="px-4 py-2.5">
                      <OutcomeBadge outcome={d.outcome} statusCode={d.status_code} />
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-xs text-slate-400">
                      {d.latency_ms != null ? `${d.latency_ms} ms` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Timestamp iso={d.attempted_at} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Panel>
        {totalPages > 1 && (
          <div className="mt-3 flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded border border-hairline px-3 py-1 font-mono text-xs text-slate-300 transition hover:border-slate-600 disabled:opacity-40"
            >
              ← prev
            </button>
            <span className="font-mono text-xs text-slate-500">
              {page} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded border border-hairline px-3 py-1 font-mono text-xs text-slate-300 transition hover:border-slate-600 disabled:opacity-40"
            >
              next →
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
