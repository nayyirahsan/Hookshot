from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import DeadLetter, DeliveryAttempt, Event
from api.schemas import HealthResponse, StatsResponse
from worker.celery_app import celery_app

router = APIRouter(tags=["health"])

DELIVERY_COUNTER = Counter(
    "hookshot_deliveries_total",
    "Total delivery attempts",
    ["outcome"],
)
DELIVERY_LATENCY = Histogram(
    "hookshot_delivery_latency_ms",
    "Delivery latency in milliseconds",
    buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
)
DEAD_LETTER_GAUGE = Gauge("hookshot_dead_letters", "Number of dead letters")


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    await db.execute(text("SELECT 1"))

    worker_status = "degraded"
    try:
        inspect = celery_app.control.inspect(timeout=2.0)
        ping = inspect.ping()
        if ping:
            worker_status = "ok"
    except Exception:
        worker_status = "degraded"

    return HealthResponse(status="ok", worker=worker_status)


@router.get("/metrics")
async def metrics(db: AsyncSession = Depends(get_db)) -> Response:
    outcomes = await db.execute(
        select(DeliveryAttempt.outcome, func.count())
        .group_by(DeliveryAttempt.outcome)
    )
    for outcome, count in outcomes.all():
        DELIVERY_COUNTER.labels(outcome=outcome).inc(count)

    latencies = await db.execute(
        select(DeliveryAttempt.latency_ms).where(DeliveryAttempt.latency_ms.is_not(None))
    )
    for (latency_ms,) in latencies.all():
        DELIVERY_LATENCY.observe(latency_ms)

    dl_count = await db.execute(select(func.count()).select_from(DeadLetter))
    DEAD_LETTER_GAUGE.set(dl_count.scalar_one())

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)) -> StatsResponse:
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    events_today_result = await db.execute(
        select(func.count()).select_from(Event).where(Event.created_at >= today_start)
    )
    events_today = events_today_result.scalar_one()

    total_attempts_result = await db.execute(select(func.count()).select_from(DeliveryAttempt))
    total_attempts = total_attempts_result.scalar_one()

    success_result = await db.execute(
        select(func.count())
        .select_from(DeliveryAttempt)
        .where(DeliveryAttempt.outcome == "success")
    )
    successes = success_result.scalar_one()

    latency_result = await db.execute(
        select(func.avg(DeliveryAttempt.latency_ms)).where(
            DeliveryAttempt.latency_ms.is_not(None)
        )
    )
    mean_latency = latency_result.scalar_one() or 0.0

    dl_result = await db.execute(select(func.count()).select_from(DeadLetter))
    dead_letter_count = dl_result.scalar_one()

    success_rate = (successes / total_attempts * 100) if total_attempts > 0 else 100.0

    return StatsResponse(
        events_today=events_today,
        delivery_success_rate=round(success_rate, 2),
        mean_delivery_latency_ms=round(float(mean_latency), 2),
        dead_letter_count=dead_letter_count,
    )
