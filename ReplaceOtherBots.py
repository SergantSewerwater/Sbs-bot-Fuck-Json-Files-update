import discord
from discord.ext import commands
import logging
import asyncio
import time
from collections import defaultdict
from typing import Set, Dict, Optional, List

# Logger for this module
logger = logging.getLogger("sbsbot.ReplaceOtherBots")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

TARGET_CHANNEL_ID = 899784386038333555
IGNORED_ROLE_ID = 1429783971654406195
SUBMIT_CHANNEL_ID = 1352915632936718386

# dict of auto responses
autoresponses = {
    "espanol": "Este chat es solo en inglés.",
    "español": "Este chat es solo en inglés.",
    "spanish": "Este chat es solo en inglés.",
    "russian": "Этот чат только для англоговорящих",
    "русский": "Этот чат только для англоговорящих",
    "showcase": "Don't understand how the \"showcase\" field in <#1352915632936718386> works? Put a YouTube link into the \"showcase\" field to use the thumbnail for your submission\nMake sure that thumbnail isn't already used on the site",
    "geode": "Version 2.208 of Geometry Dash broke Geode. Once the developers update Geode, it will work again.",
    "jukebox": "Jukebox doesn't work because it relies on Geode, which was broken by version 2.208 of Geometry Dash. Once Geode and Jukebox are updated, it will work again.", # \nWant a tutorial on how to use Jukebox? You can find one [here](https://youtu.be/qfTO4nBLsbk?si=YGlr4J3DuRbYHcZ9)\nHaving problems with Jukebox? Read <#1201831020890951680> and <#1308752971743629363>\nIf you still have issues, report them in <#1302962232015192115>",
    "upload": "Wanna submit your own song(s)? Read the pinned post in <#1352870773588623404>",
    "submit": "Wanna submit your own song(s)? Read the pinned post in <#1352870773588623404>",
    "file": "Looking for certain songs? You can find them on Jukebox or our website\nhttps://www.songfilehub.com/",
    "song": "Looking for certain songs? You can find them on Jukebox or our website\nhttps://www.songfilehub.com/",
    "nong": "Looking for certain songs? You can find them on Jukebox or our website\nhttps://www.songfilehub.com/",
    "ai proof": "The \"AI Proof\" role stops our bot from auto-responding to your messages\nYou get this role after reaching level 2",
    "where": "Have questions? Read <#1201831020890951680> and the pinned post in <#1352870773588623404>\nOtherwise, go to <#1302962232015192115>",
    "why": "Have questions? Read <#1201831020890951680> and the pinned post in <#1352870773588623404>\nOtherwise, go to <#1302962232015192115>",
    "how": "Have questions? Read <#1201831020890951680> and the pinned post in <#1352870773588623404>\nOtherwise, go to <#1302962232015192115>",
    "?": "Have questions? Read <#1201831020890951680> and the pinned post in <#1352870773588623404>\nOtherwise, go to <#1302962232015192115>",
}

class ReplaceOtherBots(commands.Cog):
    """Consolidated cog that handles autoresponses, submit-channel deletions and sticky messages."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logger

        # Queue for batching submit-channel deletes to use bulk delete
        self._submit_delete_queue: asyncio.Queue = asyncio.Queue()
        # Task processing the queue
        self._submit_deleter_task: Optional[asyncio.Task] = asyncio.create_task(self._submit_deleter_loop())

        # Sticky state per channel: stores last message id and last post timestamp
        self._sticky_state: Dict[int, Dict[str, Optional[float]]] = defaultdict(lambda: {"last_msg_id": None, "last_post": 0.0})
        self._sticky_cooldown = 3.0  # seconds between sticky reposts

        # Autoresponse cooldowns: (channel_id, user_id, keyword) -> last_response_ts
        self._autoresponse_cooldowns: Dict[tuple, float] = {}
        self._autoresponse_cooldown_seconds = 30.0

    async def cog_unload(self):
        # Cancel background task on cog unload
        if self._submit_deleter_task:
            self._submit_deleter_task.cancel()
            try:
                await self._submit_deleter_task
            except asyncio.CancelledError:
                self.logger.info("Submit deleter task cancelled successfully")
            except Exception:
                self.logger.exception("Error waiting for submit deleter task to finish")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots early
        if message.author.bot:
            return

        try:
            # --- Delete stuff in #submit-here (enqueue for batch deletion)
            if message.channel.id == SUBMIT_CHANNEL_ID:
                if message.author.id != 1272790489380421643:
                    # enqueue message for batch deletion
                    try:
                        await self._submit_delete_queue.put(message)
                        self.logger.debug("Queued submit-channel message %s for deletion", message.id)
                    except Exception:
                        self.logger.exception("Failed to enqueue submit-channel message %s", message.id)
                    return

            # --- Auto responses in the target channel (with cooldowns)
            if message.channel.id == TARGET_CHANNEL_ID:
                if isinstance(message.author, discord.Member) and any(role.id == IGNORED_ROLE_ID for role in message.author.roles):
                    self.logger.debug("Skipping autoresponse because user has ignored role: %s", message.author)
                else:
                    content = message.content.lower()
                    now = time.time()
                    for keyword, response in autoresponses.items():
                        if keyword in content:
                            key = (message.channel.id, message.author.id, keyword)
                            last = self._autoresponse_cooldowns.get(key, 0.0)
                            if now - last < self._autoresponse_cooldown_seconds:
                                self.logger.debug("Skipping autoresponse to %s for '%s' due to cooldown", message.author, keyword)
                                continue
                            self._autoresponse_cooldowns[key] = now
                            self.logger.info("Autoresponding to %s for keyword '%s'", message.author, keyword)
                            try:
                                await message.channel.send(f"{response}\n{message.author.mention}")
                            except discord.HTTPException:
                                self.logger.exception("Failed to send autoresponse to %s", message.author)
                            return

            # --- Sticky message behavior (debounced, delete by id if possible)
            if STICKY_CONTENT and message.channel.id in STICKY_CHANNELS:
                if message.author != self.bot.user:
                    state = self._sticky_state[message.channel.id]
                    now = time.time()
                    last_post = state.get("last_post") or 0.0
                    if now - last_post < self._sticky_cooldown:
                        self.logger.debug("Sticky cooldown active for channel %s", message.channel.id)
                    else:
                        # Try to delete previous sticky by id
                        last_msg_id = state.get("last_msg_id")
                        deleted = False
                        if last_msg_id is not None:
                            try:
                                msg = await message.channel.fetch_message(int(last_msg_id))
                                if msg and msg.author == self.bot.user:
                                    await msg.delete()
                                    deleted = True
                                    self.logger.debug("Deleted previous sticky message %s in channel %s", last_msg_id, message.channel.id)
                            except discord.NotFound:
                                self.logger.debug("Previous sticky message %s not found", last_msg_id)
                            except Exception:
                                self.logger.exception("Failed to delete sticky message %s", last_msg_id)

                        # If no last_msg_id or deletion failed, try a small history scan but limit work
                        if not deleted and last_msg_id is None:
                            try:
                                async for msg in message.channel.history(limit=20):
                                    if msg.author == self.bot.user and msg.content == STICKY_CONTENT:
                                        try:
                                            await msg.delete()
                                            self.logger.debug("Deleted previous sticky message %s found by scan in channel %s", msg.id, message.channel.id)
                                            deleted = True
                                            break
                                        except Exception:
                                            self.logger.exception("Failed to delete old sticky message found by scan %s", msg.id)
                            except Exception:
                                self.logger.exception("Failed scanning history for sticky message in channel %s", message.channel.id)

                        # Post new sticky and record id/time
                        try:
                            sent = await message.channel.send(STICKY_CONTENT)
                            state["last_msg_id"] = int(getattr(sent, "id", 0)) if getattr(sent, "id", None) is not None else None
                            state["last_post"] = now
                            self.logger.info("Posted sticky message %s in channel %s", state["last_msg_id"], message.channel.id)
                        except discord.HTTPException:
                            self.logger.exception("Failed to post sticky message in channel %s", message.channel.id)

        except Exception:
            self.logger.exception("Uncaught exception in ReplaceOtherBots.on_message")
        finally:
            # Ensure commands still work when on_message is present
            await self.bot.process_commands(message)

    async def _submit_deleter_loop(self):
        """Background task that batches deletions from the submit channel to use bulk delete and avoid rate limits."""
        try:
            while True:
                batch: List[discord.Message] = []
                try:
                    # Wait up to 2 seconds for at least one message
                    msg = await asyncio.wait_for(self._submit_delete_queue.get(), timeout=2.0)
                    batch.append(msg)
                except asyncio.TimeoutError:
                    # no message in queue this interval
                    pass

                # Drain queue quickly for up to a short burst window
                start = time.time()
                while len(batch) < 100 and (time.time() - start) < 1.0:
                    try:
                        msg = self._submit_delete_queue.get_nowait()
                        batch.append(msg)
                    except asyncio.QueueEmpty:
                        break

                if not batch:
                    await asyncio.sleep(0.1)
                    continue

                # Group by channel for bulk deletes
                by_channel: Dict[int, List[discord.Message]] = defaultdict(list)
                for m in batch:
                    by_channel[m.channel.id].append(m)

                for chan_id, msgs in by_channel.items():
                    channel = msgs[0].channel
                    # Attempt bulk delete for messages younger than 14 days on a TextChannel
                    if isinstance(channel, discord.TextChannel):
                        try:
                            # delete_messages expects a list of message objects and will use bulk delete where possible
                            await channel.delete_messages(msgs)
                            self.logger.info("Bulk deleted %s messages in channel %s", len(msgs), chan_id)
                        except Exception:
                            # Fall back to individual deletes if bulk delete fails
                            self.logger.exception("Bulk delete failed for channel %s, falling back to single deletes", chan_id)
                            for m in msgs:
                                try:
                                    await m.delete()
                                    await asyncio.sleep(0.2)  # small pause to avoid hitting rate limits
                                except Exception:
                                    self.logger.exception("Failed to delete message %s individually", getattr(m, 'id', None))
                    else:
                        # Not a text channel (e.g., DM); delete individually
                        for m in msgs:
                            try:
                                await m.delete()
                                await asyncio.sleep(0.2)
                            except Exception:
                                self.logger.exception("Failed to delete message %s in non-text channel", getattr(m, 'id', None))

                # Sleep a short time between batches to reduce rate of requests
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            self.logger.info("Submit deleter background task cancelled")
        except Exception:
            self.logger.exception("Submit deleter encountered an error and stopped")

# --- StickyBot
STICKY_CHANNELS = {
 1453008993692942436
}

STICKY_CONTENT = ""


# --- Member Count ---
MEMBER_COUNT_CHANNEL_ID = 1453041413989072958

class MemberCount(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logger
        self._started = False

    async def update_member_count(self, guild: discord.Guild):
        member_count = max((guild.member_count or 0) - 5, 0)
        self.logger.info("Updating member count for guild %s: calculated %s", guild.id, member_count)

        channel = guild.get_channel(MEMBER_COUNT_CHANNEL_ID)
        if channel is None:
            self.logger.warning("Member count channel %s not found in guild %s", MEMBER_COUNT_CHANNEL_ID, guild.id)
            return

        # Update the channel name to reflect the current member count. This requires Manage Channels permission.
        new_name = f"Members: {member_count}"
        try:
            await channel.edit(name=new_name)
            self.logger.info("Updated member count channel %s name to '%s'", channel.id, new_name)
        except discord.Forbidden:
            self.logger.error("Missing permissions to edit channel %s in guild %s", channel.id, guild.id)
        except Exception:
            self.logger.exception("Failed to edit member count channel %s in guild %s", channel.id, guild.id)

    @commands.command(name="refresh_members")
    @commands.has_permissions(manage_guild=True)
    async def refresh_members(self, ctx: commands.Context):
        """Manually refresh the member count channel name for this guild."""
        if ctx.guild is None:
            await ctx.send("This command can only be used in a server/guild.")
            return
        await self.update_member_count(ctx.guild)
        await ctx.send("Member count refreshed.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        self.logger.debug("on_member_join: %s in guild %s", member, member.guild.id)
        await self.update_member_count(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        self.logger.debug("on_member_remove: %s in guild %s", member, member.guild.id)
        await self.update_member_count(member.guild)

    @commands.Cog.listener()
    async def on_ready(self):
        # Run once on ready to ensure the channel is correct
        if self._started:
            return
        self._started = True
        self.logger.info("MemberCount cog running startup refresh for %s guilds", len(self.bot.guilds))
        for g in self.bot.guilds:
            try:
                await self.update_member_count(g)
            except Exception:
                self.logger.exception("Error updating member count for guild %s on startup", g.id)




async def setup(bot: commands.Bot):
    logger.info("Registering ReplaceOtherBots and MemberCount cogs")
    await bot.add_cog(ReplaceOtherBots(bot))
    await bot.add_cog(MemberCount(bot))
