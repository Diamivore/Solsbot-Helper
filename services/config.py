"""Service layer configuration."""
from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class WebSocketConfig:
    """WebSocket connection and retry configuration."""
    uri: str = "wss://api.mongoosee.com/solsstattracker/v2/gateway"
    
    # Startup retry (fail fast)
    startup_max_retries: int = 3
    startup_base_delay: float = 5.0
    startup_max_delay: float = 10.0
    
    # Runtime retry (more tolerant)
    runtime_max_retries: int = 10
    runtime_base_delay: float = 5.0
    runtime_max_delay: float = 300.0
    
    # Connection health
    close_timeout: float = 10.0
    zombie_timeout: float = 60.0


@dataclass(frozen=True)
class QueueConfig:
    """Notification queue configuration."""
    max_size: int = 1000
    drop_strategy: str = "oldest"  # "oldest" or "newest"


@dataclass(frozen=True)
class NotificationConfig:
    """Notification processing configuration."""
    exceptional_rarity_threshold: int = 750_000_000
    global_icon_url: str = "https://cdn.mongoosee.com/assets/stars/Global.png"
    exceptional_message: str = "Good find!"


@dataclass(frozen=True)
class DeduplicationConfig:
    """Duplicate detection configuration."""
    window_size: int = 100  # Number of recent hashes to track


@dataclass(frozen=True)
class CacheConfig:
    """Cache TTL and size configuration."""
    permission_cache_ttl: int = 300  # 5 minutes
    permission_cache_size: int = 1000


@dataclass(frozen=True)
class ValidationConfig:
    """Input validation constraints."""
    username_max_length: int = 20
    username_min_length: int = 1
    webhook_valid_domains: tuple[str, ...] = ("discord.com", "discordapp.com")


@dataclass
class ServiceConfig:
    """Root configuration container for all services."""
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    queue: QueueConfig = field(default_factory=QueueConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    deduplication: DeduplicationConfig = field(default_factory=DeduplicationConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    
    @classmethod
    def from_environment(cls) -> "ServiceConfig":
        """Load configuration with environment variable overrides."""
        return cls(
            websocket=WebSocketConfig(
                uri=os.getenv(
                    "SOLS_API_URI", 
                    "wss://api.mongoosee.com/solsstattracker/v2/gateway"
                ),
                zombie_timeout=float(os.getenv("WS_ZOMBIE_TIMEOUT", "60")),
            ),
            queue=QueueConfig(
                max_size=int(os.getenv("QUEUE_MAX_SIZE", "1000")),
            ),
            notification=NotificationConfig(
                exceptional_rarity_threshold=int(
                    os.getenv("EXCEPTIONAL_RARITY", "750000000")
                ),
            ),
        )


# Global default configuration
default_config = ServiceConfig()
