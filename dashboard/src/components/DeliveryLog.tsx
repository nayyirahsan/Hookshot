import type { Delivery } from "../api/client";

interface Props {
  deliveries: Delivery[];
}

function statusLabel(outcome: string): string {
  if (outcome === "success") return "success";
  if (outcome === "failure" || outcome === "timeout" || outcome === "rejected") {
    return outcome === "failure" ? "failed" : "retried";
  }
  return outcome;
}

function statusClass(outcome: string): string {
  if (outcome === "success") return "text-emerald-400";
  return "text-amber-400";
}

export default function DeliveryLog({ deliveries }: Props) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-900 text-slate-400">
          <tr>
            <th className="px-4 py-3">Event Type</th>
            <th className="px-4 py-3">Endpoint</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Latency</th>
            <th className="px-4 py-3">Attempted At</th>
          </tr>
        </thead>
        <tbody>
          {deliveries.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                No deliveries yet
              </td>
            </tr>
          ) : (
            deliveries.map((d) => (
              <tr key={d.id} className="border-t border-slate-800">
                <td className="px-4 py-3 font-mono">{d.event_type}</td>
                <td className="px-4 py-3 font-mono text-xs">{d.endpoint_url}</td>
                <td className={`px-4 py-3 ${statusClass(d.outcome)}`}>
                  {statusLabel(d.outcome)}
                </td>
                <td className="px-4 py-3">{d.latency_ms ?? "—"} ms</td>
                <td className="px-4 py-3 text-slate-400">
                  {new Date(d.attempted_at).toLocaleString()}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
