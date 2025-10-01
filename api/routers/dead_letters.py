from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import DeadLetter, Endpoint, Event
from api.schemas import DeadLetterResponse, PaginatedDeadLetters, RetryAllResponse
from worker.tasks import deliver_event

router = APIRouter(prefix="/dead-letters", tags=["dead-letters"])


async def _enrich_dead_letter(
    db: AsyncSession, dead_letter: DeadLetter
) -> DeadLetterResponse:
    event = await db.get(Event, dead_letter.event_id)
    endpoint = await db.get(Endpoint, dead_letter.endpoint_id)
    return DeadLetterResponse(
        id=dead_letter.id,
        event_id=dead_letter.event_id,
        endpoint_id=dead_letter.endpoint_id,
        final_attempt_at=dead_letter.final_attempt_at,
        retry_count=dead_letter.retry_count,
        last_error=dead_letter.last_error,
        created_at=dead_letter.created_at,
        event_type=event.event_type if event else None,
        endpoint_url=endpoint.url if endpoint else None,
    )


@router.get("", response_model=PaginatedDeadLetters)
async def list_dead_letters(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedDeadLetters:
    total_result = await db.execute(select(func.count()).select_from(DeadLetter))
    total = total_result.scalar_one()

    result = await db.execute(
        select(DeadLetter)
        .order_by(DeadLetter.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    dead_letters = list(result.scalars().all())
    items = [await _enrich_dead_letter(db, dl) for dl in dead_letters]

    return PaginatedDeadLetters(items=items, total=total, page=page, page_size=page_size)


@router.post("/retry-all", response_model=RetryAllResponse)
async def retry_all_dead_letters(db: AsyncSession = Depends(get_db)) -> RetryAllResponse:
    result = await db.execute(select(DeadLetter))
    dead_letters = list(result.scalars().all())

    for dead_letter in dead_letters:
        deliver_event.delay(str(dead_letter.event_id), str(dead_letter.endpoint_id), 1)
        await db.delete(dead_letter)

    await db.commit()
    return RetryAllResponse(retried_count=len(dead_letters))


@router.post("/{dead_letter_id}/retry", response_model=DeadLetterResponse)
async def retry_dead_letter(
    dead_letter_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DeadLetterResponse:
    dead_letter = await db.get(DeadLetter, dead_letter_id)
    if not dead_letter:
        raise HTTPException(status_code=404, detail="Dead letter not found")

    event_id = str(dead_letter.event_id)
    endpoint_id = str(dead_letter.endpoint_id)
    response = await _enrich_dead_letter(db, dead_letter)

    await db.delete(dead_letter)
    await db.commit()

    deliver_event.delay(event_id, endpoint_id, 1)
    return response
