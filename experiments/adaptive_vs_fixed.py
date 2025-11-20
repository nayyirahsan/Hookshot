"""Reproducible benchmark: adaptive (EMA) retry scheduling vs fixed exponential backoff.

Discrete-event simulation that imports the REAL production scheduling code
(worker.health_model.compute_adaptive_delay / update_health_model) — the
adaptive policy here is byte-for-byte what the worker runs. Time is simulated,
so 500 outages per scenario take milliseconds instead of days, and the run is
fully reproducible via --seed.

Model:
  * An endpoint suffers repeated outages; each outage duration is drawn from a
    lognormal distribution characteristic of that endpoint class.
  * One event arrives at a uniformly random moment during each outage and is
    (re)tried per policy until the outage has ended (delivery succeeds) or the
    attempt cap is hit (dead-lettered).
  * The adaptive policy carries endpoint EMA state across outages, exactly as
    the worker does via the endpoints table; recovery time is measured the
    same way (success time minus last failed attempt).
  * Both policies use the same ±25% jitter and the same 1h delay cap.
    Fixed baseline: 1s * 2^(attempt-1), the classic webhook backoff.

Usage:
  python -m experiments.adaptive_vs_fixed --seed 42 --outages 500 --warmup 50
"""

import argparse
import json
import random
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from worker.health_model import (
    JITTER_FACTOR,
    MAX_BACKOFF_MS,
    compute_adaptive_delay,
    update_health_model,
)

MAX_ATTEMPTS = 8  # mirrors settings.max_delivery_attempts

# Two fixed-exponential baselines: 1s base is the latency-aggressive extreme
# (8 attempts span only ~255s of wall time), 30s base is a production-typical
# schedule (spans ~2.1h). A single global policy has to pick one tradeoff;
# adaptive picks per endpoint.
POLICIES = {
    "fixed-1s": 1_000.0,
    "fixed-30s": 30_000.0,
    "adaptive": None,
}

SCENARIOS = {
    "fast-recovery": {"median_s": 5.0, "sigma": 0.5},
    "medium-recovery": {"median_s": 30.0, "sigma": 0.5},
    "slow-recovery": {"median_s": 240.0, "sigma": 0.4},
}


@dataclass
class SimEndpoint:
    """Duck-types worker.health_model.EndpointLike."""

    ema_recovery_ms: float = 30_000.0
    consecutive_failures: int = 0
    failure_rate: float = 0.0
    health_score: float = 1.0
    streak_started_at: float | None = field(default=None)  # sim-clock seconds


def fixed_delay(base_ms: float, attempt_number: int) -> float:
    delay_ms = min(base_ms * (2 ** (attempt_number - 1)), MAX_BACKOFF_MS)
    jitter = 1.0 + JITTER_FACTOR * (2 * random.random() - 1)
    return (delay_ms * jitter) / 1000


def deliver(policy: str, endpoint: SimEndpoint, arrival: float, outage_end: float,
            max_attempts: int) -> tuple[float | None, int]:
    """Returns (delivery latency in seconds or None if dead-lettered, attempts used).

    Mirrors worker.tasks.deliver_event exactly: streak start recorded on the
    first failure, recovery measured over the whole streak, probe delays
    computed from elapsed time in the outage.
    """
    t = arrival
    for attempt_number in range(1, max_attempts + 1):
        if t >= outage_end:
            if policy == "adaptive":
                recovery_ms = None
                if endpoint.consecutive_failures > 0 and endpoint.streak_started_at is not None:
                    recovery_ms = (t - endpoint.streak_started_at) * 1000
                endpoint.streak_started_at = None
                update_health_model(endpoint, success=True, recovery_ms=recovery_ms)
            return t - arrival, attempt_number

        if policy == "adaptive":
            if endpoint.consecutive_failures == 0 or endpoint.streak_started_at is None:
                endpoint.streak_started_at = t
            update_health_model(endpoint, success=False)
            elapsed = t - endpoint.streak_started_at
            t += compute_adaptive_delay(endpoint, attempt_number, elapsed_in_outage_s=elapsed)
        else:
            t += fixed_delay(POLICIES[policy], attempt_number)

    return None, max_attempts


def run_scenario(median_s: float, sigma: float, outages: int, warmup: int,
                 max_attempts: int, seed: int) -> dict:
    import math

    mu = math.log(median_s)
    results: dict[str, dict] = {}

    for policy in POLICIES:
        # Same seed per policy → every policy faces the identical outage
        # sequence and arrival times (paired comparison).
        random.seed(seed)
        endpoint = SimEndpoint()
        latencies: list[float] = []
        attempts_used: list[int] = []
        dead_letters = 0
        clock = 0.0

        for i in range(warmup + outages):
            duration = random.lognormvariate(mu, sigma)
            outage_start = clock
            outage_end = outage_start + duration
            arrival = outage_start + random.random() * duration

            latency, n = deliver(policy, endpoint, arrival, outage_end, max_attempts)

            if i >= warmup:
                attempts_used.append(n)
                if latency is None:
                    dead_letters += 1
                else:
                    latencies.append(latency)

            # Steady healthy traffic: an event shortly after recovery succeeds
            # first try. For adaptive this closes a streak left dangling by a
            # dead-letter (recovery observation is capped in the model).
            healthy_t = outage_end + 30.0
            deliver(policy, endpoint, healthy_t, healthy_t, max_attempts)
            clock = outage_end + 600.0

        latencies.sort()
        total = dead_letters + len(latencies)
        # Tail latency counting dead-letters as never-delivered (∞): fair
        # tail comparison — a policy must not look good by dropping the tail.
        p95_all_idx = int(total * 0.95)
        p95_all = latencies[p95_all_idx] if p95_all_idx < len(latencies) else None

        results[policy] = {
            "mean_latency_s": round(statistics.mean(latencies), 2),
            "p50_latency_s": round(latencies[len(latencies) // 2], 2),
            "p95_latency_delivered_s": round(latencies[int(len(latencies) * 0.95)], 2),
            "p95_latency_all_s": round(p95_all, 2) if p95_all is not None else "DLQ",
            "mean_attempts": round(statistics.mean(attempts_used), 2),
            "delivered_pct": round(100 * len(latencies) / total, 2),
            "dead_letter_rate_pct": round(100 * dead_letters / total, 2),
            "final_ema_s": round(endpoint.ema_recovery_ms / 1000, 1),
        }

    return results


def print_table(res: dict) -> None:
    print(f"{'':>10} {'mean':>8} {'p50':>8} {'p95(all)':>9} {'attempts':>9} "
          f"{'delivered':>10}")
    for policy in POLICIES:
        r = res[policy]
        p95 = r["p95_latency_all_s"]
        p95 = f"{p95:>8.1f}s" if isinstance(p95, float) else f"{p95:>9}"
        print(f"{policy:>10} {r['mean_latency_s']:>7.1f}s {r['p50_latency_s']:>7.1f}s "
              f"{p95} {r['mean_attempts']:>9.2f} {r['delivered_pct']:>9.1f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--outages", type=int, default=500, help="measured outages per scenario")
    parser.add_argument(
        "--warmup", type=int, default=50, help="unmeasured outages for EMA convergence"
    )
    parser.add_argument("--max-attempts", type=int, default=MAX_ATTEMPTS)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "results.json")
    args = parser.parse_args()

    all_results = {
        "config": vars(args) | {"out": str(args.out)},
        "scenarios": {},
    }

    for name, params in SCENARIOS.items():
        res = run_scenario(params["median_s"], params["sigma"], args.outages,
                           args.warmup, args.max_attempts, args.seed)
        all_results["scenarios"][name] = {"params": params, **res}
        print(f"\n=== {name} (median outage {params['median_s']}s, "
              f"{args.outages} outages, seed {args.seed}) ===")
        print_table(res)
        print(f"  adaptive learned EMA: {res['adaptive']['final_ema_s']}s")

    # Fleet aggregate: equal event volume per endpoint class.
    agg: dict[str, dict] = {}
    for policy in POLICIES:
        rows = [all_results["scenarios"][s][policy] for s in SCENARIOS]
        agg[policy] = {
            "mean_latency_s": round(statistics.mean(r["mean_latency_s"] for r in rows), 2),
            "mean_attempts": round(statistics.mean(r["mean_attempts"] for r in rows), 2),
            "delivered_pct": round(statistics.mean(r["delivered_pct"] for r in rows), 2),
            "dead_letter_rate_pct": round(
                statistics.mean(r["dead_letter_rate_pct"] for r in rows), 2
            ),
        }
    all_results["fleet_aggregate"] = agg

    print("\n=== fleet aggregate (equal volume across classes) ===")
    print(f"{'':>10} {'mean lat':>9} {'attempts':>9} {'delivered':>10}")
    for policy, r in agg.items():
        print(f"{policy:>10} {r['mean_latency_s']:>8.1f}s {r['mean_attempts']:>9.2f} "
              f"{r['delivered_pct']:>9.1f}%")

    args.out.write_text(json.dumps(all_results, indent=2))
    print(f"\nResults written to {args.out}")


if __name__ == "__main__":
    main()
