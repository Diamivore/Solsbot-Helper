"""User data access."""
import logging
from typing import Optional
from tortoise.exceptions import DoesNotExist

from models import User, UsernameList, AuraList
from .exceptions import NotFoundError, DuplicateError


logger = logging.getLogger(__name__)


class UserRepository:
    """Data access for User, UsernameList, and AuraList entities."""
    
    # ============== User Operations ==============
    
    @staticmethod
    async def get_or_create(user_id: int) -> tuple[User, bool]:
        """Get existing user or create new one."""
        return await User.get_or_create(user_id=user_id)
    
    @staticmethod
    async def get_by_id(user_id: int) -> Optional[User]:
        """Get user by ID, returns None if not found."""
        return await User.filter(user_id=user_id).first()
    
    @staticmethod
    async def get_guilds(user_id: int) -> list[int]:
        """Get list of guild IDs user is subscribed to."""
        user, _ = await User.get_or_create(user_id=user_id)
        return user.guilds if user.guilds else []
    
    @staticmethod
    async def update_guilds(user_id: int, guilds: list[int]) -> None:
        """Update user's guild subscriptions."""
        user, _ = await User.get_or_create(user_id=user_id)
        user.guilds = guilds
        await user.save(update_fields=["guilds"])
    
    # ============== Username Operations ==============
    
    @staticmethod
    async def get_username(name: str) -> Optional[UsernameList]:
        """Get username record by name."""
        return await UsernameList.filter(name=name).first()
    
    @staticmethod
    async def get_username_with_user(name: str) -> UsernameList:
        """
        Get username with prefetched user relation.
        
        Raises:
            NotFoundError: If username doesn't exist
        """
        try:
            return await UsernameList.get(name=name).prefetch_related("user_id")
        except DoesNotExist:
            raise NotFoundError("Username", name)
    
    @staticmethod
    async def create_username(user_id: int, name: str) -> UsernameList:
        """
        Create a new username for a user.
        
        Raises:
            DuplicateError: If username already exists
        """
        # Check global uniqueness
        existing = await UsernameList.filter(name=name).first()
        if existing:
            raise DuplicateError("Username", name)
        
        user, _ = await User.get_or_create(user_id=user_id)
        return await UsernameList.create(name=name, user_id=user)
    
    @staticmethod
    async def delete_username(user_id: int, name: str) -> None:
        """
        Delete a username owned by a user.
        
        Raises:
            NotFoundError: If user or username doesn't exist
        """
        user = await User.filter(user_id=user_id).first()
        if not user:
            raise NotFoundError("User", user_id)
        
        username_record = await UsernameList.filter(
            name=name, 
            user_id=user
        ).first()
        
        if not username_record:
            raise NotFoundError("Username", name)
        
        await username_record.delete()
    
    @staticmethod
    async def get_usernames_for_user(user_id: int) -> list[str]:
        """Get all usernames registered to a user."""
        user, created = await User.get_or_create(user_id=user_id)
        if created:
            return []
        
        return await user.usernames.all().values_list("name", flat=True)
    
    @staticmethod
    async def get_all_active_usernames() -> list[str]:
        """
        Get all usernames that have at least one guild subscription.
        
        Used for initializing the in-memory username cache.
        """
        usernames = await UsernameList.all().prefetch_related("user_id")
        active = []
        
        for username in usernames:
            if username.user_id.guilds:
                active.append(username.name)
        
        return active
    
    @staticmethod
    async def username_exists(name: str) -> bool:
        """Check if a username is already registered globally."""
        return await UsernameList.filter(name=name).exists()
    
    @staticmethod
    async def user_owns_username(user_id: int, name: str) -> bool:
        """Check if a specific user owns a username."""
        user = await User.filter(user_id=user_id).first()
        if not user:
            return False
        return await UsernameList.filter(name=name, user_id=user).exists()
