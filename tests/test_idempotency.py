import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from api.database import SyncSessionLocal
from api.models import DeliveryAttempt, Event
from tests.test_delivery import ingest_event, register_endpoint


@pytest.mark.asyncio
async def test_idempotency_key_deduplication(client, mock_httpx):
    from unittest.mock import MagicMock

    await register_endpoint(client, "http://example.com/webhook")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"
    mock_httpx.post.return_value = mock_response

    key = "unique-idem-key-12345"
    first = await ingest_event(client, key)
    second = await ingest_event(client, key)

    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    with SyncSessionLocal() as db:
        events = db.execute(select(Event)).scalars().all()
        assert len(events) == 1
        attempts = db.execute(select(func.count()).select_from(DeliveryAttempt)).scalar_one()
        assert attempts == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_ingestion(mock_httpx):
    """Simultaneous POSTs with the same key must produce exactly ONE event and
    ONE delivery. Uses the app's real per-request DB sessions (not the shared
    test session) so the requests genuinely race; the loser of the insert race
    hits the unique constraint and returns the winner's event.
    """
    from unittest.mock import MagicMock

    from api.main import app

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"
    mock_httpx.post.return_value = mock_response

    key = "concurrent-idem-key"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await register_endpoint(client, "http://example.com/webhook")
        responses = await asyncio.gather(*(ingest_event(client, key) for _ in range(5)))

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200, 200, 200, 200, 202], statuses
    assert len({r.json()["id"] for r in responses}) == 1

    with SyncSessionLocal() as db:
        events = db.execute(select(Event)).scalars().all()
        assert len(events) == 1
        attempts = db.execute(select(func.count()).select_from(DeliveryAttempt)).scalar_one()
        assert attempts == 1
