"""Service layer protocols (interfaces)."""
from typing import Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass
class ParsedEmbed:
    """Parsed notification embed data."""
    name: str
    full_name: str
    icon_url: str
    url: str
    description: str
    aura: str
    rarity: str | None  # None if rarity is in description, populated if separate field
    rolls: str
    luck: str
    time: str
    timestamp: str
    color: int
    is_rare_format: bool = False  # True if using rare aura format (separate rarity field)


@dataclass
class GuildSettings:
    """Guild configuration data."""
    guild_id: int
    guild_name: str
    webhook_url: str | None
    allow_posting: bool
    required_role_id: int | None


@dataclass
class WebhookTarget:
    """Target for webhook delivery."""
    url: str
    guild_id: int
    user_id: int


@dataclass
class DeliveryResult:
    """Result of a webhook delivery attempt."""
    target: WebhookTarget
    success: bool
    error: str | None = None


@runtime_checkable
class UsernameCache(Protocol):
    """Interface for username cache operations."""
    
    def contains(self, username: str) -> bool:
        """Check if username is in cache."""
        ...
    
    def add(self, username: str) -> None:
        """Add username to cache."""
        ...
    
    def remove(self, username: str) -> None:
        """Remove username from cache."""
        ...
    
    def as_set(self) -> frozenset[str]:
        """Get all usernames as frozen set for fast lookup."""
        ...
    
    async def refresh_from_db(self) -> None:
        """Reload cache from database."""
        ...


@runtime_checkable
class DeduplicationCache(Protocol):
    """Interface for notification deduplication."""
    
    def is_duplicate(self, notification_hash: str) -> bool:
        """Check if notification was recently processed."""
        ...
    
    def record(self, notification_hash: str) -> None:
        """Record notification as processed."""
        ...
    
    def clear(self) -> None:
        """Clear all recorded hashes."""
        ...


@runtime_checkable
class NotificationQueue(Protocol):
    """Interface for notification queue."""
    
    async def enqueue(self, payload: dict) -> None:
        """Add notification to queue."""
        ...
    
    async def dequeue(self) -> dict:
        """Get next notification from queue (blocking)."""
        ...
    
    def size(self) -> int:
        """Current queue size."""
        ...
    
    def is_full(self) -> bool:
        """Check if queue is at capacity."""
        ...


@runtime_checkable
class DiscordGateway(Protocol):
    """Interface for Discord API operations."""
    
    def get_guild(self, guild_id: int):
        """Get guild from cache."""
        ...
    
    def get_user(self, user_id: int):
        """Get user from cache."""
        ...
    
    async def fetch_member(self, guild_id: int, user_id: int):
        """Fetch member from Discord API."""
        ...
