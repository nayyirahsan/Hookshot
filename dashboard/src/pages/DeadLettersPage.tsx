import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type DeadLetter } from "../api/client";
import DeadLetterQueue from "../components/DeadLetterQueue";

export default function DeadLettersPage() {
  const [deadLetters, setDeadLetters] = useState<DeadLetter[]>([]);

  async function load() {
    const res = await api.getDeadLetters();
    setDeadLetters(res.items);
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <Link to="/" className="text-sm text-indigo-400 hover:text-indigo-300">
        ← Back to dashboard
      </Link>
      <h1 className="mt-4 text-2xl font-bold">Dead Letter Queue</h1>
      <p className="mt-1 text-slate-400">Events that exceeded max delivery attempts</p>
      <div className="mt-6">
        <DeadLetterQueue deadLetters={deadLetters} onRetry={load} />
      </div>
    </div>
  );
}
