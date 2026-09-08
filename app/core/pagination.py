import base64
import uuid
from datetime import datetime


class InvalidCursorError(Exception):
    pass


def encode_cursor(created_at: datetime, ticket_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{ticket_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        created_at_raw, id_raw = raw.split("|", 1)
        return datetime.fromisoformat(created_at_raw), uuid.UUID(id_raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidCursorError("Malformed pagination cursor") from exc
