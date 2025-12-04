import { Link } from "react-router-dom";
import type { Delivery } from "../api/client";
import { EmptyState, OutcomeBadge, Panel, Timestamp } from "./ui";

interface Props {
  deliveries: Delivery[];
}

export default function DeliveryLog({ deliveries }: Props) {
  return (
    <Panel className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-hairline text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            <th className="px-4 py-2.5">Event</th>
            <th className="px-4 py-2.5">Endpoint</th>
            <th className="px-4 py-2.5">Attempt</th>
            <th className="px-4 py-2.5">Outcome</th>
            <th className="px-4 py-2.5 text-right">Latency</th>
            <th className="px-4 py-2.5 text-right">When</th>
          </tr>
        </thead>
        <tbody>
          {deliveries.length === 0 ? (
            <tr>
              <td colSpan={6}>
                <EmptyState title="No deliveries yet — ingest an event to see the feed" />
              </td>
            </tr>
          ) : (
            deliveries.map((d) => (
              <tr
                key={d.id}
                className="row-in border-b border-hairline/50 last:border-0 hover:bg-slate-800/20"
              >
                <td className="px-4 py-2.5 font-mono text-xs text-slate-300">{d.event_type}</td>
                <td className="max-w-[220px] truncate px-4 py-2.5 font-mono text-xs text-slate-400">
                  <Link to={`/endpoints/${d.endpoint_id}`} className="hover:text-sky-400">
                    {d.endpoint_url.replace(/^https?:\/\//, "")}
                  </Link>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-500">
                  #{d.attempt_number}
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
  );
}
