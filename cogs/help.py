import disnake
import disnake.ui as ui
from disnake.ext import commands
import time


# Help content definitions (now as text for TextDisplay)
MAIN_CONTENT = (
    "## Solsbot Helper\n"
    "Keep your friends updated on your Sol's RNG finds!\n"
    "• Get notified in Discord when you or your friends find auras\n"
    "• Subscribe to multiple servers at once\n"
    "• Server admins can control who posts and where\n\n"
    "*New here? Select a topic below to get started!*"
)

GETTING_STARTED_CONTENT = (
    "## Getting Started\n\n"
    "For Users:\n"
    "1. Use `/add_username [Roblox Username]` to register your account\n"
    "2. Use `/add_server [Server ID]` to add servers for notifications\n"
    "3. That's it! You'll get notified when you find auras.\n"
    "For Server Admins:\n"
    "1. Use `/admin add_subscriber_webhook [URL]` to set your notification channel\n"
    "2. Use `/admin toggle_notifications` to enable posting\n"
    "3. Optionally, use `/admin add_notification_role [Role ID]` to restrict who can post"
)


def build_command_content(bot: commands.InteractionBot, cog_name: str, title: str) -> str:
    """Build a markdown-formatted string listing commands from a cog."""
    cog = bot.get_cog(cog_name)
    lines = [f"# {title}\n"]
    
    if cog:
        for cmd in cog.get_slash_commands():
            # Skip owner-only commands (dev commands)
            if hasattr(cmd, 'checks'):
                if any(check.__qualname__.startswith('is_owner') for check in cmd.checks):
                    continue
            
            # Check if it's a parent command with sub-commands
            if hasattr(cmd, 'children') and cmd.children:
                # It's a command group - list sub-commands instead
                for sub_name, sub_cmd in cmd.children.items():
                    desc = sub_cmd.description or "No description."
                    lines.append(f"**/{cmd.name} {sub_name}**\n> {desc}\n")
            else:
                # Regular command
                desc = cmd.description or "No description."
                lines.append(f"**/{cmd.name}**\n> {desc}\n")
    
    return "\n".join(lines)


def build_help_container(content: str, disabled: bool = False) -> list:
    """Build Components V2 layout with Container and external buttons."""
    dropdown = ui.StringSelect(
        custom_id="help_dropdown",
        placeholder="Select a help topic..." if not disabled else "This menu has expired",
        disabled=disabled,
        options=[
            disnake.SelectOption(
                label="Getting Started",
                value="getting_started",
                description="How to set up the bot",
            ),
            disnake.SelectOption(
                label="User Commands",
                value="user",
                description="Commands for managing your notifications",
            ),
            disnake.SelectOption(
                label="Admin Commands",
                value="admin",
                description="Server configuration commands",
            ),
        ]
    )
    
    container = ui.Container(
        ui.TextDisplay(content),
        ui.Separator(spacing=disnake.SeparatorSpacing.small),
        ui.ActionRow(dropdown),
        accent_colour=None,  # None disables the accent bar entirely
    )
    
    # Buttons outside the container
    buttons = ui.ActionRow(
        ui.Button(
            label="Support",
            style=disnake.ButtonStyle.link,
            url="https://discord.gg/934ED3JZqs",
        ),
        ui.Button(
            label="Invite the bot",
            style=disnake.ButtonStyle.link,
            url="https://discord.com/oauth2/authorize?client_id=1457837557516603465",
        ),
    )
    
    return [container, buttons]


HELP_TIMEOUT = 60  # seconds


# Main help command
class HelpCommand(commands.Cog):
    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot
        # Track message timestamps for timeout: {message_id: last_interaction_time}
        self._help_timestamps: dict[int, float] = {}

    @commands.slash_command(description="Show all available commands")
    async def help(self, inter: disnake.ApplicationCommandInteraction):
        components = build_help_container(MAIN_CONTENT)
        await inter.response.send_message(
            components=components,
            flags=disnake.MessageFlags(is_components_v2=True)
        )
        # Track this message for timeout
        msg = await inter.original_response()
        self._help_timestamps[msg.id] = time.time()

    @commands.Cog.listener("on_dropdown")
    async def help_dropdown_handler(self, inter: disnake.MessageInteraction):
        """Handle the help dropdown selections."""
        if inter.component.custom_id != "help_dropdown":
            return
        
        msg_id = inter.message.id
        
        # Check timeout
        if msg_id in self._help_timestamps:
            if time.time() - self._help_timestamps[msg_id] > HELP_TIMEOUT:
                # Expired - disable the dropdown and clean up
                del self._help_timestamps[msg_id]
                components = build_help_container(MAIN_CONTENT, disabled=True)
                await inter.response.edit_message(components=components)
                return
            # Reset timer on valid interaction
            self._help_timestamps[msg_id] = time.time()
        
        selected = inter.values[0]
        
        if selected == "getting_started":
            content = GETTING_STARTED_CONTENT
        elif selected == "user":
            content = build_command_content(self.bot, "user", "User Commands")
        elif selected == "admin":
            content = build_command_content(self.bot, "admin", "Admin Commands")
        else:
            content = GETTING_STARTED_CONTENT
        
        components = build_help_container(content)
        await inter.response.edit_message(components=components)


def setup(bot: commands.InteractionBot):
    bot.add_cog(HelpCommand(bot))
