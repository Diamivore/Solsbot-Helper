import disnake
from disnake.ext import commands
import logging
import traceback
import discord_webhook
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.webhook_url: str | None = os.environ.get("OWNER_WEBHOOK_DEBUG_URL")

        # Validate webhook URL format
        if self.webhook_url and not self._is_valid_webhook_url(self.webhook_url):
            logger.warning("OWNER_WEBHOOK_DEBUG_URL has invalid format. Webhooks disabled.")
            self.webhook_url = None
        elif not self.webhook_url:
            logger.warning("OWNER_WEBHOOK_DEBUG_URL not set. Error webhooks disabled.")

    @staticmethod
    def _is_valid_webhook_url(url: str) -> bool:
        """Validate webhook URL is a Discord webhook."""
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in ("http", "https")
                and "discord.com" in parsed.netloc
                and "/api/webhooks/" in parsed.path
            )
        except Exception:
            return False

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

        tb_str = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

        # Handle specific errors
        if isinstance(error, commands.MissingPermissions):
            embed = disnake.Embed(description="You don't have permissions to run this command.")
            await inter.send(embed=embed, ephemeral=True)
            return
        elif isinstance(error, commands.NotOwner):
            embed = disnake.Embed(description="Only the bot owner can use this command.")
            await inter.send(embed=embed, ephemeral=True)
            return
        elif isinstance(error, PermissionError):
            embed = disnake.Embed(description="You do not own this item.")
            await inter.send(embed=embed, ephemeral=True)
            return
        elif isinstance(error, commands.CommandOnCooldown):
            embed = disnake.Embed(description=f"Slow down! Try again in {error.retry_after:.2f}s")
            await inter.response.send_message(embed=embed, ephemeral=True)
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = disnake.Embed(description=f"Missing required argument: `{error.param.name}`")
            await inter.send(embed=embed, ephemeral=True)
            return
        elif isinstance(error, commands.BadArgument):
            embed = disnake.Embed(description=f"Invalid argument provided. {error}")
            await inter.send(embed=embed, ephemeral=True)
            return
        elif isinstance(error, commands.CommandNotFound):
            embed = disnake.Embed(description="That command doesn't exist.")
            await inter.send(embed=embed, ephemeral=True)
            return
        elif isinstance(error, commands.CheckFailure):
            embed = disnake.Embed(description="You failed a command check.")
            await inter.send(embed=embed, ephemeral=True)
            return
        elif isinstance(error, commands.MaxConcurrencyReached):
            embed = disnake.Embed(description="This command is already running. Please wait.")
            await inter.send(embed=embed, ephemeral=True)
            return
        elif isinstance(error, disnake.Forbidden):
            embed = disnake.Embed(description="I don't have permission to do that.")
            await inter.send(embed=embed, ephemeral=True)
            return
        elif isinstance(error, disnake.NotFound):
            embed = disnake.Embed(description="That resource was not found.")
            await inter.send(embed=embed, ephemeral=True)
            return
        elif isinstance(error, disnake.HTTPException):
            embed = disnake.Embed(description=f"A Discord API error occurred. (Status: {error.status})")
            await inter.send(embed=embed, ephemeral=True)
            logger.error(
                f"HTTPException in {inter.application_command.name}: "
                f"{error.status}"
            )
            return

        # Log and send webhook for unexpected errors
        try:
            await self.send_error_webhook(inter, error, tb_str)
        except Exception as webhook_error:
            logger.error(f"Failed to send error webhook: {webhook_error}")

        logger.error(
            f"Ignoring exception in command {inter.application_command.name}:",
            exc_info=True
        )

        if not inter.response.is_done():
            embed = disnake.Embed(
                description="An unexpected error occurred. The developer has been notified."
            )
            await inter.send(embed=embed, ephemeral=True)

    async def send_error_webhook(
        self,
        inter: disnake.ApplicationCommandInteraction,
        error: Exception,
        traceback_str: str
    ) -> None:
        """Send error details to webhook without exposing sensitive data."""
        if not self.webhook_url:
            logger.warning("Webhook URL not configured. Skipping error webhook.")
            return

        try:
            webhook = discord_webhook.AsyncDiscordWebhook(
                url=self.webhook_url,
                username="Solsbot Debugger",
                content=f"<@{self.bot.owner_id}>"
            )

            # Sanitize error message and limit length
            error_msg = self._sanitize_string(str(error))
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "... (truncated)"

            # Sanitize traceback (remove file paths and sensitive info)
            sanitized_tb = self._sanitize_traceback(traceback_str)
            if len(sanitized_tb) > 900:
                sanitized_tb = sanitized_tb[:900] + "... (truncated)"

            # Sanitize command name and user info
            command_name = self._sanitize_string(
                inter.application_command.name
            )
            user_name = self._sanitize_string(str(inter.user))

            desc_text = (
                f"**Command:** `/{command_name}`\n"
                f"**User:** {user_name} (`{inter.user.id}`)\n"
                f"**Error Type:** `{type(error).__name__}`"
            )
            embed = discord_webhook.DiscordEmbed(
                title="Command Error",
                description=desc_text,
                color=15158332
            )
            embed.add_embed_field(
                name="Error Message",
                value=f"```\n{error_msg}\n```",
                inline=False
            )
            embed.add_embed_field(
                name="Traceback",
                value=f"```python\n{sanitized_tb}\n```",
                inline=False
            )

            webhook.add_embed(embed)
            await webhook.execute()

        except Exception as webhook_error:
            logger.error(f"Failed to execute error webhook: {webhook_error}")

    @staticmethod
    def _sanitize_string(text: str) -> str:
        """Remove potentially harmful characters from user input."""
        # Remove markdown code blocks and backticks
        text = text.replace("```", "")
        text = text.replace("`", "")
        # Remove Discord webhook URLs entirely (contains ID + token)
        import re
        text = re.sub(
            r'https?://(?:www\.)?discord\.com/api/webhooks/\d+/[^\s/]+',
            '[WEBHOOK_REDACTED]',
            text
        )
        return text.strip()

    @staticmethod
    def _sanitize_traceback(traceback_str: str) -> str:
        """Remove sensitive file paths from traceback."""
        lines = traceback_str.split("\n")
        sanitized_lines = []

        for line in lines:
            # Remove full file paths, keep only filename
            if 'File "' in line:
                try:
                    start = line.index('File "') + 6
                    end = line.index('"', start)
                    file_path = line[start:end]
                    # Keep only the filename, not the full path
                    file_name = file_path.split("/")[-1]
                    line = line.replace(file_path, file_name)
                except (ValueError, IndexError):
                    pass

            sanitized_lines.append(line)

        return "\n".join(sanitized_lines)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(ErrorHandler(bot))