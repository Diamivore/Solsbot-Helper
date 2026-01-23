"""
Cache Implementations

Concrete implementations of cache protocols.
"""
import hashlib
from collections import deque
from typing import Callable, Awaitable

from .protocols import UsernameCache, DeduplicationCache
from .config import DeduplicationConfig


class InMemoryUsernameCache:
    """Thread-safe in-memory username cache."""
    
    def __init__(self, db_loader: Callable[[], Awaitable[list[str]]] | None = None):
        self._usernames: set[str] = set()
        self._db_loader = db_loader
    
    def contains(self, username: str) -> bool:
        return username.lower() in self._usernames
    
    def add(self, username: str) -> None:
        self._usernames.add(username.lower())
    
    def remove(self, username: str) -> None:
        self._usernames.discard(username.lower())
    
    def as_set(self) -> frozenset[str]:
        return frozenset(self._usernames)
    
    async def refresh_from_db(self) -> None:
        if self._db_loader:
            usernames = await self._db_loader()
            self._usernames = set(u.lower() for u in usernames)
    
    def __len__(self) -> int:
        return len(self._usernames)


class CircularDeduplicationCache:
    """Circular buffer-based deduplication cache."""
    
    def __init__(self, config: DeduplicationConfig | None = None):
        self._config = config or DeduplicationConfig()
        self._hashes: deque[str] = deque(maxlen=self._config.window_size)
        self._hash_set: set[str] = set()
    
    def is_duplicate(self, notification_hash: str) -> bool:
        return notification_hash in self._hash_set
    
    def record(self, notification_hash: str) -> None:
        if len(self._hashes) >= self._config.window_size:
            oldest = self._hashes[0]
            self._hash_set.discard(oldest)
        
        self._hashes.append(notification_hash)
        self._hash_set.add(notification_hash)
    
    def clear(self) -> None:
        self._hashes.clear()
        self._hash_set.clear()
    
    @staticmethod
    def generate_hash(name: str, aura: str, timestamp: str) -> str:
        """Generate notification hash from key fields."""
        key = f"{name}:{aura}:{timestamp}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def __len__(self) -> int:
        return len(self._hashes)
