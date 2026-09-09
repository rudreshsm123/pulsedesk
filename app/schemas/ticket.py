import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)


class TicketOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    assigned_agent_id: uuid.UUID | None
    subject: str
    body: str
    status: TicketStatus
    category: str | None
    priority: TicketPriority | None
    ai_confidence: float | None
    sla_deadline: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    items: list[TicketOut]
    next_cursor: str | None


class TicketAssignRequest(BaseModel):
    agent_id: uuid.UUID


class TicketAnalyticsOut(BaseModel):
    total_tickets: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    by_category: dict[str, int]
