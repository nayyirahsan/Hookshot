from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import any_, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import DeliveryAttempt, Endpoint, Event
from api.schemas import DeliveryAttemptResponse, EventCreate, EventResponse
from worker.tasks import deliver_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventResponse)
async def ingest_event(
    body: EventCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> Event:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")

    existing = await db.execute(
        select(Event).where(Event.idempotency_key == idempotency_key)
    )
    existing_event = existing.scalar_one_or_none()
    if existing_event:
        response.status_code = 200
        return existing_event

    event = Event(
        idempotency_key=idempotency_key,
        event_type=body.event_type,
        payload=body.resolved_payload(),
    )
    db.add(event)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        dup = await db.execute(
            select(Event).where(Event.idempotency_key == idempotency_key)
        )
        existing_event = dup.scalar_one()
        response.status_code = 200
        return existing_event

    endpoints_result = await db.execute(
        select(Endpoint).where(
            Endpoint.active.is_(True),
            literal(body.event_type) == any_(Endpoint.event_types),
        )
    )
    endpoints = list(endpoints_result.scalars().all())

    await db.commit()
    await db.refresh(event)

    for endpoint in endpoints:
        deliver_event.delay(str(event.id), str(endpoint.id), 1)

    response.status_code = 202
    return event


@router.get("/{event_id}/deliveries", response_model=list[DeliveryAttemptResponse])
async def get_event_deliveries(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[DeliveryAttempt]:
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    result = await db.execute(
        select(DeliveryAttempt)
        .where(DeliveryAttempt.event_id == event_id)
        .order_by(DeliveryAttempt.attempt_number.asc())
    )
    return list(result.scalars().all())
