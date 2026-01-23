"""
Base model mixins and utilities.
"""
from tortoise import fields


class TimestampMixin:
    """Mixin providing created_at and modified_at timestamps."""
    created_at = fields.DatetimeField(null=True, auto_now_add=True)
    modified_at = fields.DatetimeField(null=True, auto_now=True)
