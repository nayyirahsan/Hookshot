from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy import func, select

from api.database import SyncSessionLocal
from api.models import DeadLetter, DeliveryAttempt


async def register_endpoint(client, url: str, event_types: list[str] | None = None):
    response = await client.post(
        "/api/endpoints",
        json={
            "url": url,
            "secret": "test-secret",
            "event_types": event_types or ["order.created"],
        },
    )
    assert response.status_code == 201
    return response.json()


async def ingest_event(client, idempotency_key: str, event_type: str = "order.created"):
    return await client.post(
        "/api/events",
        json={"event_type": event_type, "data": {"order_id": "123"}},
        headers={"Idempotency-Key": idempotency_key},
    )


@pytest.mark.asyncio
async def test_successful_delivery(client, mock_httpx):
    await register_endpoint(client, "http://example.com/webhook")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"
    mock_httpx.post.return_value = mock_response

    response = await ingest_event(client, "idem-success-1")
    assert response.status_code == 202

    with SyncSessionLocal() as db:
        attempts = db.execute(select(DeliveryAttempt)).scalars().all()
        assert len(attempts) == 1
        assert attempts[0].status_code == 200
        assert attempts[0].outcome == "success"


@pytest.mark.asyncio
async def test_retry_on_500(client, mock_httpx):
    await register_endpoint(client, "http://example.com/webhook")

    responses = []
    for status in [500, 500, 200]:
        mock_response = MagicMock()
        mock_response.status_code = status
        mock_response.text = "error" if status != 200 else "ok"
        responses.append(mock_response)

    mock_httpx.post.side_effect = responses

    response = await ingest_event(client, "idem-retry-500")
    assert response.status_code == 202

    with SyncSessionLocal() as db:
        attempts = db.execute(
            select(DeliveryAttempt).order_by(DeliveryAttempt.attempt_number)
        ).scalars().all()
        assert len(attempts) == 3
        assert attempts[-1].outcome == "success"


@pytest.mark.asyncio
async def test_dead_letter_after_max_retries(client, mock_httpx, monkeypatch):
    monkeypatch.setenv("MAX_DELIVERY_ATTEMPTS", "3")
    get_settings = __import__("api.config", fromlist=["get_settings"]).get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(
        "worker.tasks.settings",
        __import__("api.config", fromlist=["get_settings"]).get_settings(),
    )

    await register_endpoint(client, "http://example.com/webhook")

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "error"
    mock_httpx.post.return_value = mock_response

    response = await ingest_event(client, "idem-dead-letter")
    assert response.status_code == 202

    with SyncSessionLocal() as db:
        dead_letters = db.execute(select(DeadLetter)).scalars().all()
        assert len(dead_letters) == 1
        assert dead_letters[0].retry_count >= 3


@pytest.mark.asyncio
async def test_idempotency_key_deduplication(client, mock_httpx):
    await register_endpoint(client, "http://example.com/webhook")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"
    mock_httpx.post.return_value = mock_response

    first = await ingest_event(client, "idem-dedup")
    second = await ingest_event(client, "idem-dedup")

    assert first.status_code == 202
    assert second.status_code == 200

    with SyncSessionLocal() as db:
        count = db.execute(select(func.count()).select_from(DeliveryAttempt)).scalar_one()
        assert count == 1


@pytest.mark.asyncio
async def test_timeout_triggers_retry(client, mock_httpx):
    await register_endpoint(client, "http://example.com/webhook")

    def raise_timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    mock_httpx.post.side_effect = raise_timeout

    response = await ingest_event(client, "idem-timeout")
    assert response.status_code == 202

    with SyncSessionLocal() as db:
        attempts = db.execute(select(DeliveryAttempt)).scalars().all()
        assert len(attempts) >= 1
        assert attempts[0].outcome == "timeout"


@pytest.mark.asyncio
async def test_connection_refused_triggers_retry(client):
    await register_endpoint(client, "http://localhost:19999/webhook")

    response = await ingest_event(client, "idem-conn-refused")
    assert response.status_code == 202

    with SyncSessionLocal() as db:
        attempts = db.execute(select(DeliveryAttempt)).scalars().all()
        assert len(attempts) >= 1
        assert attempts[0].outcome == "rejected"


@pytest.mark.asyncio
async def test_dead_letter_manual_retry(client, mock_httpx, monkeypatch):
    monkeypatch.setenv("MAX_DELIVERY_ATTEMPTS", "1")
    get_settings = __import__("api.config", fromlist=["get_settings"]).get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(
        "worker.tasks.settings",
        __import__("api.config", fromlist=["get_settings"]).get_settings(),
    )

    await register_endpoint(client, "http://example.com/webhook")

    fail_response = MagicMock()
    fail_response.status_code = 500
    fail_response.text = "error"

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = "ok"

    mock_httpx.post.side_effect = [fail_response, ok_response]

    await ingest_event(client, "idem-manual-retry")

    with SyncSessionLocal() as db:
        dead_letter = db.execute(select(DeadLetter)).scalar_one()
        dead_letter_id = str(dead_letter.id)

    retry_response = await client.post(f"/api/dead-letters/{dead_letter_id}/retry")
    assert retry_response.status_code == 200

    with SyncSessionLocal() as db:
        attempts = db.execute(select(DeliveryAttempt)).scalars().all()
        assert len(attempts) >= 2
        dead_letters = db.execute(select(DeadLetter)).scalars().all()
        assert len(dead_letters) == 0


@pytest.mark.asyncio
async def test_inactive_endpoint_skipped(client, mock_httpx):
    endpoint = await register_endpoint(client, "http://example.com/webhook")
    await client.delete(f"/api/endpoints/{endpoint['id']}")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"
    mock_httpx.post.return_value = mock_response

    response = await ingest_event(client, "idem-inactive")
    assert response.status_code == 202

    with SyncSessionLocal() as db:
        count = db.execute(select(func.count()).select_from(DeliveryAttempt)).scalar_one()
        assert count == 0
