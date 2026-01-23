"""User business logic."""
import logging
from repositories import UserRepository, GuildRepository
from repositories.exceptions import NotFoundError, DuplicateError

logger = logging.getLogger(__name__)


# Business exceptions for user operations
class GuildNotAllowedError(Exception):
    """Guild does not allow posting."""
    pass


class GuildWebhookError(Exception):
    """Guild has no webhook configured."""
    pass


class ItemNotFoundError(Exception):
    """Requested item does not exist."""
    pass


class ItemExistsError(Exception):
    """Item already exists."""
    pass


class UserService:
    """User operations and business rules."""
    
    # ============== Username Operations ==============
    
    @staticmethod
    async def add_username(user_id: int, username: str) -> None:
        """
        Add a username to a user.
        
        Raises:
            PermissionError: If username is already registered globally
            ItemExistsError: If user already has this username
        """
        try:
            await UserRepository.create_username(user_id, username)
        except DuplicateError:
            # Check if it's global duplicate or user's own duplicate
            if await UserRepository.user_owns_username(user_id, username):
                raise ItemExistsError("You already have this username")
            raise PermissionError("Username already registered by another user")
    
    @staticmethod
    async def remove_username(user_id: int, username: str) -> None:
        """
        Remove a username from a user.
        
        Raises:
            ItemNotFoundError: If username doesn't exist or user doesn't own it
        """
        try:
            await UserRepository.delete_username(user_id, username)
        except NotFoundError:
            raise ItemNotFoundError("Username not found")
    
    @staticmethod
    async def view_usernames(user_id: int) -> list[str]:
        """Get all usernames for a user."""
        return await UserRepository.get_usernames_for_user(user_id)
    
    # ============== Guild Subscription Operations ==============
    
    @staticmethod
    async def add_guild_subscription(user_id: int, guild_id: int, guild_name: str) -> None:
        """
        Subscribe a user to a guild.
        
        Raises:
            GuildNotAllowedError: If guild doesn't allow posting
            GuildWebhookError: If guild has no webhook
            ItemExistsError: If already subscribed
        """
        from models import GuildSettings
        
        # Get or create guild settings
        guild_settings, _ = await GuildSettings.get_or_create(
            guild_id=guild_id,
            defaults={"name": guild_name}
        )
        
        # Business rules
        if not guild_settings.allow_posting:
            raise GuildNotAllowedError("Guild does not allow posting")
        if not guild_settings.post_channel_webhook:
            raise GuildWebhookError("Guild has no webhook configured")
        
        # Check existing subscription
        current_guilds = await UserRepository.get_guilds(user_id)
        if guild_id in current_guilds:
            raise ItemExistsError("Already subscribed to this guild")
        
        # Add subscription
        current_guilds.append(guild_id)
        await UserRepository.update_guilds(user_id, current_guilds)
    
    @staticmethod
    async def remove_guild_subscription(user_id: int, guild_id: int) -> None:
        """
        Unsubscribe a user from a guild.
        
        Raises:
            ItemNotFoundError: If not subscribed
        """
        current_guilds = await UserRepository.get_guilds(user_id)
        
        if guild_id not in current_guilds:
            raise ItemNotFoundError("Not subscribed to this guild")
        
        current_guilds.remove(guild_id)
        await UserRepository.update_guilds(user_id, current_guilds)
    
    @staticmethod
    async def view_user_guilds(user_id: int) -> list[int]:
        """
        Get all guilds a user is subscribed to.
        
        Raises:
            ItemNotFoundError: If no subscriptions
        """
        guilds = await UserRepository.get_guilds(user_id)
        if not guilds:
            raise ItemNotFoundError("No guild subscriptions")
        return guilds
