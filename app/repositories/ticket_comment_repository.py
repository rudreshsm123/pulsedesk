import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import TicketComment


class TicketCommentRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self, ticket_id: uuid.UUID, author_id: uuid.UUID, body: str, is_internal: bool
    ) -> TicketComment:
        comment = TicketComment(
            ticket_id=ticket_id, author_id=author_id, body=body, is_internal=is_internal
        )
        self._session.add(comment)
        await self._session.flush()
        await self._session.refresh(comment)
        return comment

    async def list_by_ticket(self, ticket_id: uuid.UUID) -> list[TicketComment]:
        stmt = (
            select(TicketComment)
            .where(TicketComment.ticket_id == ticket_id)
            .order_by(TicketComment.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
