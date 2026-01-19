from tortoise.models import Model
from tortoise import fields, run_async
from tortoise.signals import post_save
from typing import Type

# TODO: set up subscriptions so individual roblox accounts can be posted to individual guilds

# Inheritence model
class TimestampMixin():
    created_at = fields.DatetimeField(null=True, auto_now_add=True)
    modified_at = fields.DatetimeField(null=True, auto_now=True)

user_model = "models.User"

# Tables
class User(Model, TimestampMixin):
    user_id = fields.BigIntField(primary_key=True, generated=False, unique=True, index=True)
    post_all_keys = fields.BooleanField(default=True)
    auras: fields.ReverseRelation["AuraList"]
    usernames: fields.ReverseRelation["UsernameList"]
    guilds = fields.JSONField(default=list, null=True)

class GuildSettings(Model, TimestampMixin):
    guild_id = fields.BigIntField(primary_key=True, generated=False, unique=True, index=True)
    name = fields.CharField(max_length=100)
    can_post_role = fields.BigIntField(null=True)
    post_channel_webhook = fields.CharField(null=True, max_length=150)
    allow_posting = fields.BooleanField(default=False)

class AuraList(Model, TimestampMixin):
    user_id = fields.OneToOneField(
        f"{user_model}", 
        related_name="auras", 
        index=True, 
        primary_key=True,
        generated=False
        )
    
    auras = fields.JSONField(default=list)

class UsernameList(Model, TimestampMixin):
    id = fields.IntField(primary_key=True, unique=True, index=True, generated=True)
    name = fields.CharField(generated=False, unique=True, index=True, max_length=20)
    user_id = fields.ForeignKeyField(
        f"{user_model}",
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
    if created:
        await AuraList.create(user_id=instance)
