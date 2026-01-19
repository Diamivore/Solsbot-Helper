import disnake
from disnake.ext import commands
import logging
import traceback
import discord_webhook
import os
import dotenv

logger = logging.getLogger(__name__)


class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot

    @commands.Cog.listener()
    async def on_slash_command_error(
        self,
        inter: disnake.ApplicationCommandInteraction,
        error: Exception
    ) -> None:
        if hasattr(inter.application_command, "on_error"):
            return
        if hasattr(error, "original"):
            error = error.original

        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))

        if isinstance(error, commands.MissingPermissions):
            await inter.send("You don't have permissions to run this command.", ephemeral=True)
            return
        elif isinstance(error, commands.NotOwner):
            await inter.send("Only the bot owner can use this command.", ephemeral=True)
            return
        elif isinstance(error, PermissionError):
            await inter.send("You do not own this item.", ephemeral=True)
            return
        elif isinstance(error, commands.CommandOnCooldown):
            await inter.response.send_message(f"Slow down! Try again in {error.retry_after:.2f}s", ephemeral=True)
            return

        try:
            await self.send_error_webhook(inter, error, tb_str)
        except Exception as e:
            logger.error(f"Failed to send error webhook: {e}")

        logger.error(f"Ignoring exception in command: {inter.application_command.name}:")
        traceback.print_exception(type(error), error, error.__traceback__)

        if not inter.response.is_done():
            await inter.send("An unexpected error occured. The developer has been notified.", ephemeral=True)


    async def send_error_webhook(self, inter, error, traceback_str):
        dotenv.load_dotenv()
        webhook = discord_webhook.AsyncDiscordWebhook(
            url=f"{os.environ.get("OWNER_WEBHOOK_DEBUG_URL")}",
            username="Solsbot Debugger",
            content=f"<@{self.bot.owner_id}>"
        )

        # Truncate error message if it's huge
        error_msg = str(error)
        if len(error_msg) > 500:  
            error_msg = error_msg[:500] + "... (error message truncated)"

        desc_text = f"**User:** {inter.user} (`{inter.user.id}`)\n**Error:** `{error_msg}`"

        embed = discord_webhook.DiscordEmbed(
            title=f"Error in /{inter.application_command.name}",
            description=desc_text,
            color=15158332
        )

        if len(traceback_str) > 900:
            traceback_str = traceback_str[:900] + "... (truncated)"
            
        embed.add_embed_field(name="Traceback", value=f"```python\n{traceback_str}\n```")
        
        webhook.add_embed(embed)
        await webhook.execute()



def setup(bot: commands.Bot):
    bot.add_cog(ErrorHandler(bot))