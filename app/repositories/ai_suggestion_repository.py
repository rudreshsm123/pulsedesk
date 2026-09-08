import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import AISuggestion


class AISuggestionRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_ticket_id(self, ticket_id: uuid.UUID) -> AISuggestion | None:
        result = await self._session.execute(
            select(AISuggestion).where(AISuggestion.ticket_id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, ticket_id: uuid.UUID, suggested_reply: str, source_article_ids: list[uuid.UUID]
    ) -> AISuggestion:
        suggestion = AISuggestion(
            ticket_id=ticket_id,
            suggested_reply=suggested_reply,
            source_article_ids=source_article_ids,
        )
        self._session.add(suggestion)
        await self._session.flush()
        await self._session.refresh(suggestion)
        return suggestion
