"""Guild business logic."""
import logging
from repositories import GuildRepository
from models import GuildSettings, User

logger = logging.getLogger(__name__)


class GuildService:
    """
    Business logic for guild-related operations.
    """
    
    @staticmethod
    async def add_webhook(guild_id: int, webhook_url: str, guild_name: str) -> None:
        """Set webhook URL for a guild."""
        await GuildRepository.update_webhook(guild_id, webhook_url, guild_name)
    
    @staticmethod
    async def add_role(guild_id: int, role_id: int, guild_name: str) -> None:
        """Set or remove required role for a guild."""
        actual_role_id = None if role_id == 0 else role_id
        await GuildRepository.update_role(guild_id, actual_role_id, guild_name)
    
    @staticmethod
    async def get_posting_status(guild_id: int, guild_name: str) -> bool:
        """Check if guild allows posting."""
        return await GuildRepository.get_posting_status(guild_id, guild_name)
    
    @staticmethod
    async def toggle_posting(guild_id: int, guild_name: str) -> bool:
        """
        Toggle guild posting status.
        
        If disabling, removes all user subscriptions to this guild.
        
        Returns:
            New posting status (True = enabled, False = disabled)
        """
        current_status = await GuildRepository.get_posting_status(guild_id, guild_name)
        
        if current_status:
            # Disabling - remove all subscriptions
            await GuildRepository.set_posting_status(guild_id, False, guild_name)
            await GuildRepository.remove_guild_from_users(guild_id)
            return False
        else:
            # Enabling
            await GuildRepository.set_posting_status(guild_id, True, guild_name)
            return True
    
    @staticmethod
    async def get_user_destinations(username: str) -> tuple:
        """
        Get webhook destinations for a username.
        
        Returns:
            Tuple of (webhooks list, user_id)
            
        Raises:
            repositories.exceptions.NotFoundError: If username not found
        """
        from repositories import UserRepository
        
        username_obj = await UserRepository.get_username_with_user(username)
        user = username_obj.user_id
        guild_ids = user.guilds if user.guilds else []
        
        if not guild_ids:
            return [], user.user_id
        
        webhooks = await GuildRepository.get_webhook_destinations(guild_ids)
        return webhooks, user.user_id
