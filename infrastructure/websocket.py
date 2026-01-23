"""WebSocket connection and queue management."""
import websockets
import asyncio
import logging
import sys

from discord_webhook import AsyncDiscordWebhook

from services import (
    ServiceConfig,
    NotificationService,
    PermissionService,
    WebhookValidationService,
    InMemoryUsernameCache,
    CircularDeduplicationCache,
    GuildService,
)
from repositories import UserRepository


logger = logging.getLogger(__name__)


class WORKERNOTDEFINED(Exception):
    """Raised when websocket worker is not initialized."""
    pass


class WORKERRUNNING(Exception):
    """Raised when websocket worker is already running."""
    pass


class DiscordBotGatewayAdapter:
    """Adapts disnake Bot to DiscordGateway protocol."""
    
    def __init__(self, bot):
        self._bot = bot
    
    def get_guild(self, guild_id: int):
        """Get guild from bot cache."""
        return self._bot.get_guild(guild_id)
    
    def get_user(self, user_id: int):
        """Get user from bot cache."""
        return self._bot.get_user(user_id)
    
    async def fetch_member(self, guild_id: int, user_id: int):
        """Fetch member from Discord API."""
        guild = self._bot.get_guild(guild_id)
        if not guild:
            return None
        return await guild.fetch_member(user_id)


class WebSocketClient:
    """
    WebSocket client for receiving real-time notifications.
    
    This is a thin infrastructure layer that:
    - Manages WebSocket connection lifecycle
    - Handles reconnection with backoff
    - Receives messages and enqueues for processing
    - Delegates all processing to NotificationService
    
    Architecture:
        WebSocket → Queue → NotificationService → Webhooks
        
    The WebSocketClient is intentionally thin - all business logic
    (parsing, filtering, permission checks, webhook delivery) is
    delegated to the services layer for testability and separation
    of concerns.
    """
    
    def __init__(self, bot):
        self._bot = bot
        self._config = ServiceConfig.from_environment()
        
        # Queue for message processing
        self.queue = asyncio.Queue(maxsize=self._config.queue.max_size)
        
        # Connection state
        self._has_connected = False
        
        # Service layer components (initialized lazily in _init_services)
        self._notification_service: NotificationService | None = None
        self._username_cache: InMemoryUsernameCache | None = None
        self._gateway_adapter: DiscordBotGatewayAdapter | None = None
    
    async def _init_services(self) -> None:
        """
        Initialize service layer components.
        
        Called once before processing starts. Uses dependency injection
        to wire up the service graph:
        
        NotificationService
        ├── InMemoryUsernameCache (username filtering)
        ├── CircularDeduplicationCache (duplicate detection)
        ├── PermissionService (role checks)
        │   └── DiscordBotGatewayAdapter (Discord API)
        ├── WebhookValidationService (URL validation)
        └── GuildService.get_user_destinations (destination loading)
        """
        if self._notification_service is not None:
            return  # Already initialized
        
        # Create gateway adapter for Discord API access
        self._gateway_adapter = DiscordBotGatewayAdapter(self._bot)
        
        # Create username cache with DB loader
        self._username_cache = InMemoryUsernameCache(
            db_loader=UserRepository.get_all_active_usernames
        )
        
        # Load initial usernames
        await self._username_cache.refresh_from_db()
        logger.info(f"Loaded {len(self._username_cache)} usernames into cache")
        
        # Create deduplication cache
        dedup_cache = CircularDeduplicationCache(self._config.deduplication)
        
        # Create permission service with caching
        permission_service = PermissionService(
            discord_gateway=self._gateway_adapter,
            config=self._config.cache,
            enable_cache=True,
        )
        
        # Create webhook validator
        webhook_validator = WebhookValidationService(self._config.validation)
        
        # Create notification service (main orchestrator)
        self._notification_service = NotificationService(
            username_cache=self._username_cache,
            dedup_cache=dedup_cache,
            permission_service=permission_service,
            webhook_validator=webhook_validator,
            destination_loader=GuildService.get_user_destinations,
            config=self._config.notification,
            bot_avatar_url=None,  # Set dynamically per request
        )
        
        logger.info("Service layer initialized")
    
    # ─────────────────────────────────────────────────────────────────
    # Public Cache Interface (for cog integration)
    # ─────────────────────────────────────────────────────────────────
    
    async def refresh_username_cache(self) -> None:
        """Refresh username cache from database."""
        if self._username_cache:
            await self._username_cache.refresh_from_db()
            logger.debug(f"Username cache refreshed: {len(self._username_cache)} usernames")
    
    def add_username(self, username: str) -> None:
        """Add username to cache (called when user registers)."""
        if self._username_cache:
            self._username_cache.add(username)
            logger.debug(f"Added '{username}' to cache")
    
    def remove_username(self, username: str) -> None:
        """Remove username from cache (called when user unregisters)."""
        if self._username_cache:
            self._username_cache.remove(username)
            logger.debug(f"Removed '{username}' from cache")
    
    def get_username_count(self) -> int:
        """Get current username cache size."""
        return len(self._username_cache) if self._username_cache else 0
    
    # ─────────────────────────────────────────────────────────────────
    # WebSocket Connection Management
    # ─────────────────────────────────────────────────────────────────
    
    async def websocket_worker(self, api_key: str, ready_event: asyncio.Event) -> None:
        """
        Main WebSocket connection loop.
        
        Handles:
        - Initial connection with limited retries (fail-fast)
        - Runtime reconnection with exponential backoff
        - Zombie connection detection
        - Message enqueueing with backpressure handling
        
        Args:
            api_key: Third-party API authentication token
            ready_event: Event to signal when first message received
        """
        retry_count = 0
        ws_config = self._config.websocket
        
        while True:
            # Select retry config based on connection state
            is_startup = not self._has_connected
            max_retries = ws_config.startup_max_retries if is_startup else ws_config.runtime_max_retries
            base_delay = ws_config.startup_base_delay if is_startup else ws_config.runtime_base_delay
            max_delay = ws_config.startup_max_delay if is_startup else ws_config.runtime_max_delay
            
            if retry_count >= max_retries:
                mode = "startup" if is_startup else "runtime"
                logger.critical(
                    f"WebSocket worker failed after {retry_count} {mode} attempts. Shutting down."
                )
                sys.exit(1)
            
            try:
                attempt_info = f" (attempt {retry_count + 1}/{max_retries})" if retry_count > 0 else ""
                logger.info(f"Connecting websocket worker...{attempt_info}")
                
                async with websockets.connect(
                    ws_config.uri,
                    additional_headers={"token": f"{api_key}"},
                    close_timeout=ws_config.close_timeout,
                ) as websocket:
                    await self._handle_connection(websocket, ready_event, ws_config.zombie_timeout)
                    
                    # If we exit handle_connection normally, zombie detected
                    retry_count += 1
                    
            except asyncio.CancelledError:
                logger.info("Websocket worker cancelled, shutting down...")
                raise
                
            except websockets.exceptions.ConnectionClosedError as e:
                if e.code == 4002:
                    logger.error("API Key is invalid")
                    sys.exit("API Key validation failed")
                elif e.code == 4003:
                    logger.error("API Key is already in use")
                    sys.exit("API Key already in use by another connection")
                else:
                    retry_count += 1
                    logger.warning(f"Connection closed with code {e.code}: {e.reason}")
                    
            except Exception as e:
                retry_count += 1
                delay = min(base_delay * (2 ** (retry_count - 1)), max_delay)
                
                mode = "startup" if is_startup else "runtime"
                if retry_count >= max_retries - 1:
                    logger.critical(f"API Error ({mode} {retry_count}/{max_retries}): {e}")
                elif retry_count >= max_retries // 2:
                    logger.warning(f"API Error ({mode} {retry_count}/{max_retries}): {e}")
                else:
                    logger.error(f"API Error: {e}")
                
                logger.info(f"Reconnecting in {delay}s...")
                await asyncio.sleep(delay)
    
    async def _handle_connection(
        self, 
        websocket, 
        ready_event: asyncio.Event,
        zombie_timeout: float,
    ) -> None:
        """
        Handle an active WebSocket connection.
        
        Receives messages until zombie timeout or disconnect.
        """
        retry_count = 0
        
        while True:
            try:
                # Wait for message with zombie detection timeout
                message = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=zombie_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"No message received for {zombie_timeout}s, reconnecting...")
                return  # Exit to trigger reconnect
            
            # Signal ready on first successful message
            if message and not self._has_connected:
                self._has_connected = True
                ready_event.set()
            
            # Log successful recovery
            if retry_count > 0:
                logger.info(f"Connection restored after {retry_count} retries")
                retry_count = 0
            
            logger.debug(
                f"Worker received: {message[:200]}..." 
                if len(message) > 200 
                else f"Worker received: {message}"
            )
            
            # Enqueue for processing with backpressure handling
            await self._enqueue_message(message)
    
    async def _enqueue_message(self, message: str) -> None:
        """Enqueue message with backpressure handling."""
        packet = {"payload": message}
        
        try:
            self.queue.put_nowait(packet)
        except asyncio.QueueFull:
            logger.warning(
                f"Queue full ({self._config.queue.max_size} items), dropping oldest message"
            )
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:
                pass
            self.queue.put_nowait(packet)
    
    # ─────────────────────────────────────────────────────────────────
    # Queue Processing (delegates to NotificationService)
    # ─────────────────────────────────────────────────────────────────
    
    async def queue_processor(self) -> None:
        """
        Process queued messages.
        
        Intentionally simple and direct to avoid blocking the event loop.
        Matches the original proven-working implementation pattern.
        """
        await self._init_services()
        
        while True:
            try:
                packet = await self.queue.get()
                
                if not packet:
                    self.queue.task_done()
                    continue
                
                raw_json = packet["payload"]
                
                try:
                    # Parse payload
                    parse_result = self._notification_service._parser.parse_raw_message(raw_json)
                    
                    if not parse_result.embeds:
                        self.queue.task_done()
                        continue
                    
                    # Process each embed
                    for embed in parse_result.embeds:
                        # Check if username is tracked
                        if not self._username_cache.contains(embed.name):
                            continue
                        
                        # Load destinations from DB - YIELDS to event loop
                        try:
                            destinations = await GuildService.get_user_destinations(embed.name)
                            webhooks, user_id = destinations
                        except Exception:
                            logger.debug(f"No destinations for {embed.name}")
                            continue
                        
                        # ALWAYS yield after DB operation
                        await asyncio.sleep(0)
                        
                        if not webhooks:
                            continue
                        
                        # Build Discord user info
                        user = self._bot.get_user(user_id)
                        if user:
                            user_mention = f"<@{user.id}>"
                            avatar_url = user.display_avatar.url
                        else:
                            user_mention = "Unknown User"
                            avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"
                        
                        # Build Discord embed
                        discord_embed = self._notification_service._build_discord_embed(embed, user_id, self._bot)
                        
                        # Determine if exceptional find
                        content = self._notification_service._get_content_message(embed)
                        
                        # Send to each webhook sequentially
                        for url, guild_id, required_role_id in webhooks:
                            try:
                                # Check permission - YIELDS to event loop
                                if not await self._notification_service._permissions.check_user_permission(
                                    guild_id, user_id, required_role_id
                                ):
                                    continue
                                
                                # YIELD after permission check
                                await asyncio.sleep(0)
                                
                                # Validate URL
                                if not self._notification_service._webhook_validator.is_valid(url):
                                    continue
                                
                                # Send webhook - YIELDS to event loop
                                webhook = AsyncDiscordWebhook(
                                    url=url,
                                    content=content,
                                    username="Solsbot Helper",
                                    avatar_url=self._bot.user.display_avatar.url if self._bot.user else None,
                                )
                                webhook.add_embed(discord_embed)
                                await webhook.execute()
                                
                                # YIELD after webhook send
                                await asyncio.sleep(0)
                                
                            except Exception as e:
                                logger.debug(f"Webhook send failed: {e}")
                    
                    # Parse errors - log with full context
                    if parse_result.errors:
                        for error in parse_result.errors:
                            logger.warning(f"Parse error: {error}")
                        # Log raw payload at debug level for deeper investigation
                        logger.debug(f"Full payload for failed parse: {raw_json[:2000]}")
                    
                except Exception as e:
                    logger.exception(f"Queue processing error: {e}")
                finally:
                    self.queue.task_done()
                    # ALWAYS yield before getting next message
                    await asyncio.sleep(0)
                    
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"Critical queue processor error: {e}")
                # Sleep briefly to avoid busy loop on persistent errors
                await asyncio.sleep(1)
