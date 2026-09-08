class PulseDeskError(Exception):
    """Base class for all domain errors mapped to HTTP responses by the central handler."""


class NotFoundError(PulseDeskError):
    def __init__(self, resource: str, resource_id: str):
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} {resource_id} not found")


class UnauthorizedActionError(PulseDeskError):
    def __init__(self, message: str = "You are not allowed to perform this action"):
        super().__init__(message)


class DuplicateResourceError(PulseDeskError):
    def __init__(self, message: str):
        super().__init__(message)


class IdempotencyConflictError(PulseDeskError):
    def __init__(self, message: str = "Idempotency-Key reused with a different payload"):
        super().__init__(message)


class InvalidCredentialsError(PulseDeskError):
    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message)


class InvalidStateTransitionError(PulseDeskError):
    def __init__(self, message: str):
        super().__init__(message)
