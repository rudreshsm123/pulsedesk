from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    DuplicateResourceError,
    IdempotencyConflictError,
    InvalidCredentialsError,
    InvalidStateTransitionError,
    NotFoundError,
    UnauthorizedActionError,
)
from app.core.pagination import InvalidCursorError

_STATUS_MAP = {
    NotFoundError: 404,
    UnauthorizedActionError: 403,
    DuplicateResourceError: 409,
    IdempotencyConflictError: 409,
    InvalidCredentialsError: 401,
    InvalidStateTransitionError: 409,
    InvalidCursorError: 400,
}


def register_exception_handlers(app: FastAPI) -> None:
    for exc_type, status_code in _STATUS_MAP.items():

        def make_handler(code: int):
            async def handler(request: Request, exc: Exception) -> JSONResponse:
                return JSONResponse(status_code=code, content={"detail": str(exc)})

            return handler

        app.add_exception_handler(exc_type, make_handler(status_code))
