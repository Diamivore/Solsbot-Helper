from disnake.ext import commands
import disnake
import disnake.ui as ui
import logging
import json

from models import GuildSettings, User
from services import GuildService

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

        embed = disnake.Embed(description="Disabled subscription messaging.")
        await inter.response.edit_message(embed=embed, view=None)
        self.stop()

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.red)
    async def cancel_callback(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        self.value = False
        for child in self.children:
            child.disabled = True

        embed = disnake.Embed(description="Process cancelled.")
        await inter.response.edit_message(embed=embed, view=None)
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
    async def toggle_notifications(
        self,
        inter: disnake.ApplicationCommandInteraction,
    ) -> None:
        can_post = await GuildService.get_posting_status(inter.guild_id, inter.guild.name)

        # Check if webhook is configured before allowing enable
        if not can_post:
            guild_settings, _ = await GuildSettings.get_or_create(guild_id=inter.guild_id, name=inter.guild.name)
            if not guild_settings.post_channel_webhook:
                embed = disnake.Embed(
                    description="Cannot enable notifications without a webhook configured.\n"
                               "Please use `/admin add_subscriber_webhook` first."
                )
                await inter.response.send_message(embed=embed, ephemeral=True)
                return

        if can_post:
            view = ConfirmView()
            embed = disnake.Embed(
                description="**Are you sure you want to disable all subscriptions to this server?**\n\n"
                           "Disabling will delete all user subscriptions to this guild, and they will have to re-enable them manually."
            )
            await inter.response.send_message(embed=embed, view=view)
            await view.wait()

            if view.value == True:
                await GuildService.toggle_posting(inter.guild_id, inter.guild.name)
        else:
            await GuildService.toggle_posting(inter.guild_id, inter.guild.name)
            embed = disnake.Embed(description="Enabled subscription messaging.")
            await inter.response.send_message(embed=embed)

    @admin_group.sub_command(description="Tell the bot which webhook you want subscriptions posted to.")
    async def add_subscriber_webhook(
        self,
        inter: disnake.ApplicationCommandInteraction,
        webhook_url: str
    ) -> None:
        await GuildService.add_webhook(inter.guild_id, webhook_url, inter.guild.name)
        embed = disnake.Embed(description="Webhook assigned successfully.")
        await inter.response.send_message(embed=embed, ephemeral=True)

    @admin_group.sub_command(description="Add role for subscription permissions.")
    async def add_notification_role(
        self,
        inter: disnake.ApplicationCommandInteraction,
        role_id: str
    ) -> None:
        if inter.guild.get_role(int(role_id)):
            await GuildService.add_role(inter.guild_id, int(role_id), inter.guild.name)
            embed = disnake.Embed(description="Role assigned successfully.")
            await inter.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = disnake.Embed(description="This role is not a part of this server.")
            await inter.response.send_message(embed=embed, ephemeral=True)

    @admin_group.sub_command(description="View server information")
    async def view_info(
        self,
        inter: disnake.ApplicationCommandInteraction
    ) -> None:
        guild_settings, _ = await GuildSettings.get_or_create(guild_id=inter.guild_id, name=inter.guild.name)
        list_of_subscribers = await User.filter(guilds__contains=inter.guild_id)

        # Build content for Components V2 display
        status_text = "On" if guild_settings.allow_posting else "Off"
        role_text = f"<@&{guild_settings.can_post_role}>" if guild_settings.can_post_role else "*No role set*"
        webhook_text = "Configured" if guild_settings.post_channel_webhook else "*Not configured*"
        
        content = (
            f"## {inter.guild.name}\n"
            f"### Server Settings\n"
            f"**Subscriptions:** {status_text}\n"
            f"**Subscriber Role:** {role_text}\n"
            f"**Total Subscribers:** {len(list_of_subscribers)}\n"
            f"**Webhook:** {webhook_text}"
        )
        
        container = ui.Container(
            ui.TextDisplay(content),
            accent_colour=None,
        )
        
        await inter.response.send_message(
            components=[container],
            flags=disnake.MessageFlags(is_components_v2=True)
        )

    # Owner commands for debugging
    @commands.slash_command(description="Dev Only: Simulate API Drop.", hidden=True)
    @commands.is_owner()
    async def simulate_api_message(
        self,
        inter: disnake.ApplicationCommandInteraction,
        username: str,
        aura: str = commands.Param(
            choices=[
                "ARCHANGEL",
                "AEGIS", "Memory, The Fallen!", "Frozen Sovereign", "Luminosity"
            ],
            description="Select the aura type to simulate"
        ),
    ) -> None:
        from datetime import datetime, timezone
        import time
        
        # Test aura presets
        test_auras = {
            # Normal format (rarity in description)
            "ARCHANGEL": {
                "icon_url": "https://cdn.mongoosee.com/assets/stars/Global.png",
                "is_rare": False,
                "rarity": "1 IN 250,000,000",
            },
            "AEGIS": {
                "icon_url": "https://cdn.mongoosee.com/assets/stars/Global.png",
                "is_rare": False,
                "rarity": "1 IN 825,000,000",
            },
            # Rare format (separate Rarity field)
            "Memory, The Fallen!": {
                "icon_url": "https://cdn.mongoosee.com/assets/stars/Memory.png",
                "is_rare": True,
                "rarity": "1 in 100 [From Oblivion Potion]",
            },
            "Frozen Sovereign": {
                "icon_url": "https://cdn.mongoosee.com/assets/stars/Global.png",
                "is_rare": True,
                "rarity": "1 in 1,000,000,000",
            },
            "Luminosity": {
                "icon_url": "https://cdn.mongoosee.com/assets/stars/Global.png",
                "is_rare": True,
                "rarity": "1 in 1,200,000,000",
            },
        }
        
        aura_data = test_auras.get(aura)
        if not aura_data:
            await inter.response.send_message("Invalid aura selection.", ephemeral=True)
            return
        
        icon_url = aura_data["icon_url"]
        is_rare = aura_data["is_rare"]
        rarity = aura_data["rarity"]
        
        # Build the embed based on format
        if is_rare:
            # Rare format: different description, separate Rarity field
            description = f"> **Diami(@{username})** has found **[{aura}]**"
            fields = [
                {"name": "Rarity", "value": rarity, "inline": True},
                {"name": "Rolls", "value": "1,000,000", "inline": True},
                {"name": "Luck", "value": "24", "inline": True},
                {"name": "Time Discovered", "value": f"<t:{int(time.time())}:R>", "inline": True},
            ]
        else:
            # Normal format: rarity in description
            description = f"> **Diami(@{username})** HAS FOUND **{aura}**, CHANCE OF **{rarity}**"
            fields = [
                {"name": "Rolls", "value": "1,000,000", "inline": True},
                {"name": "Luck", "value": "24", "inline": True},
                {"name": "Time Discovered", "value": f"<t:{int(time.time())}:R>", "inline": True},
            ]

        fake_payload = {
            "action": "executeWebhook",
            "data": {
                "username": "Sol's Stat Tracker",
                "avatarURL": "https://cdn.mongoosee.com/assets/solsstattracker/webhook/icon_2.png",
                "embeds": [
                    {
                        "author": {
                            "icon_url": icon_url,
                            "url": "https://www.roblox.com/users/468606899/profile",
                            "name": f"Diami(@{username})"
                        },
                        "description": description,
                        "fields": fields,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "color": 5070842
                    }
                ]
            }
        }
        packet = {"payload": json.dumps(fake_payload)}

        self.bot.ws_manager.queue.put_nowait(packet)
        embed = disnake.Embed(description=f"Simulated **{aura}** drop for **{username}**.")
        await inter.response.send_message(embed=embed, ephemeral=True)


def setup(bot: commands.InteractionBot):
    bot.add_cog(admin(bot=bot))