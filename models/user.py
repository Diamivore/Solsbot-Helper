"""User domain models."""
from tortoise.models import Model
from tortoise import fields
from tortoise.signals import post_save
from typing import TYPE_CHECKING

from .base import TimestampMixin

if TYPE_CHECKING:
    from typing import Type


class User(Model, TimestampMixin):
    """Discord user registered with the bot."""
    user_id = fields.BigIntField(primary_key=True, generated=False, unique=True, db_index=True)
    post_all_keys = fields.BooleanField(default=True)
    auras: fields.ReverseRelation["AuraList"]
    usernames: fields.ReverseRelation["UsernameList"]
    guilds = fields.JSONField(default=list, null=True)


class AuraList(Model, TimestampMixin):
    """
    Stores aura history for a user.
    
    One-to-one relationship with User.
    """
    user_id = fields.OneToOneField(
        "models.User", 
        related_name="auras", 
        db_index=True, 
        primary_key=True,
        generated=False
    )
    auras = fields.JSONField(default=list)


class UsernameList(Model, TimestampMixin):
    """
    Maps Roblox usernames to Discord users.
    
    Each username can only be registered to one user.
    """
    id = fields.IntField(primary_key=True, unique=True, db_index=True, generated=True)
    name = fields.CharField(generated=False, unique=True, db_index=True, max_length=20)
    user_id = fields.ForeignKeyField(
        "models.User",
        related_name="usernames",
        generated=False
    )


@post_save(User)
async def create_aura_list(
    sender: "Type[User]",
    instance: User,
    created: bool,
    using_db,
    update_fields
):
    """Automatically create an AuraList when a new User is created."""
    if created:
        await AuraList.create(user_id=instance)
