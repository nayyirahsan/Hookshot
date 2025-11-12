"""Worker/API crash recovery: every loss window must be repaired by the reaper.

These tests simulate crashes by writing the exact DB state a crash leaves
behind, then assert reap_stuck_deliveries re-drives the delivery.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from api.database import SyncSessionLocal
from api.models import DeliveryAttempt, Endpoint, Event
from worker.tasks import deliver_event, reap_stuck_deliveries

STALE = datetime.now(UTC) - timedelta(minutes=30)


def _seed_endpoint_and_event(**event_kwargs) -> tuple[str, str]:
    with SyncSessionLocal() as db:
        endpoint = Endpoint(
            id=uuid.uuid4(),
            url="http://example.com/webhook",
            secret="test-secret",
            event_types=["order.created"],
            active=True,
            created_at=STALE - timedelta(minutes=5),
        )
        event = Event(
            id=uuid.uuid4(),
            idempotency_key=f"crash-{uuid.uuid4()}",
            event_type="order.created",
            payload={"order_id": "123"},
            created_at=STALE,
            **event_kwargs,
        )
        db.add_all([endpoint, event])
        db.commit()
        return str(event.id), str(endpoint.id)


def _ok_response(mock_httpx):
    response = MagicMock()
    response.status_code = 200
    response.text = "ok"
    mock_httpx.post.return_value = response


@pytest.mark.asyncio
async def test_reaper_requeues_event_never_fanned_out(client, mock_httpx):
    """API crashed after committing the event but before enqueueing delivery."""
    event_id, endpoint_id = _seed_endpoint_and_event()
    _ok_response(mock_httpx)

    result = reap_stuck_deliveries.apply().get()
    assert result["orphan_events"] == 1

    with SyncSessionLocal() as db:
        attempts = db.execute(select(DeliveryAttempt)).scalars().all()
        assert len(attempts) == 1
        assert attempts[0].outcome == "success"


@pytest.mark.asyncio
async def test_reaper_requeues_delivery_crashed_mid_flight(client, mock_httpx):
    """Worker died between the intent record and recording an outcome.

    The stranded attempt row has outcome='failure' and next_retry_at NULL —
    indistinguishable from a delivery that succeeded on the wire but whose
    worker died before the success commit. The reaper re-delivers; the
    receiver dedupes on X-Hookshot-Event-Id.
    """
    event_id, endpoint_id = _seed_endpoint_and_event()
    with SyncSessionLocal() as db:
        db.add(
            DeliveryAttempt(
                event_id=uuid.UUID(event_id),
                endpoint_id=uuid.UUID(endpoint_id),
                attempt_number=1,
                outcome="failure",
                attempted_at=STALE,
                next_retry_at=None,
            )
        )
        db.commit()
    _ok_response(mock_httpx)

    result = reap_stuck_deliveries.apply().get()
    assert result["stale_deliveries"] == 1

    with SyncSessionLocal() as db:
        attempts = (
            db.execute(select(DeliveryAttempt).order_by(DeliveryAttempt.attempt_number))
            .scalars()
            .all()
        )
        assert [a.attempt_number for a in attempts] == [1, 2]
        assert attempts[-1].outcome == "success"


@pytest.mark.asyncio
async def test_reaper_requeues_lost_retry(client, mock_httpx):
    """Retry lease expired: next_retry_at long past with no newer attempt."""
    event_id, endpoint_id = _seed_endpoint_and_event()
    with SyncSessionLocal() as db:
        db.add(
            DeliveryAttempt(
                event_id=uuid.UUID(event_id),
                endpoint_id=uuid.UUID(endpoint_id),
                attempt_number=1,
                outcome="failure",
                attempted_at=STALE,
                next_retry_at=STALE + timedelta(seconds=5),
            )
        )
        db.commit()
    _ok_response(mock_httpx)

    result = reap_stuck_deliveries.apply().get()
    assert result["stale_deliveries"] == 1

    with SyncSessionLocal() as db:
        attempts = db.execute(select(DeliveryAttempt)).scalars().all()
        assert any(a.outcome == "success" for a in attempts)


@pytest.mark.asyncio
async def test_reaper_leaves_pending_retry_alone(client, mock_httpx):
    """A retry scheduled for the future is not the reaper's business."""
    event_id, endpoint_id = _seed_endpoint_and_event()
    with SyncSessionLocal() as db:
        db.add(
            DeliveryAttempt(
                event_id=uuid.UUID(event_id),
                endpoint_id=uuid.UUID(endpoint_id),
                attempt_number=1,
                outcome="failure",
                attempted_at=datetime.now(UTC),
                next_retry_at=datetime.now(UTC) + timedelta(seconds=60),
            )
        )
        db.commit()

    result = reap_stuck_deliveries.apply().get()
    assert result == {"orphan_events": 0, "stale_deliveries": 0}
    assert mock_httpx.post.call_count == 0


@pytest.mark.asyncio
async def test_redelivered_task_after_success_does_not_deliver_twice(client, mock_httpx):
    """acks_late redelivery of an already-succeeded task must be a no-op."""
    event_id, endpoint_id = _seed_endpoint_and_event()
    _ok_response(mock_httpx)

    deliver_event.apply(args=[event_id, endpoint_id, 1])
    assert mock_httpx.post.call_count == 1

    # Broker redelivers the same message after a simulated worker loss.
    deliver_event.apply(args=[event_id, endpoint_id, 1])
    assert mock_httpx.post.call_count == 1

    with SyncSessionLocal() as db:
        attempts = db.execute(select(DeliveryAttempt)).scalars().all()
        assert len(attempts) == 1
