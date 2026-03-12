import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load env
load_dotenv()
AUTHORIZED_USER_ID = 1279417773013078098  # Sergeant
FORUM_CHANNEL_ID = 1352870773588623404
PROCESSED_JSON = "processed_threads.json"

class ForumScanner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Ensure processed JSON exists
        if not os.path.exists(PROCESSED_JSON):
            with open(PROCESSED_JSON, "w", encoding="utf-8") as f:
                json.dump({"threads": []}, f, indent=4)

        # Load processed threads (be robust to either dict or list stored)
        with open(PROCESSED_JSON, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if isinstance(raw, dict):
                threads = raw.get("threads", [])
            elif isinstance(raw, list):
                threads = raw
            else:
                threads = []
            self.processed_threads = set(threads)

        # Don't start the background task here; start it when the cog is fully loaded
        # to ensure bot.guilds and channels are available.

    async def cog_load(self):
        # start the auto-scan task when the cog is loaded
        try:
            self.auto_scan_task.start()
        except RuntimeError:
            # task already running or bot not ready; ignore
            pass

    def save_processed(self):
        with open(PROCESSED_JSON, "w", encoding="utf-8") as f:
            json.dump({"threads": list(self.processed_threads)}, f, indent=4)

    async def process_message(self, message, update_counts: dict):
        """
        Process a single message for 'rejected' or 'accepted'.
        Returns True if a keyword was found (to prevent double-counting).
        """
        if message.id in self.processed_threads:
            return False

        content = message.content.lower()

        # Skip if first word pings Sergeant
        if content.startswith(f"<@{AUTHORIZED_USER_ID}>") or (message.mentions and message.mentions[0].id == AUTHORIZED_USER_ID):
            return False

        # Rejected
        if "rejected" in content:
            update_counts["rejected"] += 1
            self.processed_threads.add(message.id)
            return True

        # Accepted
        if "accepted" in content and (f"<@{AUTHORIZED_USER_ID}>" in content or AUTHORIZED_USER_ID in [u.id for u in message.mentions]):
            update_counts["accepted"] += 1
            self.processed_threads.add(message.id)
            return True

        return False

    async def scan_thread(self, thread, update_counts: dict):
        """Scan all messages in a thread until first keyword found."""
        try:
            async for message in thread.history(limit=None, oldest_first=True):
                found = await self.process_message(message, update_counts)
                if found:
                    break  # Stop after first keyword in this thread
        except discord.Forbidden:
            print(f"❌ Missing permissions to read thread {thread.id}")

    async def scan_forum(self, after_datetime: datetime = None, update_counts: dict = None):
        """Scan all threads in the forum channel."""
        if update_counts is None:
            update_counts = {"rejected": 0, "accepted": 0}

        # Ensure after_datetime is timezone-aware (thread.created_at is timezone-aware).
        if after_datetime is not None and after_datetime.tzinfo is None:
            after_datetime = after_datetime.replace(tzinfo=timezone.utc)

        guild = self.bot.get_guild(self.bot.guilds[0].id)  # use first guild
        forum_channel = guild.get_channel(FORUM_CHANNEL_ID)
        if forum_channel is None:
            print("❌ Forum channel not found")
            return update_counts

        # --- Active threads ---
        for thread in forum_channel.threads:
            if after_datetime and thread.created_at < after_datetime:
                continue
            await self.scan_thread(thread, update_counts)

        # --- Archived threads ---
        # archived_threads is an async iterator; iterate directly
        async for thread in forum_channel.archived_threads(limit=None):
            if after_datetime and thread.created_at < after_datetime:
                continue
            await self.scan_thread(thread, update_counts)

        # Save processed
        self.save_processed()
        return update_counts

    @tasks.loop(minutes=10)
    async def auto_scan_task(self):
        """Automatically scan new threads/messages every 10 minutes."""
        update_counts = {"rejected": 0, "accepted": 0}
        # pass an explicit UTC-aware datetime to avoid naive/aware comparison errors
        await self.scan_forum(after_datetime=datetime(2025, 11, 9, tzinfo=timezone.utc), update_counts=update_counts)
        # Here you could add code to update Supabase with counts
        print(f"Auto scan counts (since 2025-11-09): {update_counts}")

    # Use a classic text command to avoid app command registration issues on load.
    @commands.command(name="alltime_s")
    async def alltime_s(self, ctx: commands.Context):
        if ctx.author.id != AUTHORIZED_USER_ID:
            await ctx.reply("❌ You are not allowed to use this command.", mention_author=False)
            return

        update_counts = {"rejected": 0, "accepted": 0}
        await self.scan_forum(after_datetime=None, update_counts=update_counts)
        await ctx.reply(f"📊 All-time counts:\nRejected: {update_counts['rejected']}\nAccepted: {update_counts['accepted']}", mention_author=False)


async def setup(bot):
    await bot.add_cog(ForumScanner(bot))
