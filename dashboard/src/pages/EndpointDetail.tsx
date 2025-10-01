import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { api, type Delivery, type Endpoint } from "../api/client";
import HealthScoreCard from "../components/HealthScoreCard";

export default function EndpointDetail() {
  const { id } = useParams<{ id: string }>();
  const [endpoint, setEndpoint] = useState<Endpoint | null>(null);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!id) return;
    api.getEndpoint(id).then(setEndpoint);
  }, [id]);

  useEffect(() => {
    if (!id) return;
    api.getEndpointDeliveries(id, page).then((res) => {
      setDeliveries(res.items);
      setTotal(res.total);
    });
  }, [id, page]);

  if (!endpoint) {
    return <div className="p-8 text-slate-400">Loading…</div>;
  }

  const chartData = [...deliveries]
    .reverse()
    .filter((d) => d.latency_ms !== null)
    .map((d) => ({
      time: new Date(d.attempted_at).toLocaleTimeString(),
      latency: d.latency_ms,
    }));

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <Link to="/" className="text-sm text-indigo-400 hover:text-indigo-300">
        ← Back to dashboard
      </Link>
      <h1 className="mt-4 font-mono text-xl">{endpoint.url}</h1>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <HealthScoreCard endpoint={endpoint} />
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          <h3 className="text-sm font-medium text-slate-400">Latency Timeline</h3>
          <div className="mt-4 h-48">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="time" stroke="#94a3b8" fontSize={10} />
                  <YAxis stroke="#94a3b8" fontSize={10} />
                  <Tooltip
                    contentStyle={{ background: "#1e293b", border: "1px solid #334155" }}
                  />
                  <Line type="monotone" dataKey="latency" stroke="#818cf8" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-slate-500">No latency data yet</p>
            )}
          </div>
        </div>
      </div>

      <section className="mt-8">
        <h2 className="mb-4 text-lg font-semibold">Delivery History</h2>
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-slate-400">
              <tr>
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Event Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">Latency</th>
                <th className="px-4 py-3">Attempted At</th>
              </tr>
            </thead>
            <tbody>
              {deliveries.map((d) => (
                <tr key={d.id} className="border-t border-slate-800">
                  <td className="px-4 py-3">{d.attempt_number}</td>
                  <td className="px-4 py-3 font-mono">{d.event_type}</td>
                  <td className="px-4 py-3">{d.outcome}</td>
                  <td className="px-4 py-3">{d.status_code ?? "—"}</td>
                  <td className="px-4 py-3">{d.latency_ms ?? "—"} ms</td>
                  <td className="px-4 py-3 text-slate-400">
                    {new Date(d.attempted_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {totalPages > 1 && (
          <div className="mt-4 flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded bg-slate-800 px-3 py-1 text-sm disabled:opacity-50"
            >
              Prev
            </button>
            <span className="px-3 py-1 text-sm text-slate-400">
              Page {page} of {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded bg-slate-800 px-3 py-1 text-sm disabled:opacity-50"
            >
              Next
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
