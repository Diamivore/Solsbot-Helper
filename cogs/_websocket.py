import websockets
import asyncio
import json
from disnake.ext import commands
from discord_webhook import AsyncDiscordWebhook, DiscordEmbed
import hashlib
import logging
import aiohttp
import sys

from ._tortoiseORM_handler import DB
from . import _models

# Custom errors
class WORKERRUNNING(Exception):
    pass
class WORKERNOTDEFINED(Exception):
    pass


class WebSocketClient:
    def __init__(self, bot):
        self.uri = "wss://api.mongoosee.com/solsstattracker/v2/gateway"
        self.queue = asyncio.Queue()
        self.logger = logging.getLogger(__name__)
        self.bot = bot

    async def websocket_worker(self, api_key: str, ready_event: asyncio.Event):
        while True:
            try:
                self.logger.info("Connecting websocket worker...")
                async with websockets.connect(
                    self.uri,
                    additional_headers={"token": f"{api_key}"}
                    ) as websocket:
                    async for message in websocket:
                        # Wait for websocket to connect before setting asyncio event
                        if message:
                            ready_event.set()

                        self.logger.debug(f"Worker catch: Raw JSON ⬇\n\n{message}\n\n")

                        packet = {
                            "payload": message,
                        }

                        # Detatch the information from the worker and add it to the queue
                        # This allows for the worker to immediately continue listening
                        self.queue.put_nowait(packet)

            except asyncio.CancelledError:
                self.logger.info("Disconnecting from API Key...")
                raise
            except websockets.exceptions.ConnectionClosedError as e:
                # Codes 4001-4004, code meaning and handling defined in
                # https://github.com/mongoo-se/sols-stat-tracker-webhook/blob/main/index.js
                if e.code == 4002: 
                    self.logger.error("That API Key is invalid")
                    sys.exit(f"API Key is invalid: [{api_key}]")
                elif e.code == 4003:
                    self.logger.error("That API Key is already in use")
                    sys.exit(f"API Key already in use: [{api_key}]")
                else:
                    raise
            except Exception as e:
                self.logger.error(f"API Error [{api_key}]: {e}")
                self.logger.debug("Reconnecting in 5s...")
                await asyncio.sleep(5)


    # Some helper functions
    async def check_user_permission(
        self, 
        guild_id: int, 
        user_id: int, 
        required_role_id: int
        ) -> bool:
        if not required_role_id:
            return True
        
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False
        
        member = await guild.fetch_member(user_id)
        if not member:
            return False
        
        return any(role.id == int(required_role_id) for role in member.roles)

    def parse_payload(self, payload: str) -> list:
        payload = json.loads(payload)
        embeds = payload["data"]["embeds"]

        found_embeds = []
        for embed in embeds:
            current_embed = {}
            name: str = embed["author"]["name"]
            if ")" in name:
                name = name.split("(")[1].replace(")", "")
            name = name.replace("@", "")
            if name.lower() not in self.bot.usernames:
                continue


            current_embed["icon_url"] = embed["author"]["icon_url"]
            current_embed["url"] = embed["author"]["url"]
            current_embed["full_name"] = embed["author"]["name"]
            current_embed["name"] = name

            current_embed["description"] = embed["description"]

            try:
                current_embed["aura"] = embed["description"].split("**")[3]
                current_embed["rarity"] = embed["description"].split("**")[5][5:]
            except IndexError:
                self.logger.error(f"Failed to parse aura/rarity from description: {embed['description']}")
                continue

            current_embed["rolls"] = embed["fields"][0]["value"]
            current_embed["luck"] = embed["fields"][1]["value"]
            current_embed["time"] = embed["fields"][2]["value"]

            current_embed["timestamp"] = embed["timestamp"]
            current_embed["color"] = embed["color"]

            found_embeds.append(current_embed)

        if not found_embeds:
            self.logger.debug("No matching usernames found during parsing")

        return found_embeds


    # Main queue processor pipeline
    async def queue_processor(self):
        while True:
            # Grab packet from queue and process if data is available
            packet = await self.queue.get()
            if not packet:
                continue

            data = packet['payload']
            embeds = self.parse_payload(data)

            # See if any players in the embeds are registered
            if not embeds:
                continue

            
            self.bot: commands.Bot

            # Process each embed
            for embed in embeds:
                try:
                    self.logger.debug(f"Sending Notifications for Roblox user. Description: [{embed["description"]}]..")
                    webhooks, user_id = await DB.get_user_destinations(embed["name"])
                    user = self.bot.get_user(user_id)

                    # Check user for role permissions
                    webhook_buffer = []
                    for url, guild_id, required_role_id in webhooks:
                        if not await self.check_user_permission(guild_id, user_id, required_role_id):
                            continue

                        webhook_buffer.append(url)

                    if not webhook_buffer:
                        continue

                    if user:
                        discord_avatar_url = user.display_avatar.url
                    else:
                        discord_avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"


                    data = DiscordEmbed(
                        description=f"\n**User**\n<@{user.id}>\n\n{embed["description"]}", 
                        color=embed["color"]
                        )
                    data.set_author(
                        name=embed["full_name"], 
                        url=embed["url"], 
                        icon_url=embed["icon_url"]
                        )
                    data.set_timestamp(embed["timestamp"])
                    data.add_embed_field(name="Rolls", value=embed["rolls"])
                    data.add_embed_field(name="Luck", value=embed["luck"])
                    data.add_embed_field(name="Time Discovered", value=embed["time"])
                    data.set_footer(
                        text=f"Found by: {user.name if user else "N/A"}",
                        icon_url=f"{discord_avatar_url}"
                        )

                    # Send message on exceptional finds
                    try:
                        try_rarity = int(embed["rarity"].replace(",", ""))
                    except ValueError:
                        try_rarity = 0

                    if  try_rarity >= 750000000 or embed["icon_url"] != "https://cdn.mongoosee.com/assets/stars/Global.png":
                        content = "Good find!"
                    else:
                        content= None


                    ready_webhooks = AsyncDiscordWebhook.create_batch(
                        webhook_buffer,
                        embeds=[data],
                        content=content,
                        avatar_url=f"{self.bot.user.display_avatar.url}",
                        username="Solsbot Helper"
                        )
                    for webhook in ready_webhooks:
                        await webhook.execute()


                    self.queue.task_done()
                    self.logger.debug(f"Queue caught! Embed data ⬇\n\n{embed}\n\n")

                except Exception as e:
                    self.logger.error(f"Queue processor [ERROR]: {e}")
                    await asyncio.sleep(5)

            