import discord
from discord.ext import commands
import logging
import logging.handlers
import asyncio
import time
from typing import Optional
import requests
from pathlib import Path
from collections import defaultdict

# =====================
# CONFIG
# =====================

BOT_PREFIX = "slop"
TARGET_CHANNEL_ID = 899784386038333555
IGNORED_ROLE_ID = 1429783971654406195

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"

# Sticky system
STICKY_CONTENT = "Jukebox servers are down. We're trying to fix it."
STICKY_CHANNELS = {899784386038333555}
STICKY_CONTROL_GUILD = 1411767823730085971
STICKY_COOLDOWN = 5  # seconds

# =====================
# LOGGING SETUP
# =====================

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "discord.log"

logger = logging.getLogger("sbsbot.ReplaceOtherBots")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# =====================
# AUTORESPONSES
# =====================

autoresponses = {
    "spanish": "Este chat es solo en inglés.",
    "russian": "Этот чат только для англоговорящих",
    "showcase": (
        "Don't understand how the \"showcase\" field works?\n"
        "Put a YouTube link so the site can generate a thumbnail.\n"
        "Make sure the thumbnail is not already used."
    ),
    "jukebox": (
        "Want a Jukebox tutorial? https://youtu.be/qfTO4nBLsbk\n"
        "Problems? Read pinned posts for help.\n"
    ),
    "submit": "Wanna submit your own song or NONG? Read the pinned post.",
    "song": "Looking for songs or NONGs? Use Jukebox or https://www.songfilehub.com/",
    "ai proof": "The AI Proof role prevents bot auto-responses.",
    "no_loop": "Song not looping after death? This is not an issue with jukebox, it is an issue with geometry dash, and we have no way of fixing it.",
    "web_request": "Having web request failed errors? We currently have no idea why this happens and no clue how to fix it.",
    "generic_help": "Have questions? Read the pinned help channels.",
}

# =====================
# AI PROMPT
# =====================

AI_PROMPT_TEMPLATE = """
You are NOT a chatbot.
You are an intent classifier for an FAQ autoresponder bot.

This bot runs in the SongFileHub Discord server.

=== CONTEXT ===
SongFileHub is a database storing NONGs for use in geometry dash
A NONG is a song not available in the normal Geometry Dash song library
Jukebox is a mod for geometry dash that makes using NONGs from the SongFileHub database easier
To get a NONG on the database users have to submit via the SongFileHub discord server in a submission form


The following is context regarding each keyword, these are simply guidelines.

spanish: use when someone speaks spanish
russian: use when someone speaks russian
showcase: use when someone asks or is confused about the showcase system in the submission forms, not for when they ask to submit as a whole, just for showcases
jukebox: for when someone asks about a specific jukebox feature.
submit: for when someone asks how to submit something.
song: for when someone asks how to get a specific song, 
ai proof: for when someone asks about the ai proof role
web_request: a common error users may encounter with the jukebox mod displays a web request error and a negative number for example "web request failed -60", use this keyword if you believe a user is struggeling with such an error.
no_loop: a common bug in the jukebox mod is when songs dont loop after death, use this keyword if you believe a user is experiencing this issue.
generic_help: for when someone asks a question that is asking for support/help regarding geometry dash, songfilehub or jukebox but it doesnt fit any other keywords.

=== TASK ===
Decide whether the message is asking a COMMON FAQ question.
If yes:
- Return the BEST matching key

If no:
- Return NONE

=== RULES ===
- Output ONE key or NONE
- No explanations
- If unsure → NONE
- If vague → NONE

=== KEYS ===
{keys}

=== MESSAGE ===
"{message}"

Respond with ONLY ONE key or NONE.
"""

# =====================
# AI CALL
# =====================

def ai_pick_autoresponse(message: str) -> Optional[str]:
    prompt = AI_PROMPT_TEMPLATE.format(
        keys=", ".join(autoresponses.keys()),
        message=message,
    )
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 12},
            },
            timeout=60,
        )
        data = response.json()
        result = data.get("response") or data.get("message", {}).get("content")
        if result:
            result = result.strip()
        return result if result in autoresponses else None
    except Exception:
        logger.exception("AI request failed")
        return None

# =====================
# COG
# =====================

class ReplaceOtherBots(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue: asyncio.Queue[discord.Message] = asyncio.Queue()
        self.worker_task = bot.loop.create_task(self._ai_worker())
        self.sticky_enabled = False
        self._sticky_state = defaultdict(dict)

    def cog_unload(self):
        self.worker_task.cancel()

    # ---------------------
    # Sticky toggle command
    # ---------------------
    @commands.command(name="sticky")
    async def sticky_toggle(self, ctx: commands.Context, state: str = None):
        if ctx.guild is None or ctx.guild.id != STICKY_CONTROL_GUILD:
            return

        if state is None:
            status = "ON" if self.sticky_enabled else "OFF"
            await ctx.send(f"Sticky messages are currently **{status}**.")
            return

        state = state.lower()
        if state in ("on", "enable", "enabled"):
            self.sticky_enabled = True
            await ctx.send("✅ Sticky messages **enabled**.")
        elif state in ("off", "disable", "disabled"):
            self.sticky_enabled = False
            await ctx.send("⛔ Sticky messages **disabled**.")
        else:
            await ctx.send(f"Usage: `{BOT_PREFIX} sticky on` or `{BOT_PREFIX} sticky off`")

    # ---------------------
    # AI worker
    # ---------------------
    async def _ai_worker(self):
        loop = asyncio.get_running_loop()
        while True:
            message = await self.queue.get()
            try:
                picked_key = await loop.run_in_executor(None, ai_pick_autoresponse, message.content.lower().strip())
                if picked_key:
                    await message.channel.send(f"{autoresponses[picked_key]}\n{message.author.mention}")
                    logger.info("Responded with key=%s user=%s", picked_key, message.author)
            except Exception:
                logger.exception("Error in AI worker")
            finally:
                self.queue.task_done()

    # ---------------------
    # Message handler
    # ---------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Allow commands
        await self.bot.process_commands(message)

        # Ignore commands for sticky
        if message.content.startswith(BOT_PREFIX):
            return

        # Handle sticky messages
        if self.sticky_enabled and message.channel.id in STICKY_CHANNELS and STICKY_CONTENT:
            await self._handle_sticky(message)

        # AI filtering
        if message.channel.id == TARGET_CHANNEL_ID:
            if isinstance(message.author, discord.Member) and any(role.id == IGNORED_ROLE_ID for role in message.author.roles):
                return
            await self.queue.put(message)

    # ---------------------
    # Sticky handler
    # ---------------------
    async def _handle_sticky(self, message: discord.Message):
        state = self._sticky_state[message.channel.id]
        now = time.time()
        last_post = state.get("last_post", 0)

        if now - last_post < STICKY_COOLDOWN:
            return

        last_msg_id = state.get("last_msg_id")

        # Try delete previous sticky quickly
        try:
            if last_msg_id:
                msg = await message.channel.fetch_message(last_msg_id)
                if msg.author == self.bot.user:
                    await msg.delete()
        except Exception:
            pass  # ignore if not found

        try:
            sent = await message.channel.send(STICKY_CONTENT)
            state["last_msg_id"] = sent.id
            state["last_post"] = now
            logger.debug("Sticky posted in %s", message.channel.id)
        except Exception:
            logger.exception("Failed to send sticky")

# =====================
# SETUP
# =====================
async def setup(bot: commands.Bot):
    logger.info("Registering ReplaceOtherBots cog")
    await bot.add_cog(ReplaceOtherBots(bot))