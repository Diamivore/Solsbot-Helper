"""Database connection management."""
import logging
from tortoise import Tortoise


logger = logging.getLogger(__name__)


class Database:
    """Manages database connections using Tortoise ORM."""
    
    def __init__(self, db_url: str, models_module: str = "models"):
        self.db_url = db_url
        self.models_module = models_module
        self.models = {"models": [models_module]}
        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Initialize database connection and generate schemas."""
        self.logger.info("Connecting to database...")

        try:
            await Tortoise.init(
                db_url=self.db_url,
                modules=self.models
            )
            await Tortoise.generate_schemas(safe=True)
        except Exception:
            self.logger.error("Error while connecting to database")
            raise

        self.logger.info("Database connected and verified")

    async def stop(self) -> None:
        """Close database connections."""
        self.logger.info("Closing connection to database...")
        try:
            await Tortoise.close_connections()
            self.logger.info("Connection closed")
        except Exception as e:
            self.logger.error(f"Error while disconnecting database: {e}")
