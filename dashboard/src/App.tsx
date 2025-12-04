import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api, type Health, type Stats } from "./api/client";
import Dashboard from "./pages/Dashboard";
import DeadLettersPage from "./pages/DeadLettersPage";
import EndpointDetail from "./pages/EndpointDetail";

function WorkerStatus({ health }: { health: Health | null }) {
  const ok = health?.worker === "ok";
  return (
    <div className="flex items-center gap-2 rounded border border-hairline px-2.5 py-1.5">
      <span
        className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-400 live-dot" : "bg-amber-400"}`}
      />
      <span className="font-mono text-[11px] text-slate-400">
        worker {ok ? "online" : "degraded"}
      </span>
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const load = () => {
      api.getHealth().then(setHealth).catch(() => setHealth(null));
      api.getStats().then(setStats).catch(() => {});
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  const tab = ({ isActive }: { isActive: boolean }) =>
    `rounded px-3 py-1.5 text-sm transition ${
      isActive ? "bg-slate-800/80 text-slate-100" : "text-slate-400 hover:text-slate-200"
    }`;

  return (
    <div>
      <nav className="sticky top-0 z-10 border-b border-hairline bg-ink/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2.5">
              <svg width="22" height="22" viewBox="0 0 22 22" className="text-sky-400">
                <path
                  d="M4 15 L15 4 M15 4 h-5 M15 4 v5 M7 18 a3 3 0 1 1-4-4"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  fill="none"
                />
              </svg>
              <span className="text-base font-semibold tracking-tight">
                Hookshot
                <span className="ml-2 hidden font-mono text-[10px] font-normal uppercase tracking-[0.18em] text-slate-500 sm:inline">
                  adaptive delivery engine
                </span>
              </span>
            </div>
            <div className="flex items-center gap-1">
              <NavLink to="/" end className={tab}>
                Overview
              </NavLink>
              <NavLink to="/dead-letters" className={tab}>
                Dead letters
                {stats && stats.dead_letter_count > 0 && (
                  <span className="ml-1.5 rounded bg-red-500/15 px-1.5 py-0.5 font-mono text-[10px] text-red-400">
                    {stats.dead_letter_count}
                  </span>
                )}
              </NavLink>
            </div>
          </div>
          <WorkerStatus health={health} />
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/endpoints/:id" element={<EndpointDetail />} />
        <Route path="/dead-letters" element={<DeadLettersPage />} />
      </Routes>
    </div>
  );
}
