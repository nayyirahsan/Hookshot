import { useState } from "react";
import type { DeadLetter } from "../api/client";
import { api } from "../api/client";

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
      <div className="mb-4 flex justify-end">
        <button
          onClick={handleRetryAll}
          disabled={deadLetters.length === 0 || loading === "all"}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading === "all" ? "Retrying…" : "Bulk Retry All"}
        </button>
      </div>
      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-3">Event Type</th>
              <th className="px-4 py-3">Endpoint</th>
              <th className="px-4 py-3">Retries</th>
              <th className="px-4 py-3">Last Error</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {deadLetters.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  No dead letters
                </td>
              </tr>
            ) : (
              deadLetters.map((dl) => (
                <tr key={dl.id} className="border-t border-slate-800">
                  <td className="px-4 py-3 font-mono">{dl.event_type ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{dl.endpoint_url ?? "—"}</td>
                  <td className="px-4 py-3">{dl.retry_count}</td>
                  <td className="px-4 py-3 text-red-400">{dl.last_error ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-400">
                    {new Date(dl.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleRetry(dl.id)}
                      disabled={loading === dl.id}
                      className="rounded bg-slate-700 px-3 py-1 text-xs hover:bg-slate-600 disabled:opacity-50"
                    >
                      {loading === dl.id ? "…" : "Retry"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
