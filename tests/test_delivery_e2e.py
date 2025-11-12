"""End-to-end delivery tests against a real local HTTP server.

Unlike the mocked-httpx tests, these exercise the full wire path: real
sockets, real timeouts, and receiver-side verification of the HMAC signature
and dedup headers.
"""

import hashlib
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from sqlalchemy import select

from api.database import SyncSessionLocal
from api.models import DeadLetter, DeliveryAttempt
from tests.test_delivery import ingest_event

SECRET = "e2e-secret"


class ScriptedHandler(BaseHTTPRequestHandler):
    """Serves responses from server.script (list of dicts), records requests.

    Script steps: {"status": 500} or {"sleep": 3.0, "status": 200}.
    An exhausted script answers 200.
    """

    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.server.requests.append(
            {"headers": {k: v for k, v in self.headers.items()}, "body": body}
        )
        step = self.server.script.pop(0) if self.server.script else {"status": 200}
        if "sleep" in step:
            time.sleep(step["sleep"])
        self.send_response(step.get("status", 200))
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok" if step.get("status", 200) < 400 else b"error")

    def log_message(self, *args):
        pass


@pytest.fixture
def webhook_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ScriptedHandler)
    server.script = []
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.url = f"http://127.0.0.1:{server.server_address[1]}/webhook"
    yield server
    server.shutdown()
    thread.join(timeout=5)


async def _register(client, url: str):
    response = await client.post(
        "/api/endpoints",
        json={"url": url, "secret": SECRET, "event_types": ["order.created"]},
    )
    assert response.status_code == 201
    return response.json()


def _verify_signature(request: dict) -> bool:
    payload = json.loads(request["body"])
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    expected = hmac.new(SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(request["headers"]["X-Hookshot-Signature"], f"sha256={expected}")


@pytest.mark.asyncio
async def test_success_delivers_signed_payload(client, webhook_server):
    await _register(client, webhook_server.url)
    response = await ingest_event(client, "e2e-success")
    assert response.status_code == 202

    assert len(webhook_server.requests) == 1
    request = webhook_server.requests[0]
    assert _verify_signature(request)
    assert request["headers"]["X-Hookshot-Event"] == "order.created"
    assert request["headers"]["X-Hookshot-Attempt"] == "1"


@pytest.mark.asyncio
async def test_500_retries_with_stable_event_id(client, webhook_server):
    """Receiver-side dedup contract: X-Hookshot-Event-Id must be identical on
    every attempt, while X-Hookshot-Delivery identifies the individual try."""
    webhook_server.script = [{"status": 500}, {"status": 500}, {"status": 200}]
    await _register(client, webhook_server.url)
    await ingest_event(client, "e2e-retry-500")

    requests = webhook_server.requests
    assert len(requests) == 3
    event_ids = {r["headers"]["X-Hookshot-Event-Id"] for r in requests}
    delivery_ids = {r["headers"]["X-Hookshot-Delivery"] for r in requests}
    assert len(event_ids) == 1
    assert len(delivery_ids) == 3
    assert [r["headers"]["X-Hookshot-Attempt"] for r in requests] == ["1", "2", "3"]

    with SyncSessionLocal() as db:
        attempts = (
            db.execute(select(DeliveryAttempt).order_by(DeliveryAttempt.attempt_number))
            .scalars()
            .all()
        )
        assert [a.outcome for a in attempts] == ["failure", "failure", "success"]


@pytest.mark.asyncio
async def test_timeout_then_success(client, webhook_server):
    """First response arrives after the 2s client timeout; retry succeeds."""
    webhook_server.script = [{"sleep": 3.0, "status": 200}, {"status": 200}]
    await _register(client, webhook_server.url)
    await ingest_event(client, "e2e-timeout")

    with SyncSessionLocal() as db:
        attempts = (
            db.execute(select(DeliveryAttempt).order_by(DeliveryAttempt.attempt_number))
            .scalars()
            .all()
        )
        assert attempts[0].outcome == "timeout"
        assert attempts[-1].outcome == "success"


@pytest.mark.asyncio
async def test_dead_letter_after_max_retries_real_server(client, webhook_server, monkeypatch):
    monkeypatch.setattr("worker.tasks.settings.max_delivery_attempts", 3)
    webhook_server.script = [{"status": 500}] * 10
    await _register(client, webhook_server.url)
    await ingest_event(client, "e2e-dead-letter")

    assert len(webhook_server.requests) == 3
    with SyncSessionLocal() as db:
        dead_letters = db.execute(select(DeadLetter)).scalars().all()
        assert len(dead_letters) == 1
        assert dead_letters[0].last_error == "HTTP 500"
