import pytest
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
