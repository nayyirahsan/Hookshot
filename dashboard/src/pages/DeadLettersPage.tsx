import { useEffect, useState } from "react";
import { api, type DeadLetter } from "../api/client";
import DeadLetterQueue from "../components/DeadLetterQueue";

export default function DeadLettersPage() {
  const [deadLetters, setDeadLetters] = useState<DeadLetter[]>([]);
  const [total, setTotal] = useState(0);

  async function load() {
    const res = await api.getDeadLetters();
    setDeadLetters(res.items);
    setTotal(res.total);
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Dead letter queue</h1>
          <p className="mt-1 text-sm text-slate-400">
            Deliveries that exhausted all retry attempts. Retrying re-enters the normal delivery
            pipeline; receivers dedupe on the event ID.
          </p>
        </div>
        <span className="font-mono text-xs text-slate-500">{total} total</span>
      </div>
      <DeadLetterQueue deadLetters={deadLetters} onRetry={load} />
    </div>
  );
}
