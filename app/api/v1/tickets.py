import uuid

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.db import get_db
from app.core.enums import TicketPriority, TicketStatus, UserRole
from app.models.user import User
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository
from app.schemas.ticket import TicketAssignRequest, TicketCreate, TicketListResponse, TicketOut
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_ticket_service(session: AsyncSession = Depends(get_db)) -> TicketService:
    return TicketService(TicketRepository(session), UserRepository(session))


@router.post("", response_model=TicketOut, status_code=status.HTTP_202_ACCEPTED)
async def create_ticket(
    body: TicketCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: User = Depends(require_role(UserRole.CUSTOMER)),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> TicketOut:
    ticket = await ticket_service.create_ticket(
        customer_id=user.id,
        subject=body.subject,
        body=body.body,
        idempotency_key=idempotency_key,
    )
    return TicketOut.model_validate(ticket)


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    priority: TicketPriority | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> TicketListResponse:
    tickets, next_cursor = await ticket_service.list_tickets(
        user=user, status=status_filter, priority=priority, cursor=cursor, limit=limit
    )
    return TicketListResponse(
        items=[TicketOut.model_validate(t) for t in tickets], next_cursor=next_cursor
    )


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(
    ticket_id: uuid.UUID,
    user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> TicketOut:
    ticket = await ticket_service.get_ticket_for_user(ticket_id, user)
    return TicketOut.model_validate(ticket)


@router.patch("/{ticket_id}/assign", response_model=TicketOut)
async def assign_ticket(
    ticket_id: uuid.UUID,
    body: TicketAssignRequest,
    user: User = Depends(require_role(UserRole.AGENT, UserRole.ADMIN)),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> TicketOut:
    ticket = await ticket_service.assign_ticket(ticket_id, body.agent_id, user)
    return TicketOut.model_validate(ticket)
