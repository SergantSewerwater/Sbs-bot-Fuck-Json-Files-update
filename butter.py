import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from supabase import create_client
from collections import deque

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    raise ValueError("SUPABASE_URL or SERVICE_ROLE_KEY not found in environment variables.")

# create supabase client for this cog (uses same env as SlopGen)
supabase = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

class Butter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # use a set for fast membership checks
        self._butter_users = {1339158762128146463, 932981222622249001}
        # capped recent-event cache (dedupe) to avoid unbounded memory usage
        self._recent_deque = deque(maxlen=10000)
        self._recent_set = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignore bots and DMs
        if message.author.bot or message.guild is None:
            return

        if message.author.id in self._butter_users:
            try:
                await message.add_reaction("🧈")
            except discord.Forbidden:
                # missing permissions to add reactions — silently ignore
                pass
            except Exception:
                # avoid bubbling unexpected errors from this listener
                pass

    async def _increment_misc_by_id(self, row_id: int, delta: int = 1):
        """Increment the 'count' in miscinfo where id == row_id (create if missing)."""
        # read current
        res = supabase.from_("miscinfo").select("count").eq("id", row_id).execute()
        current = 0
        if res.data and len(res.data) > 0:
            try:
                current = int(res.data[0].get("count", 0))
            except Exception:
                current = 0

        new_value = current + delta
        # attempt update
        upd = supabase.from_("miscinfo").update({"count": new_value}).eq("id", row_id).execute()
        # if update didn't affect a row (row missing), insert a fallback
        if getattr(upd, "count", 0) == 0:
            try:
                supabase.from_("miscinfo").insert({"id": row_id, "count": new_value}).execute()
            except Exception:
                # ignore insertion errors, don't crash the bot
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Increment miscinfo.id == 3 when a butter reaction is added to messages authored by targeted users."""
        # ignore reactions outside guilds (DMs)
        if payload.guild_id is None:
            return

        # only count the butter emoji
        emoji_name = getattr(payload.emoji, "name", str(payload.emoji))
        if emoji_name != "🧈":
            return

        # dedupe key (message, reacting user, emoji)
        key = (payload.message_id, payload.user_id, emoji_name)
        if key in self._recent_set:
            return
        # push to deque and set, evict if needed
        if len(self._recent_deque) == self._recent_deque.maxlen:
            old = self._recent_deque.popleft()
            self._recent_set.discard(old)
        self._recent_deque.append(key)
        self._recent_set.add(key)

        try:
            channel = self.bot.get_channel(payload.channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            # can't fetch message => ignore safely
            return

        # only increment if the message author is one of the tracked users
        if message.author and message.author.id in self._butter_users:
            # increment miscinfo row id = 3
            try:
                await self._increment_misc_by_id(3, 1)
            except Exception:
                # ignore Supabase errors so the bot remains functional
                pass

async def setup(bot):
    await bot.add_cog(Butter(bot))
