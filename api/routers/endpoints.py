from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import DeliveryAttempt, Endpoint, Event
from api.schemas import (
    DeliveryWithContext,
    EndpointCreate,
    EndpointResponse,
    PaginatedDeliveries,
)

router = APIRouter(prefix="/endpoints", tags=["endpoints"])


@router.post("", response_model=EndpointResponse, status_code=201)
async def register_endpoint(
    body: EndpointCreate,
    db: AsyncSession = Depends(get_db),
) -> Endpoint:
    endpoint = Endpoint(
        url=body.url,
        secret=body.secret,
        event_types=body.event_types,
    )
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)
    return endpoint


@router.get("", response_model=list[EndpointResponse])
async def list_endpoints(db: AsyncSession = Depends(get_db)) -> list[Endpoint]:
    result = await db.execute(select(Endpoint).order_by(Endpoint.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{endpoint_id}", response_model=EndpointResponse)
async def get_endpoint(
    endpoint_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Endpoint:
    endpoint = await db.get(Endpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return endpoint


@router.delete("/{endpoint_id}", response_model=EndpointResponse)
async def deactivate_endpoint(
    endpoint_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Endpoint:
    endpoint = await db.get(Endpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    endpoint.active = False
    await db.commit()
    await db.refresh(endpoint)
    return endpoint


@router.get("/{endpoint_id}/deliveries", response_model=PaginatedDeliveries)
async def get_endpoint_deliveries(
    endpoint_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedDeliveries:
    endpoint = await db.get(Endpoint, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    total_result = await db.execute(
        select(func.count())
        .select_from(DeliveryAttempt)
        .where(DeliveryAttempt.endpoint_id == endpoint_id)
    )
    total = total_result.scalar_one()

    query = (
        select(DeliveryAttempt, Event.event_type, Endpoint.url)
        .join(Event, DeliveryAttempt.event_id == Event.id)
        .join(Endpoint, DeliveryAttempt.endpoint_id == Endpoint.id)
        .where(DeliveryAttempt.endpoint_id == endpoint_id)
        .order_by(DeliveryAttempt.attempted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(query)).all()

    items = [
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

    return PaginatedDeliveries(items=items, total=total, page=page, page_size=page_size)
