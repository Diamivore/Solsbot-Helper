"""Guild data access."""
import logging
from typing import Optional

from models import GuildSettings, User
from .exceptions import NotFoundError


logger = logging.getLogger(__name__)


class GuildRepository:
    """
    Data access for GuildSettings entity.
    """
    
    # ============== Guild Settings Operations ==============
    
    @staticmethod
    async def get_or_create(guild_id: int, name: str) -> tuple[GuildSettings, bool]:
        """Get existing guild settings or create with defaults."""
        return await GuildSettings.get_or_create(
            guild_id=guild_id,
            defaults={"name": name}
        )
    
    @staticmethod
    async def get_by_id(guild_id: int) -> Optional[GuildSettings]:
        """Get guild settings by ID, returns None if not found."""
        return await GuildSettings.filter(guild_id=guild_id).first()
    
    @staticmethod
    async def update_webhook(guild_id: int, webhook_url: str, name: str) -> None:
        """Set or update webhook URL for a guild."""
        guild_settings, _ = await GuildSettings.get_or_create(
            guild_id=guild_id,
            defaults={"name": name}
        )
        guild_settings.post_channel_webhook = webhook_url
        await guild_settings.save(update_fields=["post_channel_webhook"])
    
    @staticmethod
    async def update_role(guild_id: int, role_id: int | None, name: str) -> None:
        """Set or update required role for a guild."""
        guild_settings, _ = await GuildSettings.get_or_create(
            guild_id=guild_id,
            defaults={"name": name}
        )
        guild_settings.can_post_role = role_id
        await guild_settings.save(update_fields=["can_post_role"])
    
    @staticmethod
    async def get_posting_status(guild_id: int, name: str) -> bool:
        """Check if guild allows posting."""
        guild_settings, _ = await GuildSettings.get_or_create(
            guild_id=guild_id,
            defaults={"name": name}
        )
        return guild_settings.allow_posting
    
    @staticmethod
    async def set_posting_status(guild_id: int, allow: bool, name: str) -> None:
        """Set guild posting status."""
        guild_settings, _ = await GuildSettings.get_or_create(
            guild_id=guild_id,
            defaults={"name": name}
        )
        guild_settings.allow_posting = allow
        await guild_settings.save(update_fields=["allow_posting"])
    
    @staticmethod
    async def get_webhook_destinations(guild_ids: list[int]) -> list[tuple]:
        """
        Get webhook destinations for multiple guilds.
        
        Returns:
            List of (webhook_url, guild_id, can_post_role) tuples
        """
        return await GuildSettings.filter(
            guild_id__in=guild_ids
        ).values_list(
            "post_channel_webhook",
            "guild_id",
            "can_post_role"
        )
    
    @staticmethod
    async def remove_guild_from_users(guild_id: int) -> int:
        """
        Remove a guild from all users' subscription lists.
        
        Returns:
            Number of users updated
        """
        users = await User.filter(guilds__contains=[guild_id])
        count = 0
        
        if users:
            for user in users:
                current_guilds = user.guilds if user.guilds else []
                if guild_id in current_guilds:
                    user.guilds = [g for g in current_guilds if g != guild_id]
                    count += 1
            
            await User.bulk_update(users, fields=["guilds"])
        
        return count
