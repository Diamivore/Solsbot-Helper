"""Notification processing and delivery."""
import logging
from dataclasses import dataclass
from typing import Any

from discord_webhook import AsyncDiscordWebhook, DiscordEmbed

from .protocols import (
    ParsedEmbed,
    UsernameCache,
    DeduplicationCache,
    WebhookTarget,
    DeliveryResult,
)
from .parsing import PayloadParsingService
from .permission import PermissionService
from .validation import WebhookValidationService
from .config import NotificationConfig
from .exceptions import NotFoundError


logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a raw notification payload."""
    processed_count: int
    skipped_duplicates: int
    skipped_no_destinations: int
    delivery_results: list[DeliveryResult]
    errors: list[str]


class NotificationService:
    """Processes and routes notifications to webhooks."""
    
    def __init__(
        self,
        username_cache: UsernameCache,
        dedup_cache: DeduplicationCache,
        permission_service: PermissionService,
        webhook_validator: WebhookValidationService,
        destination_loader,  # Callable to load destinations from DB
        config: NotificationConfig | None = None,
        bot_avatar_url: str | None = None,
    ):
        self._usernames = username_cache
        self._dedup = dedup_cache
        self._permissions = permission_service
        self._webhook_validator = webhook_validator
        self._load_destinations = destination_loader
        self._config = config or NotificationConfig()
        self._bot_avatar_url = bot_avatar_url
        
        self._parser = PayloadParsingService()
    
    async def process_raw_payload(
        self,
        raw_json: str,
        discord_gateway: Any = None,  # For user lookups
    ) -> ProcessingResult:
        """
        Process a raw WebSocket payload end-to-end.
        
        Args:
            raw_json: Raw JSON string from WebSocket
            discord_gateway: Discord client for user lookups
            
        Returns:
            ProcessingResult with statistics and any errors
        """
        result = ProcessingResult(
            processed_count=0,
            skipped_duplicates=0,
            skipped_no_destinations=0,
            delivery_results=[],
            errors=[],
        )
        
        # Parse payload
        parse_result = self._parser.parse_raw_message(raw_json)
        result.errors.extend(parse_result.errors)
        
        if not parse_result.embeds:
            return result
        
        # Process each embed
        for embed in parse_result.embeds:
            try:
                embed_result = await self._process_single_embed(embed, discord_gateway)
                
                if embed_result == "duplicate":
                    result.skipped_duplicates += 1
                elif embed_result == "no_match":
                    pass  # Not tracked, expected
                elif embed_result == "no_destinations":
                    result.skipped_no_destinations += 1
                elif isinstance(embed_result, list):
                    result.processed_count += 1
                    result.delivery_results.extend(embed_result)
                    
            except Exception as e:
                result.errors.append(f"Embed '{embed.name}': {e}")
                logger.exception(f"Error processing embed for {embed.name}")
        
        return result
    
    async def _process_single_embed(
        self,
        embed: ParsedEmbed,
        discord_gateway: Any,
    ) -> str | list[DeliveryResult]:
        """
        Process a single parsed embed.
        
        Returns:
            "duplicate" - Already processed
            "no_match" - Username not tracked
            "no_destinations" - No valid delivery targets
            List[DeliveryResult] - Delivery results
        """
        # Check if username is tracked
        if not self._usernames.contains(embed.name):
            return "no_match"
        
        # Check for duplicate
        notification_hash = self._generate_hash(embed)
        if self._dedup.is_duplicate(notification_hash):
            logger.debug(f"Skipping duplicate notification for '{embed.name}'")
            return "duplicate"
        
        # Record as processed (before delivery to prevent retry duplicates)
        self._dedup.record(notification_hash)
        
        # Load destinations
        try:
            destinations = await self._load_destinations(embed.name)
        except NotFoundError:
            logger.warning(f"Username '{embed.name}' no longer exists")
            return "no_destinations"
        
        if not destinations:
            logger.debug(f"No destinations for user '{embed.name}'")
            return "no_destinations"
        
        webhooks, user_id = destinations
        
        if not webhooks:
            return "no_destinations"
        
        # Filter by permissions and validate URLs
        valid_targets: list[WebhookTarget] = []
        for url, guild_id, required_role_id in webhooks:
            # Check permission
            if not await self._permissions.check_user_permission(
                guild_id, user_id, required_role_id
            ):
                continue
            
            # Validate webhook URL
            if not self._webhook_validator.is_valid(url):
                logger.warning(f"Skipping invalid webhook for guild {guild_id}")
                continue
            
            valid_targets.append(WebhookTarget(
                url=url,
                guild_id=guild_id,
                user_id=user_id,
            ))
        
        if not valid_targets:
            return "no_destinations"
        
        # Build Discord embed
        discord_embed = self._build_discord_embed(embed, user_id, discord_gateway)
        
        # Determine if exceptional find
        content = self._get_content_message(embed)
        
        # Deliver to all targets
        results = await self._deliver_batch(valid_targets, discord_embed, content)
        
        return results
    
    def _generate_hash(self, embed: ParsedEmbed) -> str:
        """Generate deduplication hash for embed."""
        import hashlib
        key = f"{embed.name}:{embed.aura}:{embed.timestamp}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def _build_discord_embed(
        self,
        embed: ParsedEmbed,
        user_id: int,
        discord_gateway: Any,
    ) -> DiscordEmbed:
        """Build Discord webhook embed from parsed data."""
        # Get user info
        user = discord_gateway.get_user(user_id) if discord_gateway else None
        
        if user:
            avatar_url = user.display_avatar.url
            user_mention = f"<@{user.id}>"
            user_name = user.name
        else:
            avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"
            user_mention = "Unknown User"
            user_name = "N/A"
        
        discord_embed = DiscordEmbed(
            description=f"\n**User**\n{user_mention}\n\n{embed.description}",
            color=embed.color,
        )
        discord_embed.set_author(
            name=embed.full_name,
            url=embed.url,
            icon_url=embed.icon_url,
        )
        discord_embed.set_timestamp(embed.timestamp)
        
        if embed.rolls != "?":
            discord_embed.add_embed_field(name="Rolls", value=embed.rolls)

        # Add Rarity field for rare format auras (separate field instead of in description)
        if embed.is_rare_format and embed.rarity:
            discord_embed.add_embed_field(name="Rarity", value=embed.rarity)

        if embed.luck != "?":
            discord_embed.add_embed_field(name="Luck", value=embed.luck)
        if embed.time != "?":
            discord_embed.add_embed_field(name="Time Discovered", value=embed.time)
        discord_embed.set_footer(
            text=f"Found by: {user_name}",
            icon_url=avatar_url,
        )
        
        return discord_embed
    
    def _get_content_message(self, embed: ParsedEmbed) -> str | None:
        """Determine if notification deserves special message."""
        rarity_value = self._parser.parse_rarity_value(embed.rarity, embed.description)
        
        is_exceptional = (
            rarity_value >= self._config.exceptional_rarity_threshold
            or embed.icon_url != self._config.global_icon_url
        )
        
        return self._config.exceptional_message if is_exceptional else None
    
    async def _deliver_batch(
        self,
        targets: list[WebhookTarget],
        embed: DiscordEmbed,
        content: str | None,
    ) -> list[DeliveryResult]:
        """Deliver notification to multiple webhooks sequentially."""
        results: list[DeliveryResult] = []
        
        for target in targets:
            try:
                webhook = AsyncDiscordWebhook(
                    url=target.url,
                    content=content,
                    username="Solsbot Helper",
                    avatar_url=self._bot_avatar_url,
                )
                webhook.add_embed(embed)
                await webhook.execute()
                
                results.append(DeliveryResult(
                    target=target,
                    success=True,
                ))
                    
            except Exception as e:
                logger.debug(f"Delivery failed for {target.guild_id}: {e}")
                results.append(DeliveryResult(
                    target=target,
                    success=False,
                    error=str(e),
                ))
        
        return results
