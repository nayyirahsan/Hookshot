from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EndpointCreate(BaseModel):
    url: str
    secret: str
    event_types: list[str]


class EndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    event_types: list[str]
    active: bool
    ema_recovery_ms: float
    failure_rate: float
    consecutive_failures: int
    last_success_at: datetime | None
    last_failure_at: datetime | None
    health_score: float
    created_at: datetime


class EventCreate(BaseModel):
    event_type: str
    data: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] | None = None

    def resolved_payload(self) -> dict[str, Any]:
        if self.payload is not None:
            return self.payload
        return self.data


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    idempotency_key: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class DeliveryAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    endpoint_id: UUID
    attempt_number: int
    status_code: int | None
    response_body: str | None
    latency_ms: int | None
    outcome: str
    error_message: str | None
    attempted_at: datetime


class DeliveryWithContext(BaseModel):
    id: UUID
    event_id: UUID
    endpoint_id: UUID
    event_type: str
    endpoint_url: str
    attempt_number: int
    status_code: int | None
    latency_ms: int | None
    outcome: str
    attempted_at: datetime


class DeadLetterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    endpoint_id: UUID
    final_attempt_at: datetime | None
    retry_count: int
    last_error: str | None
    created_at: datetime
    event_type: str | None = None
    endpoint_url: str | None = None


class PaginatedDeadLetters(BaseModel):
    items: list[DeadLetterResponse]
    total: int
    page: int
    page_size: int


class PaginatedDeliveries(BaseModel):
    items: list[DeliveryWithContext]
    total: int
    page: int
    page_size: int


class HealthResponse(BaseModel):
    status: str
    worker: str


class StatsResponse(BaseModel):
    events_today: int
    delivery_success_rate: float
    mean_delivery_latency_ms: float
    dead_letter_count: int


class RetryAllResponse(BaseModel):
    retried_count: int
