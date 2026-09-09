import uuid

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.db import get_db
from app.core.enums import TicketPriority, TicketStatus, UserRole
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit
from app.models.user import User
from app.repositories.ai_suggestion_repository import AISuggestionRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository
from app.schemas.ai_suggestion import AISuggestionOut
from app.schemas.ticket import TicketAssignRequest, TicketCreate, TicketListResponse, TicketOut
from app.services.ticket_service import TicketService
from app.workers.classify import classify_ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])
logger = get_logger("pulsedesk.api.tickets")

require_customer = require_role(UserRole.CUSTOMER)
require_agent_or_admin = require_role(UserRole.AGENT, UserRole.ADMIN)


def get_ticket_service(session: AsyncSession = Depends(get_db)) -> TicketService:
    return TicketService(TicketRepository(session), UserRepository(session))


@router.post(
    "",
    response_model=TicketOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("ticket-create", capacity=30, per_minute=30))],
)
async def create_ticket(
    body: TicketCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: User = Depends(require_customer),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> TicketOut:
    ticket = await ticket_service.create_ticket(
        customer_id=user.id,
        subject=body.subject,
        body=body.body,
        idempotency_key=idempotency_key,
    )
    _enqueue_classification(str(ticket.id))
    return TicketOut.model_validate(ticket)


def _enqueue_classification(ticket_id: str) -> None:
    # A Celery/Redis outage must not fail ticket creation -- the ticket is durably
    # persisted as PENDING regardless, and the SLA sweep + a manual re-enqueue can
    # recover it later. Enqueue failures degrade to "classification is delayed",
    # never to "the customer's ticket submission failed".
    try:
        classify_ticket.delay(ticket_id)
    except Exception:
        logger.exception(f"Failed to enqueue classification for ticket {ticket_id}")


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


@router.get("/{ticket_id}/ai-suggestion", response_model=None)
async def get_ai_suggestion(
    ticket_id: uuid.UUID,
    user: User = Depends(require_agent_or_admin),
    ticket_service: TicketService = Depends(get_ticket_service),
    session: AsyncSession = Depends(get_db),
) -> AISuggestionOut | JSONResponse:
    await ticket_service.get_ticket_for_user(ticket_id, user)  # 404 if ticket doesn't exist

    suggestion = await AISuggestionRepository(session).get_by_ticket_id(ticket_id)
    if suggestion is None:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"detail": "Suggestion is still being generated"},
        )

    return AISuggestionOut.model_validate(suggestion)


@router.patch("/{ticket_id}/assign", response_model=TicketOut)
async def assign_ticket(
    ticket_id: uuid.UUID,
    body: TicketAssignRequest,
    user: User = Depends(require_agent_or_admin),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> TicketOut:
    ticket = await ticket_service.assign_ticket(ticket_id, body.agent_id, user)
    return TicketOut.model_validate(ticket)
