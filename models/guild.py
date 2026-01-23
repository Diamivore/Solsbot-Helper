"""Guild domain models."""
from tortoise.models import Model
from tortoise import fields

from .base import TimestampMixin


class GuildSettings(Model, TimestampMixin):
    """Discord guild configuration."""
    guild_id = fields.BigIntField(primary_key=True, generated=False, unique=True, db_index=True)
    name = fields.CharField(max_length=100)
    can_post_role = fields.BigIntField(null=True)
    post_channel_webhook = fields.CharField(null=True, max_length=150)
    allow_posting = fields.BooleanField(default=False)
