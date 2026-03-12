import discord
from discord import app_commands
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
TARGET_CHANNEL_ID = 1475506808826101924
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
    "generic_help": "Have questions? Read the pinned help channels.",
}

# =====================
# AI PROMPT TEMPLATE
# =====================

AI_PROMPT_TEMPLATE = """
You are an intent classifier for an FAQ autoresponder bot.

=== KEYS ===
{keys}

=== MESSAGE ===
"{message}"

Respond with only ONE key or NONE.
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
        self.sticky_enabled = True
        self._sticky_state = defaultdict(dict)
        self._sticky_cooldown = 5  # seconds

    # =====================
    # Sticky slash command
    # =====================
    @app_commands.command(name="sticky", description="Enable or disable sticky messages")
    @app_commands.describe(state="Turn sticky messages on or off")
    @app_commands.guilds(discord.Object(id=STICKY_CONTROL_GUILD))
    async def sticky_slash(self, interaction: discord.Interaction, state: str = None):
        if state is None:
            status = "ON" if self.sticky_enabled else "OFF"
            await interaction.response.send_message(f"Sticky messages are currently **{status}**.", ephemeral=True)
            return

        state = state.lower()
        if state in ("on", "enable", "enabled"):
            self.sticky_enabled = True
            await interaction.response.send_message("✅ Sticky messages **enabled**.", ephemeral=True)
        elif state in ("off", "disable", "disabled"):
            self.sticky_enabled = False
            await interaction.response.send_message("⛔ Sticky messages **disabled**.", ephemeral=True)
        else:
            await interaction.response.send_message("Usage: `/sticky on` or `/sticky off`", ephemeral=True)

    # =====================
    # Setup to add command
    # =====================
    async def cog_load(self):
        # Sync the slash command to your guild
        self.bot.tree.add_command(self.sticky_slash)
        await self.bot.tree.sync(guild=discord.Object(id=STICKY_CONTROL_GUILD))

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