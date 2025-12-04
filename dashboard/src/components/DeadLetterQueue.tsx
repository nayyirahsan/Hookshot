import { useState } from "react";
import { Link } from "react-router-dom";
import type { DeadLetter } from "../api/client";
import { api } from "../api/client";
import { EmptyState, Panel, Timestamp } from "./ui";

interface Props {
  deadLetters: DeadLetter[];
  onRetry: () => void;
}

export default function DeadLetterQueue({ deadLetters, onRetry }: Props) {
  const [loading, setLoading] = useState<string | null>(null);

  async function handleRetry(id: string) {
    setLoading(id);
    try {
      await api.retryDeadLetter(id);
      onRetry();
    } finally {
      setLoading(null);
    }
  }

  async function handleRetryAll() {
    setLoading("all");
    try {
      await api.retryAllDeadLetters();
      onRetry();
    } finally {
      setLoading(null);
    }
  }

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <button
          onClick={handleRetryAll}
          disabled={deadLetters.length === 0 || loading === "all"}
          className="rounded border border-sky-500/40 bg-sky-500/10 px-4 py-1.5 font-mono text-xs font-medium text-sky-300 transition hover:bg-sky-500/20 disabled:opacity-40"
        >
          {loading === "all" ? "requeueing…" : `retry all (${deadLetters.length})`}
        </button>
      </div>
      <Panel className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-hairline text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              <th className="px-4 py-2.5">Event</th>
              <th className="px-4 py-2.5">Endpoint</th>
              <th className="px-4 py-2.5 text-right">Attempts</th>
              <th className="px-4 py-2.5">Last error</th>
              <th className="px-4 py-2.5 text-right">Dead-lettered</th>
              <th className="px-4 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {deadLetters.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <EmptyState title="Queue is empty — every delivery found its way" />
                </td>
              </tr>
            ) : (
              deadLetters.map((dl) => (
                <tr
                  key={dl.id}
                  className="row-in border-b border-hairline/50 last:border-0 hover:bg-slate-800/20"
                >
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-300">
                    {dl.event_type ?? "—"}
                  </td>
                  <td className="max-w-[240px] truncate px-4 py-2.5 font-mono text-xs text-slate-400">
                    <Link to={`/endpoints/${dl.endpoint_id}`} className="hover:text-sky-400">
                      {dl.endpoint_url?.replace(/^https?:\/\//, "") ?? "—"}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs text-slate-400">
                    {dl.retry_count}
                  </td>
                  <td className="max-w-[260px] truncate px-4 py-2.5 font-mono text-xs text-red-400/90">
                    {dl.last_error ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <Timestamp iso={dl.created_at} />
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      onClick={() => handleRetry(dl.id)}
                      disabled={loading === dl.id}
                      className="rounded border border-hairline px-3 py-1 font-mono text-[11px] text-slate-300 transition hover:border-sky-500/40 hover:text-sky-300 disabled:opacity-40"
                    >
                      {loading === dl.id ? "…" : "retry"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
