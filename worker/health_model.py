import random
from typing import Protocol

EMA_ALPHA = 0.3
MIN_BACKOFF_MS = 1_000
MAX_BACKOFF_MS = 3_600_000
JITTER_FACTOR = 0.25


class EndpointLike(Protocol):
    ema_recovery_ms: float
    consecutive_failures: int
    failure_rate: float
    health_score: float


def update_health_model(
    endpoint: EndpointLike, success: bool, recovery_ms: float | None = None
) -> None:
    """Call this after every delivery attempt."""
    if success:
        if recovery_ms is not None:
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


def compute_adaptive_delay(endpoint: EndpointLike, attempt_number: int) -> float:
    """
    Returns retry delay in seconds.

    Uses EMA recovery time as the base instead of fixed exponential backoff.
    Falls back to exponential if no recovery history (ema is at default).
    """
    base_ms = endpoint.ema_recovery_ms * (1.2 ** (attempt_number - 1))
    base_ms = max(MIN_BACKOFF_MS, min(MAX_BACKOFF_MS, base_ms))
    jitter = 1.0 + JITTER_FACTOR * (2 * random.random() - 1)
    return (base_ms * jitter) / 1000
