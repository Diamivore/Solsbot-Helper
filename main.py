import disnake
import asyncio
import os
import dotenv
import logging
from logging.handlers import RotatingFileHandler
import colorlog
import sys
from disnake.ext import commands
import argparse
import time

from infrastructure import Database, WebSocketClient, WORKERNOTDEFINED

# Set up argument parsing for --verbose
parser = argparse.ArgumentParser(description="Solsbot Helper")
parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")
parser.add_argument("--silent", "-s", action="store_true", help="Disable all logging (Good for headless)")
args = parser.parse_args()

# Set up logs
def setup_logger():
    logger = logging.getLogger()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.silent:
        logging.disable()
        return logger  # Still return the logger object
    else:
        logger.setLevel(logging.INFO)
        logging.getLogger("asyncmy").setLevel(logging.ERROR)

    handler = logging.StreamHandler()
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s | %(name)s [%(levelname)s]%(reset)s: %(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'blue',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
            },
        
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    noisy_modules = [
        "disnake.gateway",
        "disnake.client",
        "disnake.http",
        "websockets",
        "tortoise",
        "asyncio",
        "disnake.ext.commands.interaction_bot_base",
        "httpcore.connection",
        "disnake.webhook.async_",
        "httpcore.http11",
        "httpx"
    ]

    # Some modules' debugging logs are really, really... REALLY long (or unnecessary)
    for module in noisy_modules:
        mod_logger = logging.getLogger(module)
        mod_logger.setLevel(logging.WARNING)

    return logger
setup_logger()

# Get rid of annoying disnake warning (voice support isn't necessary)
class NoVoiceFilter(logging.Filter):
    def filter(self, record):
        return "PyNaCl" not in record.getMessage()
logging.getLogger("disnake.client").addFilter(NoVoiceFilter())
# Get rid of annoying "table already exists" tortoise warning (safe mode is on)
class NoTableExistsFilter(logging.Filter):
    def filter(self, record):
        return "Table 'subscriptions' already exists" not in record.getMessage()
logging.getLogger("asyncmy").addFilter(NoTableExistsFilter())


class SolsbotHelper(commands.InteractionBot):
    def __init__(self):
        dotenv.load_dotenv()
        self.logger = logging.getLogger(__name__)
        
        # Determine environment mode
        self.environment = os.environ.get("ENVIRONMENT", "development").lower()
        is_production = self.environment == "production"
        
        # Validate required env vars
        sols_token = os.environ.get("SOLS_BOT_TOKEN")
        
        # Select database URL based on environment
        if is_production:
            db_url = os.environ.get("DB_URL")
            db_name = "DB_URL"
        else:
            # In development, prefer DEV_DB_URL, fallback to DB_URL
            db_url = os.environ.get("DEV_DB_URL") or os.environ.get("DB_URL")
            db_name = "DEV_DB_URL" if os.environ.get("DEV_DB_URL") else "DB_URL"
        
        # Select bot token based on environment
        if is_production:
            bot_token = os.environ.get("BOT_TOKEN")
            token_name = "BOT_TOKEN"
        else:
            # In development, prefer BOT_TOKEN_DEV, fallback to BOT_TOKEN
            bot_token = os.environ.get("BOT_TOKEN_DEV") or os.environ.get("BOT_TOKEN")
            token_name = "BOT_TOKEN_DEV" if os.environ.get("BOT_TOKEN_DEV") else "BOT_TOKEN"
        
        if not all([db_url, bot_token, sols_token]):
            raise RuntimeError(
                "Missing required environment variables: "
                f"{db_name}={bool(db_url)}, {token_name}={bool(bot_token)}, SOLS_BOT_TOKEN={bool(sols_token)}"
            )
        
        self.logger.info(f"Starting in {self.environment.upper()} mode (using {token_name}, {db_name})")
        
        intents = disnake.Intents.default()
        intents.members = True
        super().__init__(intents=intents)
        
        self.db = Database(db_url)
        self.ws_manager = WebSocketClient(self)
        self.TOKEN = bot_token
        self.queue = set()


    async def start(self, *args, **kwargs) -> None:
        # Database initialization
        try:
            await self.db.start()
        except Exception as e:
            self.logger.error(f"Something went wrong while initializing the database: {e}")
            raise

        # Initialize websocket connection
        self.logger.info("Starting websocket connection...")
        try:
            await self.start_websocket()
            self.logger.info("Websocket worker up!")
        except Exception as e:
            self.logger.error(f"Something went wrong while starting the websocket connection: {e}")
            raise

        # Start queue processor (initializes service layer with username cache)
        self.logger.info("Starting queue processor...")
        try:
            self.start_queue_processor()
            self.logger.info("Queue processor up!")
        except Exception as e:
            self.logger.error(f"Something went wrong while starting the queue processor: {e}")
            raise

        # Start health check writer for Kubernetes probes
        self.logger.info("Starting health check writer...")
        health_task = asyncio.create_task(health_writer())
        self.queue.add(health_task)
        health_task.add_done_callback(self.queue.discard)


        self.logger.info("Starting bot...")

        await super().start(*args, **kwargs)

    # Task container to prevent garbage collection
    async def start_websocket(self):
        ready_event = asyncio.Event()

        worker = self.ws_manager.websocket_worker(
            os.environ.get("SOLS_BOT_TOKEN"),
            ready_event
        )
        worker_queue = asyncio.create_task(worker)

        self.queue.add(worker_queue)
        worker_queue.add_done_callback(self.queue.discard)

        self.starting_up = asyncio.Event()
        for i in range(1, 3):
            try:
                await asyncio.wait_for(ready_event.wait(), timeout=10.0)
                self.starting_up.set()
                return 
            except asyncio.TimeoutError:
                self.logger.error(f"Connection timed out ({i}/2), please wait...")
                if i == 2:
                    self.logger.error("Failure while connecting to websocket API. Is the API URL working?")
                    raise RuntimeError("Websocket connection failed after 2 retries")

    def start_queue_processor(self) -> None:
        process = self.ws_manager.queue_processor()
        process_queue = asyncio.create_task(process)
        
        self.queue.add(process_queue)
        process_queue.add_done_callback(self.queue.discard)


    async def on_ready(self) -> None:
        self.logger.info(f"Logged in as {self.user}!")
        app_info = await self.application_info()
        self.logger.info(f"Bot Owner: {app_info.owner} (ID: {app_info.owner.id})")
        self.logger.info("Bot is running! Press (q) + enter to quit or (r) + enter to restart the bot.")

    async def close(self) -> None:
        self.logger.warning("Shutting bot down")
        try:
            await self.db.stop()
            
            # Cancel and wait for background tasks
            for task in self.queue:
                task.cancel()
            
            # Give cancelled tasks time to finish
            if self.queue:
                await asyncio.gather(*self.queue, return_exceptions=True)
            
            await super().close()
            self.logger.info("Shutdown processed successfully")
        except Exception as e:
            self.logger.error(f"Something went wrong while shutting down: {e}")


bot = SolsbotHelper()

def load_cogs() -> None:
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and not filename.startswith("_"):
            extension_name = f'cogs.{filename[:-3]}'

            try:
                bot.load_extension(extension_name)
                bot.logger.info(f"Cogs: {extension_name} loaded successfully")
            except Exception as e:
                bot.logger.error(f"Cogs: Failed to initialize {extension_name}: {e}")
                raise


async def health_writer():
    """Write health file for Kubernetes probes. Uses thread to avoid blocking event loop."""
    def _write_health():
        with open('/tmp/health', 'w') as f:
            f.write(str(time.time()))
    
    while True:
        try:
            await asyncio.to_thread(_write_health)
        except Exception:
            pass  # Non-critical, don't crash on health write failure
        await asyncio.sleep(10)


def main() -> None:
    bot.logger.info("Loading cogs...")
    try:
        load_cogs()
    except:
        bot.logger.info("Something went wrong while loading cogs")
        raise
    else:
        bot.logger.info("All cogs loaded successfully!")

    bot.run(bot.TOKEN)


if __name__ == "__main__":
    main()