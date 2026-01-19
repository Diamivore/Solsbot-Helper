from disnake.ext import commands
import disnake
import logging
from ._tortoiseORM_handler import DB
import json
from . import _models

# Commands:
# Toggle subscriptions
# Add subscribed channel
# Add/remove subscriber role

# Admin confirmation view
class ConfirmView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.value = None

    @disnake.ui.button(label="Confirm", style=disnake.ButtonStyle.green)
    async def confirm_callback(
        self, 
        button: disnake.ui.button, 
        inter: disnake.MessageInteraction
        ):
        self.value = True
        for child in self.children:
            child.disabled = True

        await inter.response.edit_message(
            "Disabled subscription messaging.",
            view=None
        )
        self.stop()

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.red)
    async def cancel_callback(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        self.value = False
        for child in self.children:
            child.disabled = True

        await inter.response.edit_message(
            "Process cancelled.",
            view=None
        )
        self.stop()


class admin(commands.Cog):
    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot
        self.logger= logging.getLogger(__name__)

    # Admin group to gatekeep (& girl boss?) non-admins from using commands
    @commands.slash_command(
        name="admin", 
        guild_only=True, 
        default_member_permissions=disnake.Permissions(administrator=True)
    )
    async def admin_group(self, inter):
        # Just a shell for the subgroup, does nothing on its own
        pass

    @admin_group.sub_command(description="Toggle whether user subscriptions will be sent to this server.")
    async def toggle_notifications( #TODO add functionality to restrict if webhook is not assigned
        self,
        inter: disnake.ApplicationCommandInteraction,
    ) -> None:
        can_post = await DB.get_guild_posting(inter.guild_id, inter.guild.name)

        if can_post:
            view = ConfirmView()
            await inter.response.send_message(
                """Are you sure you want to disable all subscriptions to this server?
Disabling will delete all user subscriptions to this guild, and they will have to re-enable them manually.""",
                view=view
            )
            await view.wait()

            if view.value == True:
                await DB.toggle_guild_posting(inter.guild_id, inter.guild.name)
        else:
            await DB.toggle_guild_posting(inter.guild_id, inter.guild.name)
            await inter.response.send_message(
                "Enabled subscription messaging"
            )

    @admin_group.sub_command(description="Tell the bot which webhook you want subscriptions posted to.")
    async def add_subscriber_webhook(
        self,
        inter: disnake.ApplicationCommandInteraction,
        webhook_url: str
    ) -> None:
        await DB.add_guild_webhook(inter.guild_id, webhook_url, inter.guild.name)
        await inter.response.send_message(
            f"Webhook: [{webhook_url}]\nAssigned successfully."
        )

    @admin_group.sub_command(description="Add role for subscription permissions.")
    async def add_notification_role(
        self,
        inter: disnake.ApplicationCommandInteraction,
        role_id: str
    ) -> None:
        if inter.guild.get_role(int(role_id)):
            await DB.add_guild_role(inter.guild_id, role_id, inter.guild.name)
            await inter.response.send_message(
                "Role assigned successfully."
                )
        else:
            await inter.response.send_message(
                "This role is not a part of this server.",
                ephemeral=True
            )

    @admin_group.sub_command(description="View server information")
    async def view_info(
        self,
        inter: disnake.ApplicationCommandInteraction
    ) -> None:
        guild_settings, _ = await _models.GuildSettings.get_or_create(guild_id=inter.guild_id, name=inter.guild.name)
        list_of_subscribers = await _models.User.filter(guilds__contains=inter.guild_id)

        embed = disnake.Embed(
            title=f"{inter.guild.name}'s Solsbot Helper Info:",
            color=disnake.Color.purple(),
            
        ).add_field(
            name="Subscriptions",
            value=("On" if guild_settings.allow_posting else "Off")
        ).add_field(
            name="Subscriber Role",
            value=(f"<@{guild_settings.can_post_role}>" if guild_settings.can_post_role else "No added role")
        ).add_field(
            name="Total Server Subscribers",
            value=f"{len(list_of_subscribers)}"
        ).add_field(
            name="Subscribed Webhook",
            value=(f"{guild_settings.post_channel_webhook}" if guild_settings.post_channel_webhook else "No webhook added")
        )

        if inter.guild and inter.guild.icon:
            embed.set_thumbnail(url=inter.guild.icon.url)

        await inter.response.send_message(
            embed=embed
        )


# Owner commands for debugging
    @commands.slash_command(description="Dev Only: Simulate API Drop.")
    @commands.is_owner()
    async def simulate_api_message(
        self,
        inter: disnake.ApplicationCommandInteraction,
        username: str,
        rare: bool = False,
        
    ) -> None:
        from datetime import datetime, timezone
        import time
        import random
        if rare:
            choice = random.randint(0,1)
            if choice == 0:
                icon_url = "https://cdn.mongoosee.com/assets/stars/Global.png"
                name = "AEGIS"
                rarity = "1 IN 825,000,000"
            else:
                icon_url = "https://cdn.mongoosee.com/assets/stars/Memory.png"
                name = "Memory, The Fallen!"
                rarity = "1 in 100 [From Oblivion Potion]"
        else:
            icon_url = "https://cdn.mongoosee.com/assets/stars/Global.png"
            name = "ARCHANGEL"
            rarity = "1 IN 250,000,000"


        fake_payload = {
        "action": "executeWebhook",
        "data": {
            "username": "Sol's Stat Tracker",
            "avatarURL": "https://cdn.mongoosee.com/assets/solsstattracker/webhook/icon_2.png",
            "embeds": [
                {
                    "author": {
                        "icon_url": f"{icon_url}",
                        "url": "https://www.roblox.com/users/468606899/profile",
                        "name": f"Diami(@{username})" 
                    },
                    "description": f"> **Diami(@{username})** HAS FOUND **{name}**, CHANCE OF **{rarity}**",
                    "fields": [
                        {
                            "name": "Rolls",
                            "value": "1,000,000",
                            "inline": True
                        },
                        {
                            "name": "Luck",
                            "value": "24",
                            "inline": True
                        },
                        {
                            "name": "Time Discovered",
                            "value": f"<t:{int(time.time())}:R>",
                            "inline": True
                        }
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "color": 5070842
                }
            ]
        }
    }
        packet = {"payload": json.dumps(fake_payload)}

        self.bot.ws_manager.queue.put_nowait(packet)
        await inter.response.send_message(
            f"Simulated drop for **{username}**."
        )
    

def setup(bot: commands.InteractionBot):
    bot.add_cog(admin(bot=bot))