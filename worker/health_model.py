import random
from typing import Protocol

EMA_ALPHA = 0.3
MIN_BACKOFF_MS = 1_000
MAX_BACKOFF_MS = 3_600_000
JITTER_FACTOR = 0.25

# Probe schedule: retry at outage_start + ema * PROBE_BETA * growth^k.
# PROBE_BETA < 1 places the first probes BELOW the current estimate — without
# this the model can never learn that an endpoint recovers faster than it
# currently believes (a success observed at the probe time would only ever
# confirm the estimate, never shrink it). Growth is fine (1.5x) up to the
# estimate for low overshoot in the typical case, then doubles so the
# 8-attempt budget still covers outages ~18x longer than predicted (the
# remaining-time distribution is heavy-tailed; a tighter grid dead-letters
# the tail).
PROBE_BETA = 0.5
PROBE_GROWTH_NEAR = 1.5
PROBE_GROWTH_PAST = 2.0

# A single recovery observation may grow the EMA by at most this factor.
# Recovery is measured to the first success after the streak, which with
# sparse traffic (or after a dead-letter) can span long idle time that the
# endpoint was actually healthy for; without the cap one such observation
# wrecks the estimate.
MAX_OBSERVATION_RATIO = 3.0


class EndpointLike(Protocol):
    ema_recovery_ms: float
    consecutive_failures: int
    failure_rate: float
    health_score: float


def update_health_model(
    endpoint: EndpointLike, success: bool, recovery_ms: float | None = None
) -> None:
    """Call this after every delivery attempt.

    recovery_ms must be the duration of the whole failure streak (first
    failure of the outage → this success), NOT the gap since the last failed
    attempt. The last-gap variant equals the retry delay itself, so the EMA
    would chase its own backoff and ratchet upward forever.
    """
    if success:
        if recovery_ms is not None:
            recovery_ms = min(recovery_ms, MAX_OBSERVATION_RATIO * endpoint.ema_recovery_ms)
            endpoint.ema_recovery_ms = (
                EMA_ALPHA * recovery_ms + (1 - EMA_ALPHA) * endpoint.ema_recovery_ms
            )
        endpoint.consecutive_failures = 0
        endpoint.failure_rate = max(0.0, endpoint.failure_rate - 0.1)
    else:
        endpoint.consecutive_failures += 1
        endpoint.failure_rate = min(1.0, endpoint.failure_rate + 0.1)

    endpoint.health_score = (
        0.6 * (1.0 - endpoint.failure_rate)
        + 0.4 * max(0.0, 1.0 - endpoint.consecutive_failures / 10.0)
    )


def compute_adaptive_delay(
    endpoint: EndpointLike,
    attempt_number: int,
    elapsed_in_outage_s: float | None = None,
) -> float:
    """Returns retry delay in seconds.

    Geometric probe search anchored at the outage start: probe times are
    outage_start + ema * PROBE_BETA * PROBE_GROWTH^k, and the delay returned
    is the gap from now to the next probe not yet in the past. Anchoring at
    the outage start (rather than "now") means the schedule targets the
    predicted recovery moment instead of compounding delays on top of however
    long we have already waited.

    elapsed_in_outage_s is time since the first failure of the current streak.
    Without it (no streak context, e.g. legacy callers), falls back to gentle
    exponential growth on the EMA.
    """
    if elapsed_in_outage_s is None:
        base_ms = endpoint.ema_recovery_ms * (1.2 ** (attempt_number - 1))
    else:
        elapsed_ms = elapsed_in_outage_s * 1000
        probe_ms = max(endpoint.ema_recovery_ms * PROBE_BETA, MIN_BACKOFF_MS)
        while probe_ms <= elapsed_ms + MIN_BACKOFF_MS and probe_ms < MAX_BACKOFF_MS:
            growth = (
                PROBE_GROWTH_NEAR
                if probe_ms < endpoint.ema_recovery_ms
                else PROBE_GROWTH_PAST
            )
            probe_ms *= growth
        base_ms = probe_ms - elapsed_ms

    base_ms = max(MIN_BACKOFF_MS, min(MAX_BACKOFF_MS, base_ms))
    jitter = 1.0 + JITTER_FACTOR * (2 * random.random() - 1)
    return (base_ms * jitter) / 1000
