import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import re
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timezone

# --- Load environment ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    raise ValueError("Missing Supabase credentials.")

supabase = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

# --- Constants ---
FORUM_CHANNEL_ID = 1352870773588623404
TARGET_USER_ID = 1279417773013078098  # @Sergeant

# --- Data folder setup ---
DATA_FOLDER = "data"
os.makedirs(DATA_FOLDER, exist_ok=True)
PROCESSED_THREADS_FILE = os.path.join(DATA_FOLDER, "processed_threads.json")


def load_processed_threads():
    """Load already-processed thread IDs from JSON."""
    if os.path.exists(PROCESSED_THREADS_FILE):
        try:
            with open(PROCESSED_THREADS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except json.JSONDecodeError:
            return set()
    # If file doesn't exist, create it as an empty list
    with open(PROCESSED_THREADS_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)
    return set()


def save_processed_threads(processed_threads):
    """Save processed thread IDs to JSON."""
    with open(PROCESSED_THREADS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(processed_threads), f, indent=2)


class ForumAutoScan(commands.Cog):
    """Auto-scans forum posts for accepted/rejected webhook messages."""

    def __init__(self, bot):
        self.bot = bot
        self.processed_threads = load_processed_threads()
        self.forum_scan_loop.start()

    def cog_unload(self):
        self.forum_scan_loop.cancel()

    async def scan_thread_messages(self, thread, ignore_date=False, supabase_update=True):
        """Scan a single thread for webhook messages containing 'accepted' or 'rejected'."""
        if thread.id in self.processed_threads:
            return 0  # Already processed

        after_date = None if ignore_date else datetime(2025, 11, 9, tzinfo=timezone.utc)

        async for message in thread.history(limit=None, after=after_date):
            if message.webhook_id is None:
                continue  # Only consider webhook messages

            content_lower = message.content.lower()

            if "rejected" in content_lower or "accepted" in content_lower:
                mentions_sergeant = any(u.id == TARGET_USER_ID for u in message.mentions)
                starts_with_sergeant = re.match(
                    r"^<@!?1279417773013078098>", message.content.strip()
                )

                if mentions_sergeant and not starts_with_sergeant:
                    if supabase_update:
                        if "rejected" in content_lower:
                            res = supabase.from_("miscinfo").select("count2").eq("id", 2).execute()
                            current_value = res.data[0]["count2"] if res.data else 0
                            new_value = current_value + 1
                            supabase.from_("miscinfo").update({"count2": new_value}).eq("id", 2).execute()
                            print(f"📉 Rejected: Updated count2 → {new_value}")

                        elif "accepted" in content_lower:
                            res = supabase.from_("miscinfo").select("count").eq("id", 2).execute()
                            current_value = res.data[0]["count"] if res.data else 0
                            new_value = current_value + 1
                            supabase.from_("miscinfo").update({"count": new_value}).eq("id", 2).execute()
                            print(f"📈 Accepted: Updated count → {new_value}")

                    # Mark thread as processed after first keyword
                    self.processed_threads.add(thread.id)
                    save_processed_threads(self.processed_threads)
                    break  # Stop after first keyword per thread

        return 1

    async def scan_forum_messages(self, ignore_date=False, supabase_update=True):
        """Scan all threads in the forum channel."""
        forum_channel = self.bot.get_channel(FORUM_CHANNEL_ID)
        if not forum_channel:
            print("❌ Forum channel not found.")
            return

        threads_to_check = forum_channel.threads
        rejected_count = 0
        accepted_count = 0

        for thread in threads_to_check:
            after_date = None if ignore_date else datetime(2025, 11, 9, tzinfo=timezone.utc)
            async for message in thread.history(limit=None, after=after_date):
                if message.webhook_id is None:
                    continue

                content_lower = message.content.lower()
                if "rejected" in content_lower or "accepted" in content_lower:
                    mentions_sergeant = any(u.id == TARGET_USER_ID for u in message.mentions)
                    starts_with_sergeant = re.match(
                        r"^<@!?1279417773013078098>", message.content.strip()
                    )
                    if mentions_sergeant and not starts_with_sergeant:
                        if "rejected" in content_lower:
                            rejected_count += 1
                        elif "accepted" in content_lower:
                            accepted_count += 1

                        # Mark as processed regardless
                        self.processed_threads.add(thread.id)
                        save_processed_threads(self.processed_threads)
                        break  # Stop after first keyword

        return rejected_count, accepted_count

    @tasks.loop(minutes=5)
    async def forum_scan_loop(self):
        """Run the forum scan every 5 minutes for new messages only."""
        await self.bot.wait_until_ready()
        print("🔄 Running automatic forum scan...")
        await self.scan_forum_messages()

    @forum_scan_loop.before_loop
    async def before_forum_scan_loop(self):
        await self.bot.wait_until_ready()

    # --- Slash command for all-time scan ---
    @app_commands.command(name="alltime_s", description="Scan all forum threads for accepted/rejected messages.")
    async def alltime_s(self, interaction: discord.Interaction):
        if interaction.user.id != TARGET_USER_ID:
            await interaction.response.send_message("❌ You are not allowed to use this command.", ephemeral=True)
            return

        await interaction.response.send_message("🔍 Starting all-time forum scan...", ephemeral=True)
        rejected_count, accepted_count = await self.scan_forum_messages(ignore_date=True, supabase_update=False)
        await interaction.followup.send(
            f"✅ All-time forum scan complete.\nRejected: {rejected_count}\nAccepted: {accepted_count}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ForumAutoScan(bot))
