import discord
from discord.ext import commands, tasks
import json
import os
import re
from dotenv import load_dotenv
from datetime import datetime, timezone
from supabase import create_client

# --- Load environment ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")
TOKEN = os.getenv("DISCORD_TOKEN")

# --- Constants ---
FORUM_CHANNEL_ID = 1352870773588623404
TARGET_USER_ID = 1279417773013078098
PROCESSED_FILE = "processed_threads.json"

# --- Supabase client ---
supabase = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

# --- Helpers ---
def load_processed_threads():
    if not os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return set()
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return set(json.load(f))

def save_processed_threads(threads_set):
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(threads_set), f, indent=4)

async def increment_supabase_count(attribute: str):
    # Get current value
    res = supabase.from_("miscinfo").select("count").eq("attribute", attribute).execute()
    data = res.data
    if data:
        new_value = data[0]["count"] + 1
        supabase.from_("miscinfo").update({"count": new_value}).eq("attribute", attribute).execute()
    else:
        supabase.from_("miscinfo").insert({"attribute": attribute, "count": 1}).execute()


# --- Cog ---
class DetectSlop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.processed_threads = load_processed_threads()
        self.auto_scan.start()

    def cog_unload(self):
        self.auto_scan.cancel()

    # --- Auto-scan task ---
    @tasks.loop(minutes=5)
    async def auto_scan(self):
        """Automatically scan new threads/messages after Nov 9th, 2025."""
        forum_channel = self.bot.get_channel(FORUM_CHANNEL_ID)
        if not forum_channel:
            return

        after_date = datetime(2025, 11, 9, tzinfo=timezone.utc)

        # Scan active threads
        threads = forum_channel.threads
        # Scan archived threads
        archived = await forum_channel.archived_threads(limit=None)
        threads += archived.threads

        for thread in threads:
            if thread.id in self.processed_threads:
                continue
            async for message in thread.history(limit=None, after=after_date):
                if not message.webhook_id:
                    continue
                if not ("rejected" in message.content.lower() or "accepted" in message.content.lower()):
                    continue
                # Ignore if first word mentions Sergeant
                if re.match(rf"^<@!?{TARGET_USER_ID}>", message.content.strip()):
                    continue

                mentions_sergeant = any(u.id == TARGET_USER_ID for u in message.mentions)
                if mentions_sergeant:
                    if "rejected" in message.content.lower():
                        await increment_supabase_count("count 2")
                    elif "accepted" in message.content.lower():
                        await increment_supabase_count("count")
                    self.processed_threads.add(thread.id)
                    save_processed_threads(self.processed_threads)
                    break  # stop after first keyword per thread

    @auto_scan.before_loop
    async def before_auto_scan(self):
        await self.bot.wait_until_ready()

    # --- Slash command: alltime_s ---
    @commands.hybrid_command(name="alltime_s", description="Scan all forum posts for accepted/rejected counts")
    async def alltime_s(self, ctx):
        if ctx.author.id != TARGET_USER_ID:
            await ctx.send("❌ You are not allowed to use this command.", ephemeral=True)
            return

        forum_channel = self.bot.get_channel(FORUM_CHANNEL_ID)
        if not forum_channel:
            await ctx.send("❌ Forum channel not found.", ephemeral=True)
            return

        rejected_count = 0
        accepted_count = 0

        # Active + archived threads
        threads = forum_channel.threads
        archived = await forum_channel.archived_threads(limit=None)
        threads += archived.threads

        for thread in threads:
            if thread.id in self.processed_threads:
                continue
            async for message in thread.history(limit=None):
                if not message.webhook_id:
                    continue
                content_lower = message.content.lower()
                if not ("rejected" in content_lower or "accepted" in content_lower):
                    continue
                # Ignore if first word mentions Sergeant
                if re.match(rf"^<@!?{TARGET_USER_ID}>", message.content.strip()):
                    continue
                mentions_sergeant = any(u.id == TARGET_USER_ID for u in message.mentions)
                if mentions_sergeant:
                    if "rejected" in content_lower:
                        rejected_count += 1
                    elif "accepted" in content_lower:
                        accepted_count += 1
                    self.processed_threads.add(thread.id)
                    save_processed_threads(self.processed_threads)
                    break  # stop after first keyword per thread

        await ctx.send(f"✅ Rejected: {rejected_count}\n✅ Accepted: {accepted_count}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(DetectSlop(bot))
