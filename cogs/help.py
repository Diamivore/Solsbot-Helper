import disnake
from disnake.ext import commands

# Views
class HelpDropdown(disnake.ui.Select):
    def __init__(self, bot: commands.InteractionBot, mapping: dict):
        self.bot = bot
        self.mapping = mapping

        options = []
        for cog_name, cmd_list, in mapping.items():
            if not cmd_list: continue

            description = (self.bot.get_cog(cog_name).description or "No description provided.")[:100]
            options.append(disnake.SelectOption(
                label=cog_name,
                description=description
            ))

        super().__init__(
            placeholder="Select a category for which you need help...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, inter: disnake.MessageInteraction):
        selected_cog = self.values[0]
        cmd_list = self.mapping.get(selected_cog)

        embed = disnake.Embed(
            title=f"{selected_cog} Commands",
            color=disnake.Color.purple()
        )

        for cmd in cmd_list:
            desc = cmd.description or "No description."

            embed.add_field(
                name=f"/{cmd.name}",
                value=desc,
                inline=False
            )

        await inter.response.edit_message(embed=embed, view=self)


class HelpView(disnake.ui.View):
    def __init__(self, bot, mapping):
        super().__init__(timeout=180)
        self.add_item(HelpDropdown(bot, mapping))


# Main help command
class HelpCommand(commands.Cog):
    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot

    @commands.slash_command(description="Show all available commands")
    async def help(self, inter: disnake.ApplicationCommandInteraction):
        mapping ={}

        for cog_name, cog in self.bot.cogs.items():
            commands_list = cog.get_slash_commands()

            if cog_name == "ErrorHandler":
                continue

            if commands_list:
                mapping[cog_name] = commands_list

        embed = disnake.Embed(
            title="## How to use this bot",
            description=("The Solsbot Helper keeps your friends updated on your recent finds!\n\n"
                        "## **Users**\n"
                        "### To start:\n"
                        "- Use `/add_username [Roblox Username]` to add the account you want to get notifications from\n"
                        "- Use `/add_server [Server ID (or options menu)]` to add the servers you want those notifications to be sent to\n"
                        "### Misc:\n"
                        "- Use `/view_usernames` to see all registered usernames\n"
                        "- Use `/view_servers` to see all registered servers\n\n"
                        "## **Admins**\n"
                        "To get your server started:\n"
                        "- Use `/admin add_subscriber_webhook [Webhook URL]` to add the webhook you wish notifications to be posted to\n"
                        "- Use `/admin toggle_notifications` to allow messages to be posted to your webhook\n"
                        "- Optionally, use `/admin add_notification_role [Role ID]` to add a role a user is required to have to post to your server\n"
                        "### Misc:\n"
                        "- Use `/admin view_info` to see your current server settings\n\n\n"
                        "Use the dropdown menu below to see all other commands"

            ),
            color=1e1637
        )

        await inter.response.send_message(
            embed=embed, 
            view=HelpView(self.bot, mapping), 
            ephemeral=True
            )
        

def setup(bot: commands.InteractionBot):
    bot.add_cog(HelpCommand(bot))
