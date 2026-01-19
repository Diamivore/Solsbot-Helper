from tortoise import Tortoise
from . import _models
from tortoise import transactions

import logging
import time
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

# CUSTOM ERRORS #
class GUILDDISALLOW(Exception):
    pass
class GUILDWEBHOOKERROR(Exception):
    pass
class ITEMNOTDEFINED(Exception):
    pass
class ITEMEXISTS(Exception):
    pass

logger = logging.getLogger(__name__)

# TODO: Create commands to interact with auralist table

class DB():
    def __init__(self, db_url):
        self.db_url = db_url
        self.models = {"models": ["cogs._models"]}
        self.logger = logging.getLogger(__name__)

    # INITIALIZATION #
    async def start(self):
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

    async def stop(self):
        self.logger.info("Closing connection to database...")
        try:
            await Tortoise.close_connections()
            self.logger.info("Connection closed")
        except Exception as e:
            self.logger.error(f"Error while disconnecting database: {e}")


    # PREMADE COMMANDS #
    # Some non admin user commands
    @staticmethod
    async def add_guild_subscription(user_id: str, guild_id: int, guild_name: str):
        guild_settings, _ = await _models.GuildSettings.get_or_create(
            guild_id=guild_id, 
            defaults={"name": guild_name}
        )

        if guild_settings.allow_posting == False:
            raise GUILDDISALLOW
        if not guild_settings.post_channel_webhook:
            raise GUILDWEBHOOKERROR
        
        user, _ = await _models.User.get_or_create(user_id=user_id)
        current_guilds = user.guilds if user.guilds else []

        if guild_id in current_guilds:
            raise ITEMEXISTS
        
        current_guilds.append(guild_id)
        user.guilds = current_guilds

        await user.save(update_fields=["guilds"])
        
    @staticmethod
    async def remove_guild_subscription(user_id: int, guild_id: int) -> None:
        user, _ = await _models.User.get_or_create(user_id=user_id)
        current_guilds = user.guilds if user.guilds else []

        if guild_id not in user.guilds:
            raise ITEMNOTDEFINED
        
        current_guilds.remove(guild_id)
        user.guilds = current_guilds
        
        await user.save(update_fields=["guilds"])
    
    @staticmethod
    async def view_user_guilds(user_id: int) -> list:
        user, _ = await _models.User.get_or_create(user_id=user_id)
        if not user.guilds:
            raise ITEMNOTDEFINED
        
        return user.guilds
    
    @staticmethod
    async def add_username(user_id: int, username: str) -> None:
        # Check to make sure this username isn't already being used
        is_username = await _models.UsernameList.filter(name=username).first()
        if is_username:
            raise PermissionError

        user, created = await _models.User.get_or_create(user_id=user_id)
        if created:
            await _models.UsernameList.create(name=username, user_id=user)
        else:
            exists = await user.usernames.filter(name=username).first()
            if exists:
                raise ITEMEXISTS
            else:
                await _models.UsernameList.create(name=username, user_id=user)

    @staticmethod
    async def remove_username(user_id: int, username: str) -> None:
        user, created = await _models.User.get_or_create(user_id=user_id)
        if created:
            raise ITEMNOTDEFINED
        
        username: _models.User = await user.usernames.filter(name=username).first()
        
        if not username:
            raise ITEMNOTDEFINED
        else:
            await username.delete()

    @staticmethod
    async def view_usernames(user_id: int) -> list:
        user, created = await _models.User.get_or_create(user_id=user_id)
        user: _models.User
        if created:
            return []
        
        username_list = await user.usernames.all().values_list("name", flat=True)
        return username_list

    # Admin commands, permissions are handled by command permissions
    @staticmethod
    async def add_guild_webhook(guild_id: int, webhook_url: str, guild_name: str):
        guild_settings, _ = await _models.GuildSettings.get_or_create(
            guild_id=guild_id, 
            defaults={"name": guild_name}
        )
        guild_settings: _models.GuildSettings

        guild_settings.post_channel_webhook = webhook_url
        await guild_settings.save(update_fields=["post_channel_webhook"])

    @staticmethod
    async def add_guild_role(guild_id: int, role_id: int, guild_name: str):
        guild_settings, _ = await _models.GuildSettings.get_or_create(
            guild_id=guild_id, 
            defaults={"name": guild_name}
        )
        guild_settings: _models.GuildSettings

        if role_id == 0:
            guild_settings.can_post_role = None
            await guild_settings.save(update_fields=["can_post_role"])
            return

        guild_settings.can_post_role = role_id
        await guild_settings.save(update_fields=["can_post_role"])

    @staticmethod
    async def get_guild_posting(guild_id: int, guild_name: str) -> bool:
        guild_settings, _ = await _models.GuildSettings.get_or_create(
            guild_id=guild_id, 
            defaults={"name": guild_name}
        )
        return guild_settings.allow_posting

    @staticmethod
    async def toggle_guild_posting(guild_id: int, guild_name: str) -> None:
        guild_settings, _ = await _models.GuildSettings.get_or_create(
            guild_id=guild_id, 
            defaults={"name": guild_name}
        )
        guild_settings: _models.GuildSettings

        can_post = guild_settings.allow_posting

        if can_post:
            guild_settings.allow_posting = False
            await guild_settings.save(update_fields=["allow_posting"])

            users = await _models.User.filter(guilds__contains=[guild_id])

            if users:
                for user in users:
                    current_guilds = user.guilds if user.guilds else []
                    
                    if guild_id in current_guilds:
                        user.guilds = [g for g in current_guilds if g != guild_id]

                await _models.User.bulk_update(users, fields=["guilds"])

        elif not can_post:
            guild_settings.allow_posting = True
            await guild_settings.save(update_fields=["allow_posting"])

    @staticmethod
    async def get_user_destinations(username: str) -> tuple:
        username = await _models.UsernameList.get(name=username).prefetch_related("user_id")
        username: _models.UsernameList
        user_id = username.user_id.user_id

        user = await _models.User.get(user_id=user_id)
        return await _models.GuildSettings.filter(
            guild_id__in=user.guilds
            ).values_list(
                "post_channel_webhook", 
                "guild_id", 
                "can_post_role"
                ), user.user_id

    @staticmethod
    async def get_all_users() -> list:
        usernames: _models.UsernameList = await _models.UsernameList.all().prefetch_related("user_id")
        users = []

        usernames_string = ""
        for username in usernames[:50]:
            usernames_string = f"{username}, "

        if not usernames:
            usernames_string = "No registered usernames"

        with logging_redirect_tqdm():
            with tqdm(total=len(usernames), desc="Processing usernames") as progress:
                for user in usernames:
                    if user.user_id.guilds:
                        users.append(user.name)
                    progress.update(1)

        logger.debug(f"Added usernames to list:\n{usernames_string}" + (f"... + {(len(usernames) - 50)}" if len(usernames) > 50 else ""))
        return users
    

