import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import and_, any_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from api.config import get_settings
from api.database import SyncSessionLocal
from api.models import DeadLetter, DeliveryAttempt, Endpoint, Event
from worker.celery_app import celery_app
from worker.health_model import compute_adaptive_delay, update_health_model
from worker.hmac_signer import sign_payload

settings = get_settings()


def _lock_endpoint(db: Session, endpoint_id: uuid.UUID) -> Endpoint:
    """Row-lock the endpoint so concurrent deliveries don't lose health updates."""
    return db.execute(
        select(Endpoint)
        .where(Endpoint.id == endpoint_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


def _dead_letter(db: Session, event: Event, endpoint: Endpoint, attempt_number: int) -> None:
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
    try:
        db.commit()
    except IntegrityError:
        # A concurrent duplicate of the final attempt already dead-lettered this.
        db.rollback()


@celery_app.task(bind=True, max_retries=0)
def deliver_event(self, event_id: str, endpoint_id: str, attempt_number: int = 1) -> None:
    with SyncSessionLocal() as db:
        event = db.get(Event, uuid.UUID(event_id))
        endpoint = db.get(Endpoint, uuid.UUID(endpoint_id))

        if not event or not endpoint or not endpoint.active:
            return

        # With acks_late the broker re-delivers this task if the worker dies
        # after the HTTP call but before the ack; the reaper can also re-fire
        # it. Never deliver again once a success is recorded.
        already_succeeded = db.execute(
            select(DeliveryAttempt.id)
            .where(
                DeliveryAttempt.event_id == event.id,
                DeliveryAttempt.endpoint_id == endpoint.id,
                DeliveryAttempt.outcome == "success",
            )
            .limit(1)
        ).scalar_one_or_none()
        if already_succeeded:
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
            _dead_letter(db, event, endpoint, attempt_number)
            return

        # Intent record: committed before the HTTP call so a worker crash
        # mid-flight leaves evidence the reaper can act on. next_retry_at
        # stays NULL until a retry is actually scheduled.
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
            # Stable across retries — this is the receiver's dedup key.
            "X-Hookshot-Event-Id": str(event.id),
            "X-Hookshot-Delivery": str(attempt_id),
            "X-Hookshot-Attempt": str(attempt_number),
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        error_message = None

        try:
            with httpx.Client(timeout=settings.http_timeout_seconds) as client:
                response = client.post(endpoint.url, json=event.payload, headers=headers)
                latency_ms = int((time.monotonic() - start) * 1000)
                attempt.status_code = response.status_code
                attempt.response_body = response.text[:4096]
                attempt.latency_ms = latency_ms

                if 200 <= response.status_code < 300:
                    attempt.outcome = "success"
                    now = datetime.now(UTC)
                    locked = _lock_endpoint(db, endpoint.id)

                    # Recovery time = duration of the whole failure streak.
                    # Measuring from last_failure_at instead would just echo
                    # the previous retry delay back into the EMA (feedback
                    # loop that ratchets delays upward forever).
                    recovery_ms = None
                    if locked.consecutive_failures > 0 and locked.failure_streak_started_at:
                        recovery_ms = (
                            now - locked.failure_streak_started_at
                        ).total_seconds() * 1000

                    locked.last_success_at = now
                    locked.failure_streak_started_at = None
                    update_health_model(locked, success=True, recovery_ms=recovery_ms)
                    db.commit()
                    return

                attempt.outcome = "failure"
                error_message = f"HTTP {response.status_code}"
                attempt.error_message = error_message

        except httpx.TimeoutException:
            attempt.latency_ms = int((time.monotonic() - start) * 1000)
            attempt.outcome = "timeout"
            attempt.error_message = "Request timed out"

        except httpx.RequestError as exc:
            attempt.latency_ms = int((time.monotonic() - start) * 1000)
            attempt.outcome = "rejected"
            attempt.error_message = str(exc)

        now = datetime.now(UTC)
        locked = _lock_endpoint(db, endpoint.id)
        if locked.consecutive_failures == 0 or locked.failure_streak_started_at is None:
            locked.failure_streak_started_at = now
        locked.last_failure_at = now
        update_health_model(locked, success=False)

        elapsed_s = (now - locked.failure_streak_started_at).total_seconds()
        delay = compute_adaptive_delay(locked, attempt_number, elapsed_in_outage_s=elapsed_s)
        # Persist the lease before enqueueing: if the worker dies between this
        # commit and apply_async, the reaper sees an overdue next_retry_at and
        # re-fires the delivery.
        attempt.next_retry_at = now + timedelta(seconds=delay)
        db.commit()

        deliver_event.apply_async(
            args=[event_id, endpoint_id, attempt_number + 1],
            countdown=delay,
        )


@celery_app.task
def reap_stuck_deliveries() -> dict[str, int]:
    """Crash-recovery sweep, run by beat every reaper_interval_seconds.

    Catches the three loss windows of the happy path:
      1. API crashed after committing an event but before fanning it out
         (event with no attempts for a subscribed endpoint).
      2. Worker died mid-HTTP-call (attempt stuck at outcome='failure' with
         next_retry_at NULL past the HTTP timeout).
      3. Retry message lost (next_retry_at long overdue with no newer attempt).
    Re-fired deliveries are safe: deliver_event refuses to run again after a
    recorded success, and receivers dedupe on X-Hookshot-Event-Id.
    """
    now = datetime.now(UTC)
    grace = timedelta(seconds=settings.reaper_grace_seconds)
    requeued_orphans = 0
    requeued_stale = 0

    with SyncSessionLocal() as db:
        attempt_exists = (
            select(DeliveryAttempt.id)
            .where(
                DeliveryAttempt.event_id == Event.id,
                DeliveryAttempt.endpoint_id == Endpoint.id,
            )
            .exists()
        )
        dl_exists_for_event = (
            select(DeadLetter.id)
            .where(
                DeadLetter.event_id == Event.id,
                DeadLetter.endpoint_id == Endpoint.id,
            )
            .exists()
        )
        orphans = db.execute(
            select(Event.id, Endpoint.id).where(
                Event.created_at < now - grace,
                Endpoint.active.is_(True),
                Event.event_type == any_(Endpoint.event_types),
                Endpoint.created_at <= Event.created_at,
                ~attempt_exists,
                ~dl_exists_for_event,
            )
        ).all()
        for event_id, endpoint_id in orphans:
            deliver_event.apply_async(args=[str(event_id), str(endpoint_id), 1])
            requeued_orphans += 1

        latest_sq = (
            select(DeliveryAttempt)
            .distinct(DeliveryAttempt.event_id, DeliveryAttempt.endpoint_id)
            .order_by(
                DeliveryAttempt.event_id,
                DeliveryAttempt.endpoint_id,
                DeliveryAttempt.attempt_number.desc(),
            )
            .subquery()
        )
        latest = aliased(DeliveryAttempt, latest_sq)
        dl_exists_for_attempt = (
            select(DeadLetter.id)
            .where(
                DeadLetter.event_id == latest.event_id,
                DeadLetter.endpoint_id == latest.endpoint_id,
            )
            .exists()
        )
        stale = (
            db.execute(
                select(latest).where(
                    latest.outcome != "success",
                    ~dl_exists_for_attempt,
                    or_(
                        # Retry was scheduled but never ran.
                        and_(
                            latest.next_retry_at.is_not(None),
                            latest.next_retry_at < now - grace,
                        ),
                        # Worker died mid-flight before recording an outcome.
                        and_(
                            latest.next_retry_at.is_(None),
                            latest.attempted_at
                            < now - timedelta(seconds=settings.http_timeout_seconds) - grace,
                        ),
                    ),
                )
            )
            .scalars()
            .all()
        )
        for attempt in stale:
            # Bump the lease so the next sweep doesn't re-fire this pair
            # while the re-enqueued task is still waiting in the queue.
            attempt.next_retry_at = now + grace
            db.commit()
            deliver_event.apply_async(
                args=[str(attempt.event_id), str(attempt.endpoint_id), attempt.attempt_number + 1]
            )
            requeued_stale += 1

    return {"orphan_events": requeued_orphans, "stale_deliveries": requeued_stale}
