from dataclasses import dataclass
from unittest.mock import patch

from worker.health_model import (
    MAX_OBSERVATION_RATIO,
    PROBE_BETA,
    compute_adaptive_delay,
    update_health_model,
)


@dataclass
class MockEndpoint:
    ema_recovery_ms: float = 30000.0
    consecutive_failures: int = 0
    failure_rate: float = 0.0
    health_score: float = 1.0


def no_jitter():
    return patch("worker.health_model.random.random", return_value=0.5)


def test_ema_converges_on_recovery_time():
    endpoint = MockEndpoint(ema_recovery_ms=30000.0)
    for _ in range(10):
        update_health_model(endpoint, success=True, recovery_ms=90000.0)
    assert 85000 < endpoint.ema_recovery_ms < 95000


def test_ema_can_learn_downward():
    """First probe sits below the estimate, so a fast endpoint's EMA shrinks."""
    endpoint = MockEndpoint(ema_recovery_ms=30000.0)
    for _ in range(10):
        update_health_model(endpoint, success=True, recovery_ms=5000.0)
    assert endpoint.ema_recovery_ms < 6000


def test_recovery_observation_is_capped():
    """One absurd observation (idle gap after a dead-letter) can't wreck the EMA."""
    endpoint = MockEndpoint(ema_recovery_ms=10000.0)
    update_health_model(endpoint, success=True, recovery_ms=1_000_000.0)
    capped = MAX_OBSERVATION_RATIO * 10000.0
    assert endpoint.ema_recovery_ms == 0.3 * capped + 0.7 * 10000.0


def test_first_probe_below_estimate():
    """At outage start the first retry lands at PROBE_BETA x the estimate,
    which is what lets the model discover faster recovery than it believes."""
    endpoint = MockEndpoint(ema_recovery_ms=30000.0)
    with no_jitter():
        delay = compute_adaptive_delay(endpoint, 1, elapsed_in_outage_s=0.0)
    assert abs(delay - 30.0 * PROBE_BETA) < 0.1


def test_probe_grid_escalates_past_estimate():
    """Deep into an outage the grid doubles, so delays scale with elapsed
    time rather than hammering the endpoint at a fixed interval."""
    endpoint = MockEndpoint(ema_recovery_ms=10000.0)
    with no_jitter():
        delay = compute_adaptive_delay(endpoint, 6, elapsed_in_outage_s=100.0)
    # Probes at 5, 7.5, 11.25, 22.5, 45, 90, 180s → next after 100s is 180s.
    assert 60.0 < delay <= 85.0


def test_adaptive_faster_than_fixed_for_learned_fast_endpoint():
    """An endpoint that historically recovers in ~5s gets probed at ~2.5s,
    not at the 8s a 1s-base exponential would impose by attempt 4."""
    endpoint = MockEndpoint(ema_recovery_ms=5000.0)
    with no_jitter():
        first_delay = compute_adaptive_delay(endpoint, 1, elapsed_in_outage_s=0.0)
    assert first_delay < 3.0


def test_health_score_degrades_on_failures():
    endpoint = MockEndpoint()
    for _ in range(5):
        update_health_model(endpoint, success=False)
    assert endpoint.health_score <= 0.5
    assert endpoint.consecutive_failures == 5


def test_health_score_recovers_on_success():
    endpoint = MockEndpoint()
    for _ in range(5):
        update_health_model(endpoint, success=False)
    for _ in range(3):
        update_health_model(endpoint, success=True, recovery_ms=5000.0)
    assert endpoint.health_score > 0.7
