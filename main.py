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
from threading import Thread

from cogs._websocket import WebSocketClient, WORKERNOTDEFINED
from cogs._tortoiseORM_handler import DB

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
        return
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
        intents = disnake.Intents.default()
        intents.members = True
        super().__init__(
            intents=intents,
        )
        dotenv.load_dotenv()
        self.logger = logging.getLogger(__name__)
        self.db = DB(os.environ.get("DB_URL"))
        self.ws_manager = WebSocketClient(self)
        self.TOKEN = os.environ.get("BOT_TOKEN")
        self.usernames: list = []

        self.queue = set()


    async def start(self, *args, **kwargs) -> None:
        # Initialize database connection, start workers from keys in database,
        #   and set up queue processor to handle api events

        # Database initialization
        try:
            await self.db.start()
        except:
            self.logger.error("Something went wrong while initializing the database")
            raise

        # Initialize queue processor & websocket worker
        self.logger.info("Starting websocket connection...")
        try:
            await self.start_websocket()
            self.logger.info("Websocket worker up!")
        except:
            self.logger.error("Something went wrong while starting the websocket connection")
            raise


        # Initialize usernames list 
        self.logger.info("Initializing usernames list...")
        usernames = await DB.get_all_users()
        self.usernames = usernames


        self.logger.info("Starting queue processor...")
        try:
            self.start_queue_processor()
            self.logger.info("Queue processor up!")
        except:
            self.logger.error("Something went wrong while starting the queue processor")
            raise


        bot.logger.info("Starting bot...")

        await super().start(*args, **kwargs)

    # Builds a container for the queue processor asyncio & main api worker tasks to live in
    # This ensures python garbage collection doesn't sweep it away
    #   since it's a part of the SolsbotHelper class which won't go out of scope
    #   until the bot is terminated
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
        for i in range(1, 5):
            try:
                await asyncio.wait_for(ready_event.wait(), timeout=10.0)
                self.starting_up.set()
            except asyncio.TimeoutError:
                self.logger.error(f"Connection timed out ({i}/5), please wait...")
                if i == 5:
                    self.logger.error("Failure while connecting to websocket API. Is the API URL working?")
                    break
                else:
                    continue

    def start_queue_processor(self) -> None:
        process = self.ws_manager.queue_processor()
        process_queue = asyncio.create_task(process)
        
        self.queue.add(process_queue)
        process_queue.add_done_callback(self.queue.discard)


    async def on_ready(self) -> None:
        self.logger.info(f"Logged in as {bot.user}!")
        app_info = await self.application_info()
        self.logger.info(f"Bot Owner: {app_info.owner} (ID: {app_info.owner.id})")
        self.logger.info("Bot is running! Press (q) + enter to quit or (r) + enter to restart the bot.")

    async def close(self) -> None:
        self.logger.warning("Shutting bot down")
        try:
            await self.db.stop()
            await super().close()
            self.logger.info("Shutdown processed successfully")
        except Exception as e:
            self.logger.error("Something went wrong while shutting down\nForcefully shutting down...")
            self.logger.error(f"Shut down with errors: {e}")


bot = SolsbotHelper()

def load_cogs() -> None:
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and not filename.startswith("_"):
            extension_name = f'cogs.{filename[:-3]}'

            try:
                bot.load_extension(extension_name)
                bot.logger.info(f"Cogs: {extension_name} loaded successfully")
            except:
                bot.logger.error(f"Cogs: Failed to initialize {extension_name}")
                raise


# Define methods to quit and restart from terminal
def restart_bot() -> None:
    logging.getLogger(__name__).warning("Restarting bot...")
    os.execv(sys.executable, ["python3"] + sys.argv)

async def terminal_input(bot: SolsbotHelper) -> None:
    while True:
        user_input = await asyncio.to_thread(input)

        if user_input.lower().strip() == "q":
            await bot.close()
            break

        elif user_input.lower().strip() == "r":
            await bot.close()
            restart_bot()
            break


def main() -> None:
    bot.logger.info("Loading cogs...")
    try:
        load_cogs()
    except:
        bot.logger.info("Something went wrong while loading cogs")
        raise
    else:
        bot.logger.info("All cogs loaded successfully!")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.create_task(terminal_input(bot))

    try:
        loop.run_until_complete(bot.start(f"{bot.TOKEN}"))
    except KeyboardInterrupt:
        loop.run_until_complete(bot.close())
    finally:
        loop.close()


if __name__ == "__main__":
    main()