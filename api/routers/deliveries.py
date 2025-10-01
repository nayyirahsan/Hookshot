from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import DeliveryAttempt, Endpoint, Event
from api.schemas import DeliveryWithContext

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.get("", response_model=list[DeliveryWithContext])
async def list_recent_deliveries(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[DeliveryWithContext]:
    query = (
        select(DeliveryAttempt, Event.event_type, Endpoint.url)
        .join(Event, DeliveryAttempt.event_id == Event.id)
        .join(Endpoint, DeliveryAttempt.endpoint_id == Endpoint.id)
        .order_by(DeliveryAttempt.attempted_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(query)).all()

    return [
        DeliveryWithContext(
            id=attempt.id,
            event_id=attempt.event_id,
            endpoint_id=attempt.endpoint_id,
            event_type=event_type,
            endpoint_url=url,
            attempt_number=attempt.attempt_number,
            status_code=attempt.status_code,
            latency_ms=attempt.latency_ms,
            outcome=attempt.outcome,
            attempted_at=attempt.attempted_at,
        )
        for attempt, event_type, url in rows
    ]
