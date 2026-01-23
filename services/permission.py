"""Permission checking with caching."""
import logging
from typing import Protocol
from cachetools import TTLCache

from .config import CacheConfig
from .protocols import DiscordGateway


logger = logging.getLogger(__name__)


class PermissionService:
    """Checks user permissions with caching."""
    
    def __init__(
        self, 
        discord_gateway: DiscordGateway,
        config: CacheConfig | None = None,
        enable_cache: bool = True
    ):
        self._gateway = discord_gateway
        self._config = config or CacheConfig()
        self._cache_enabled = enable_cache
        
        if enable_cache:
            self._cache: TTLCache = TTLCache(
                maxsize=self._config.permission_cache_size,
                ttl=self._config.permission_cache_ttl
            )
        else:
            self._cache = None
    
    async def check_user_permission(
        self,
        guild_id: int,
        user_id: int,
        required_role_id: int | None
    ) -> bool:
        """
        Check if user has required role in guild.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID  
            required_role_id: Required role ID, or None/0 if no requirement
            
        Returns:
            True if user has permission, False otherwise
        """
        # No role requirement = always allowed
        if not required_role_id:
            return True
        
        # Check cache first
        cache_key = (guild_id, user_id, required_role_id)
        if self._cache is not None and cache_key in self._cache:
            logger.debug(f"Permission cache hit: {cache_key}")
            return self._cache[cache_key]
        
        # Fetch from Discord API
        result = await self._check_discord_permission(guild_id, user_id, required_role_id)
        
        # Cache result
        if self._cache is not None:
            self._cache[cache_key] = result
        
        return result
    
    async def _check_discord_permission(
        self,
        guild_id: int,
        user_id: int,
        required_role_id: int
    ) -> bool:
        """Perform actual Discord API permission check."""
        guild = self._gateway.get_guild(guild_id)
        if not guild:
            logger.debug(f"Guild {guild_id} not found in cache")
            return False
        
        try:
            member = await self._gateway.fetch_member(guild_id, user_id)
        except Exception as e:
            logger.debug(f"Failed to fetch member {user_id} in guild {guild_id}: {e}")
            return False
        
        if member is None:
            return False
        
        # Check if member has required role
        required_id = int(required_role_id)
        return any(role.id == required_id for role in member.roles)
    
    def invalidate_cache(self, guild_id: int | None = None, user_id: int | None = None):
        """
        Invalidate cached permissions.
        
        Args:
            guild_id: If provided, only invalidate entries for this guild
            user_id: If provided, only invalidate entries for this user
        """
        if self._cache is None:
            return
        
        if guild_id is None and user_id is None:
            self._cache.clear()
            return
        
        # Selective invalidation
        keys_to_remove = []
        for key in self._cache:
            g_id, u_id, _ = key
            if guild_id is not None and g_id != guild_id:
                continue
            if user_id is not None and u_id != user_id:
                continue
            keys_to_remove.append(key)
        
        for key in keys_to_remove:
            self._cache.pop(key, None)
    
    @property
    def cache_stats(self) -> dict:
        """Get cache statistics for monitoring."""
        if self._cache is None:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "size": len(self._cache),
            "maxsize": self._cache.maxsize,
            "ttl": self._cache.ttl,
        }
