"""Domain error hierarchy for LUMINA."""


class DomainError(Exception):
    """Base error for all domain-level errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ValidationError(DomainError):
    """Raised when a domain invariant is violated."""


class EntityNotFoundError(DomainError):
    """Raised when a requested entity does not exist."""


class AuthorizationError(DomainError):
    """Raised when an operation is not permitted for the current tenant."""


class ConcurrencyError(DomainError):
    """Raised when a concurrent modification conflict is detected."""
