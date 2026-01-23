import disnake
import disnake.ui as ui
from disnake.ext import commands
import logging

from services import (
    UserService,
    GuildNotAllowedError,
    GuildWebhookError,
    ItemNotFoundError,
    ItemExistsError,
)
from infrastructure import WORKERRUNNING, WORKERNOTDEFINED

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
            await UserService.add_username(inter.user.id, username.lower())
            # Update in-memory cache
            self.bot.ws_manager.add_username(username.lower())
            self.logger.debug(f"Successfully added {username} to cache")
            embed = disnake.Embed(description=f"Username **{username}** has been added.")
            await inter.response.send_message(embed=embed, ephemeral=True)
        except PermissionError:
            embed = disnake.Embed(description="That username is already registered.")
            await inter.response.send_message(embed=embed, ephemeral=True)
        except ItemExistsError:
            embed = disnake.Embed(description="You already have that username registered.")
            await inter.response.send_message(embed=embed, ephemeral=True)
                
    @commands.slash_command(description="Remove a Roblox username from this Discord account.")
    async def remove_username(
        self,
        inter: disnake.ApplicationCommandInteraction,
        username: str
    ) -> None:
        username_lower = username.lower()
        try:
            await UserService.remove_username(inter.user.id, username_lower)
            # Update in-memory cache
            self.bot.ws_manager.remove_username(username_lower)
            self.logger.debug(f"Successfully removed {username_lower} from cache")
            embed = disnake.Embed(description=f"Username **{username}** has been removed.")
            await inter.response.send_message(embed=embed, ephemeral=True)
        except PermissionError:
            embed = disnake.Embed(description="You do not own this user.")
            await inter.response.send_message(embed=embed, ephemeral=True)
        except ItemNotFoundError:
            embed = disnake.Embed(description="That user does not exist.")
            await inter.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(description="See all your stored usernames.")
    async def view_usernames(
        self,
        inter: disnake.ApplicationCommandInteraction
    ) -> None:
        usernames = await UserService.view_usernames(inter.user.id)

        if not usernames:
            embed = disnake.Embed(description="You have no added users.")
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        usernames_list = "\n".join(f"• {username}" for username in usernames)
        content = f"## Your Usernames\n{usernames_list}"
        
        container = ui.Container(
            ui.TextDisplay(content),
            accent_colour=None,
        )
        await inter.response.send_message(
            components=[container],
            flags=disnake.MessageFlags(is_components_v2=True),
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
            embed = disnake.Embed(description="Invalid ID. Please provide a numerical server ID.")
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        guild = self.bot.get_guild(guild_id)
        guild_name = guild.name if guild else "Unknown Server"

        try:
            await UserService.add_guild_subscription(inter.user.id, guild_id, guild_name)
            embed = disnake.Embed(description="Server added to subscription list.")
            await inter.response.send_message(embed=embed, ephemeral=True)
        except GuildNotAllowedError:
            embed = disnake.Embed(
                description="This server does not currently allow notifications.\n\n*If you think this is wrong, please ask this server's admins to use `/admin toggle_notifications`*"
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
        except GuildWebhookError:
            embed = disnake.Embed(
                description="This server currently has no assigned notification webhook.\n\n*Please ask the admins to use `/admin add_subscriber_webhook`*"
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
        except ItemExistsError:
            embed = disnake.Embed(description="You have already added this server.")
            await inter.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(description="Remove a server to post notifications to.")
    async def remove_server(
        self,
        inter: disnake.ApplicationCommandInteraction,
        server_id: str
    ) -> None:
        try:
            server_id = int(server_id)
        except ValueError:
            embed = disnake.Embed(description="Invalid ID. Please provide a numerical server ID.")
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            await UserService.remove_guild_subscription(inter.user.id, server_id)
            embed = disnake.Embed(description="Server successfully removed.")
            await inter.response.send_message(embed=embed, ephemeral=True)
        except ItemNotFoundError:
            embed = disnake.Embed(description="You do not have this server added.")
            await inter.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(description="View all servers you post notficiations to.")
    async def view_servers(
        self,
        inter: disnake.ApplicationCommandInteraction
    ) -> None:
        try:
            guilds = await UserService.view_user_guilds(inter.user.id)
        except ItemNotFoundError:
            embed = disnake.Embed(description="You are not subscribed to any guilds currently.")
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        if guilds:
            guild_lines = []
            for guild_id in guilds:
                guild: disnake.Guild = await self.bot.fetch_guild(guild_id)
                if not guild:
                    continue
                guild_lines.append(f"• **{guild.name}** (`{guild.id}`)")
            
            guilds_list = "\n".join(guild_lines)
            content = f"## Your Servers\n{guilds_list}"
            
            container = ui.Container(
                ui.TextDisplay(content),
                accent_colour=None,
            )
            await inter.response.send_message(
                components=[container],
                flags=disnake.MessageFlags(is_components_v2=True),
                ephemeral=True
            )


    # Autocomplete definitions
    @remove_username.autocomplete("username")
    async def find_usernames(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        string: str
        ) -> list:
        usernames = await UserService.view_usernames(inter.user.id)
        return [u for u in usernames if string.lower() in u.lower()]
    
    @remove_server.autocomplete("server_id")
    async def find_guilds(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        string: str
        ) -> list:
        try:
            user_guild_ids = await UserService.view_user_guilds(inter.user.id)
        except ItemNotFoundError:
            return []
        
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