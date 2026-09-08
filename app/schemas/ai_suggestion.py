import uuid
from datetime import datetime

from pydantic import BaseModel


class AISuggestionOut(BaseModel):
    ticket_id: uuid.UUID
    suggested_reply: str
    source_article_ids: list[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}
