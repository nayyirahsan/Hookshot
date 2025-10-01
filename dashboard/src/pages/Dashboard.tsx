import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Delivery, type Endpoint, type Stats } from "../api/client";
import DeliveryLog from "../components/DeliveryLog";
import EndpointList from "../components/EndpointList";

export default function Dashboard() {
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);

  async function load() {
    const [eps, dels, st] = await Promise.all([
      api.getEndpoints(),
      api.getDeliveries(50),
      api.getStats(),
    ]);
    setEndpoints(eps);
    setDeliveries(dels);
    setStats(st);
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Hookshot</h1>
          <p className="text-slate-400">Adaptive webhook delivery engine</p>
        </div>
        <Link
          to="/dead-letters"
          className="rounded-lg border border-slate-700 px-4 py-2 text-sm hover:bg-slate-900"
        >
          Dead Letters
          {stats && stats.dead_letter_count > 0 && (
            <span className="ml-2 rounded-full bg-red-600 px-2 py-0.5 text-xs">
              {stats.dead_letter_count}
            </span>
          )}
        </Link>
      </header>

      {stats && (
        <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="Events Today" value={stats.events_today.toString()} />
          <StatCard label="Success Rate" value={`${stats.delivery_success_rate}%`} />
          <StatCard label="Mean Latency" value={`${stats.mean_delivery_latency_ms} ms`} />
          <StatCard label="Dead Letters" value={stats.dead_letter_count.toString()} />
        </div>
      )}

      <section className="mb-8">
        <h2 className="mb-4 text-lg font-semibold">Endpoints</h2>
        <EndpointList endpoints={endpoints} />
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold">Recent Deliveries</h2>
        <DeliveryLog deliveries={deliveries} />
      </section>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
    </div>
  );
}
