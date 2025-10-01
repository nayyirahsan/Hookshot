import time
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from api.config import get_settings
from api.database import SyncSessionLocal
from api.models import DeadLetter, DeliveryAttempt, Endpoint, Event
from worker.celery_app import celery_app
from worker.health_model import compute_adaptive_delay, update_health_model
from worker.hmac_signer import sign_payload

settings = get_settings()


@celery_app.task(bind=True, max_retries=0)
def deliver_event(self, event_id: str, endpoint_id: str, attempt_number: int = 1) -> None:
    with SyncSessionLocal() as db:
        event = db.get(Event, uuid.UUID(event_id))
        endpoint = db.get(Endpoint, uuid.UUID(endpoint_id))

        if not event or not endpoint or not endpoint.active:
            return

        existing_dl = db.execute(
            select(DeadLetter).where(
                DeadLetter.event_id == event.id,
                DeadLetter.endpoint_id == endpoint.id,
            )
        ).scalar_one_or_none()
        if existing_dl:
            return

        if attempt_number > settings.max_delivery_attempts:
            last_attempt = db.execute(
                select(DeliveryAttempt)
                .where(
                    DeliveryAttempt.event_id == event.id,
                    DeliveryAttempt.endpoint_id == endpoint.id,
                )
                .order_by(DeliveryAttempt.attempt_number.desc())
                .limit(1)
            ).scalar_one_or_none()

            dead_letter = DeadLetter(
                event_id=event.id,
                endpoint_id=endpoint.id,
                final_attempt_at=last_attempt.attempted_at if last_attempt else datetime.now(UTC),
                retry_count=attempt_number - 1,
                last_error=last_attempt.error_message if last_attempt else "Max retries exceeded",
            )
            db.add(dead_letter)
            db.commit()
            return

        attempt_id = uuid.uuid4()
        attempt = DeliveryAttempt(
            id=attempt_id,
            event_id=event.id,
            endpoint_id=endpoint.id,
            attempt_number=attempt_number,
            outcome="failure",
        )
        db.add(attempt)
        db.commit()

        signature = sign_payload(event.payload, endpoint.secret)
        headers = {
            "X-Hookshot-Signature": signature,
            "X-Hookshot-Event": event.event_type,
            "X-Hookshot-Delivery": str(attempt_id),
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        status_code = None
        response_body = None
        outcome = "failure"
        error_message = None

        try:
            with httpx.Client(timeout=settings.http_timeout_seconds) as client:
                response = client.post(endpoint.url, json=event.payload, headers=headers)
                status_code = response.status_code
                response_body = response.text[:4096]
                latency_ms = int((time.monotonic() - start) * 1000)

                if 200 <= status_code < 300:
                    outcome = "success"
                    attempt.status_code = status_code
                    attempt.response_body = response_body
                    attempt.latency_ms = latency_ms
                    attempt.outcome = outcome
                    endpoint.last_success_at = datetime.now(UTC)

                    recovery_ms = None
                    if endpoint.last_failure_at:
                        recovery_ms = (
                            datetime.now(UTC) - endpoint.last_failure_at
                        ).total_seconds() * 1000

                    update_health_model(endpoint, success=True, recovery_ms=recovery_ms)
                    db.commit()
                    return

                outcome = "failure"
                error_message = f"HTTP {status_code}"
                attempt.status_code = status_code
                attempt.response_body = response_body
                attempt.latency_ms = latency_ms
                attempt.outcome = outcome
                attempt.error_message = error_message

        except httpx.TimeoutException:
            latency_ms = int((time.monotonic() - start) * 1000)
            outcome = "timeout"
            error_message = "Request timed out"
            attempt.latency_ms = latency_ms
            attempt.outcome = outcome
            attempt.error_message = error_message

        except httpx.RequestError as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            outcome = "rejected"
            error_message = str(exc)
            attempt.latency_ms = latency_ms
            attempt.outcome = outcome
            attempt.error_message = error_message

        endpoint.last_failure_at = datetime.now(UTC)
        update_health_model(endpoint, success=False)
        db.commit()

        delay = compute_adaptive_delay(endpoint, attempt_number)
        deliver_event.apply_async(
            args=[event_id, endpoint_id, attempt_number + 1],
            countdown=delay,
        )
