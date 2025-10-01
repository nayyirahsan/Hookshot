from dataclasses import dataclass
from unittest.mock import patch

from worker.health_model import compute_adaptive_delay, update_health_model


@dataclass
class MockEndpoint:
    ema_recovery_ms: float = 30000.0
    consecutive_failures: int = 0
    failure_rate: float = 0.0
    health_score: float = 1.0


def test_ema_converges_on_recovery_time():
    endpoint = MockEndpoint(ema_recovery_ms=30000.0)
    for _ in range(10):
        update_health_model(endpoint, success=True, recovery_ms=90000.0)
    assert 85000 < endpoint.ema_recovery_ms < 95000


def test_adaptive_delay_faster_than_fixed_backoff():
    endpoint = MockEndpoint(ema_recovery_ms=5000.0)
    attempt_number = 4
    fixed_exponential_ms = 1000 * (2**attempt_number)

    with patch("worker.health_model.random.random", return_value=0.5):
        adaptive_seconds = compute_adaptive_delay(endpoint, attempt_number)

    adaptive_ms = adaptive_seconds * 1000
    assert adaptive_ms < fixed_exponential_ms
    assert 5000 <= adaptive_ms <= 9000


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
