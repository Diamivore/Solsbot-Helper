"""Service layer exceptions."""


class ServiceError(Exception):
    """Base exception for all service layer errors."""
    
    def __init__(self, message: str, code: str | None = None):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationError(ServiceError):
    """Input validation failed."""
    
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation error on '{field}': {message}", code="VALIDATION_ERROR")


class NotFoundError(ServiceError):
    """Requested resource does not exist."""
    
    def __init__(self, resource: str, identifier: str | int):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} '{identifier}' not found", code="NOT_FOUND")


class DuplicateError(ServiceError):
    """Resource already exists."""
    
    def __init__(self, resource: str, identifier: str | int):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} '{identifier}' already exists", code="DUPLICATE")


class PermissionDeniedError(ServiceError):
    """Operation not permitted for current user/context."""
    
    def __init__(self, action: str, reason: str | None = None):
        self.action = action
        self.reason = reason
        msg = f"Permission denied for '{action}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, code="PERMISSION_DENIED")


class GuildNotConfiguredError(ServiceError):
    """Guild is missing required configuration."""
    
    def __init__(self, guild_id: int, missing: str):
        self.guild_id = guild_id
        self.missing = missing
        super().__init__(
            f"Guild {guild_id} is not configured: {missing}",
            code="GUILD_NOT_CONFIGURED"
        )


class WebhookError(ServiceError):
    """Webhook-related failure."""
    
    def __init__(self, message: str, url: str | None = None):
        self.url = "[REDACTED]" if url else None
        super().__init__(message, code="WEBHOOK_ERROR")


class RateLimitError(ServiceError):
    """Rate limit exceeded."""
    
    def __init__(self, resource: str, retry_after: float | None = None):
        self.resource = resource
        self.retry_after = retry_after
        msg = f"Rate limit exceeded for {resource}"
        if retry_after:
            msg += f", retry after {retry_after}s"
        super().__init__(msg, code="RATE_LIMITED")
