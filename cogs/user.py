import disnake
from disnake.ext import commands
import logging

from ._tortoiseORM_handler import DB
from ._tortoiseORM_handler import GUILDDISALLOW, GUILDWEBHOOKERROR, ITEMNOTDEFINED, ITEMEXISTS

from ._websocket import WORKERRUNNING, WORKERNOTDEFINED

# TODO: Create commands to handle auralist table

# Commands:
# Add username
# Remove username
# View usernames
#
# Add guilds
# Remove guild
# See guilds
#
# Future -> Commands for adding, removing and seeing unconfirmed auras from auralist
# Future -> Commands for adding, removing and seeing specific usernames from guilds

class user(commands.Cog):
    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)


    # The actual bot commands
    @commands.slash_command(description="Add a Roblox username to this Discord account to get notifications from.")
    async def add_username(
        self,
        inter: disnake.ApplicationCommandInteraction,
        username: str,
    ) -> None:
        try:
            await DB.add_username(inter.user.id, username.lower())
            try:
                self.bot.usernames.append(username.lower())
                self.logger.debug(f"Successfully appended {username} to global list")
            except Exception as e:
                self.logger.error(f"Error while appending {username} to global list: {e}")
            await inter.response.send_message(
                f"Username **{username}** has been added!",
                ephemeral=True
            )
        except PermissionError:
            await inter.response.send_message(
                "That username is already registered!",
                    ephemeral=True
                    )
        except ITEMEXISTS:
            await inter.response.send_message(
                "You already have that username registered!",
                    ephemeral=True
                    )
                
    @commands.slash_command(description="Remove a Roblox username from this Discord account.")
    async def remove_username(
        self,
        inter: disnake.ApplicationCommandInteraction,
        username: str
    ) -> None:
        try:
            await DB.remove_username(inter.user.id, username)
            try:
                self.bot.usernames.remove(username)
                self.logger.debug(f"Successfully removed {username} from global list")
            except Exception as e:
                self.logger.error(f"Error while removing {username} from global list: {e}")
            await inter.response.send_message(
                f"Username **{username}** has been removed.",
                ephemeral=True
            )
        except PermissionError:
            await inter.response.send_message(
                "You do not own this user.",
                ephemeral=True
            )
        except ITEMNOTDEFINED:
            await inter.response.send_message(
                "That user does not exist.",
                ephemeral=True
            )

    @commands.slash_command(description="See all your stored usernames.")
    async def view_usernames(
        self,
        inter: disnake.ApplicationCommandInteraction
    ) -> None:
        usernames = await DB.view_usernames(inter.user.id)

        if not usernames:
            await inter.response.send_message(
                "You have no added users.",
                ephemeral=True
            )
            return

        response = ""
        for username in usernames:
            response = response + f"{username}\n"
                                                 
        await inter.response.send_message(
            "**Your Users:**\n" + response,
            ephemeral=True
        )

    @commands.slash_command(description="Add a server to post notifications to.")
    async def add_server(
        self,
        inter: disnake.ApplicationCommandInteraction,
        server_id: str
    ) -> None:
        try:
            guild_id = int(server_id)
        except ValueError:
            await inter.response.send_message(
                "Invalid ID. Please provide a numerical server ID.",
                ephemeral=True
            )
            return

        guild = self.bot.get_guild(guild_id)
        guild_name = guild.name if guild else "Unknown Server"

        try:
            
            await DB.add_guild_subscription(inter.user.id, guild_id, guild_name)   
            await inter.response.send_message(
                "Server added to subscription list.",
                ephemeral=True
            )
        except GUILDDISALLOW:
            await inter.response.send_message(
                "This server does not currently allow notifications.\nIf you think this is wrong, please ask this server's admins to use /toggle_notifications",
                ephemeral=True
            )
        except GUILDWEBHOOKERROR:
            await inter.response.send_message(
                "This server currently has no assigned notification webhook.\nPlease ask the admins to use /add_webhook",
                ephemeral=True
            )
        except ITEMEXISTS:
            await inter.response.send_message(
                "You have already added this server!",
                ephemeral=True
            )

    @commands.slash_command(description="Remove a server to post notifications to.")
    async def remove_server(
        self,
        inter: disnake.ApplicationCommandInteraction,
        server_id: str
    ) -> None:
        try:
            server_id = int(server_id)
        except ValueError:
            await inter.response.send_message(
                "Invalid ID. Please provide a numerical server ID.",
                ephemeral=True
            )
            return

        try:
            await DB.remove_guild_subscription(inter.user.id, server_id)
            await inter.response.send_message(
                "Server successfully removed!",
                ephemeral=True
            )
        except ITEMNOTDEFINED:
            await inter.response.send_message(
                "You do not have this server added!",
                ephemeral=True
            )

    @commands.slash_command(description="View all servers you post notficiations to.")
    async def view_servers(
        self,
        inter: disnake.ApplicationCommandInteraction
    ) -> None:
        try:
            guilds = await DB.view_user_guilds(inter.user.id)
        except ITEMNOTDEFINED:
            await inter.response.send_message(
                "You are not subscribed to any guilds currently.",
                ephemeral=True
            )
            return

        if guilds:
            guild_str = ""
            for guild in guilds:
                guild: disnake.Guild = await self.bot.fetch_guild(guild)
                if not guild:
                    continue

                guild_name = guild.name
                guild_id = guild.id

                guild_str = guild_str + f"{guild_name}: {guild_id}\n"
            await inter.response.send_message(
                "**Your Guilds:**\n" + guild_str,
                ephemeral=True
            )


    # Autocomplete definitions
    @remove_username.autocomplete("username")
    async def find_usernames(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        string: str
        ) -> list:
        usernames = await DB.view_usernames(inter.user.id)
        return [u for u in usernames if string.lower() in u.lower()]
    
    @remove_server.autocomplete("server_id")
    async def find_guilds(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        string: str
        ) -> list:
        user_guild_ids = await DB.view_user_guilds(inter.user.id)
        
        choices = []
        for g_id in user_guild_ids:
            guild = self.bot.get_guild(g_id)
            name = guild.name if guild else str(g_id)
            
            if string.lower() in name.lower() or string in str(g_id):
                choices.append(disnake.OptionChoice(name=name, value=str(g_id)))
        
        return choices[:25]
    
    @add_server.autocomplete("server_id")
    async def find_mutual_guilds(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        string: str
        ) -> list:
            return [
            disnake.OptionChoice(name=g.name, value=str(g.id))
            for g in inter.user.mutual_guilds
            if string.lower() in g.name.lower()
            ][:25]


def setup(bot: commands.InteractionBot):
    bot.add_cog(user(bot=bot))