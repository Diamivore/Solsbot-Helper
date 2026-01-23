"""Repository-level exceptions."""


class RepositoryError(Exception):
    """Base exception for repository operations."""
    pass


class NotFoundError(RepositoryError):
    """Raised when a requested entity does not exist."""
    def __init__(self, entity_type: str, identifier: str | int):
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} '{identifier}' not found")


class DuplicateError(RepositoryError):
    """Raised when attempting to create a duplicate entity."""
    def __init__(self, entity_type: str, identifier: str | int):
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} '{identifier}' already exists")
