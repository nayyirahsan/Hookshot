from celery import Celery

from api.config import get_settings

settings = get_settings()

celery_app = Celery(
    "hookshot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_always_eager,
    # At-least-once: ack only after the task finishes, and requeue the message
    # if the worker process dies mid-task. Without these, a crash between the
    # HTTP call and recording the outcome silently drops the delivery.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Must exceed the longest retry countdown (MAX_BACKOFF_MS = 1h), otherwise
    # Redis re-delivers still-scheduled retries and every retry runs twice.
    broker_transport_options={"visibility_timeout": 7200},
    beat_schedule={
        "reap-stuck-deliveries": {
            "task": "worker.tasks.reap_stuck_deliveries",
            "schedule": settings.reaper_interval_seconds,
        },
    },
)
