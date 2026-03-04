import discord
from discord.ext import commands
import logging
import logging.handlers
import asyncio
import time
from typing import Optional
import requests
from pathlib import Path

# =====================
# CONFIG
# =====================

TARGET_CHANNEL_ID = 899784386038333555
IGNORED_ROLE_ID = 1429783971654406195

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"

# =====================
# LOGGING SETUP
# =====================

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "discord.log"

logger = logging.getLogger("sbsbot.ReplaceOtherBots")
logger.setLevel(logging.DEBUG)

_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(_formatter)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)

logger.addHandler(_file_handler)
logger.addHandler(_console_handler)

# =====================
# AUTORESPONSES
# =====================

autoresponses = {
    "spanish": "Este chat es solo en inglés.",
    "russian": "Этот чат только для англоговорящих",
    "showcase": (
        "Don't understand how the \"showcase\" field in <#1352915632936718386> works?\n"
        "Put a YouTube link into the showcase field so the site can generate a thumbnail.\n"
        "Make sure the thumbnail is not already used."
    ),
    "jukebox": (
        "Want a Jukebox tutorial? https://youtu.be/qfTO4nBLsbk\n"
        "Problems? Read <#1201831020890951680> and <#1308752971743629363>\n"
        "Still broken? Report in <#1302962232015192115>"
    ),
    "submit": "Wanna submit your own song or NONG? Read the pinned post in <#1352870773588623404>",
    "song": "Looking for songs or NONGs? Use Jukebox or https://www.songfilehub.com/",
    "ai proof": (
        "The AI Proof role prevents bot auto-responses.\n"
        "You receive it after reaching level 2."
    ),
    "generic_help": (
        "Have questions? Read <#1201831020890951680> and the pinned post in "
        "<#1352870773588623404>\nOtherwise, go to <#1302962232015192115>"
    ),
}

# =====================
# AI PROMPT
# =====================

AI_PROMPT_TEMPLATE = """
You are NOT a chatbot.
You are an intent classifier for an FAQ autoresponder bot.

This bot runs in the SongFileHub Discord server.

=== SERVER CONTEXT ===
- Geometry Dash community
- If a message contains a random buzzword that stands out, that is probably a geometry dash level. "Where can i find slaughterhouse song" -> Slaughterhouse is the level.
- Custom songs/nongs are used in geometry dash levels.
- Users submit SONGS or NONGs (custom music)
- The words: Song, NONG, Mashup and Remix are interchangable
- "Submitting" means using the submission form/channel
- The "showcase" field REQUIRES a YouTube link for thumbnails
- If a user is looking for a song or asking where a certain song is, they want to know how to find it, not how to submit it. This usually means the "song" keyword is correct
- Jukebox depends on Geode
- Geode is broken in GD 2.208
- Users frequently ask the same lazy questions

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
# AI CALL (SYNC, RUNS IN EXECUTOR)
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
                "options": {
                    "temperature": 0.0,
                    "num_predict": 12,
                },
            },
            timeout=90,
        )

        data = response.json()
        logger.debug("AI raw response: %s", data)

        if "response" in data:
            result = data["response"].strip()
        elif "message" in data and "content" in data["message"]:
            result = data["message"]["content"].strip()
        else:
            logger.error("Unrecognized Ollama response format")
            return None

    except Exception:
        logger.exception("AI request failed")
        return None

    logger.info("AI decision: %r → %r", message, result)

    if not result or result == "NONE":
        return None

    if result in autoresponses:
        return result

    logger.warning("AI returned invalid key: %r", result)
    return None

# =====================
# COG WITH QUEUE WORKER
# =====================

class ReplaceOtherBots(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue: asyncio.Queue[discord.Message] = asyncio.Queue()
        self.worker_task = bot.loop.create_task(self._ai_worker())
        logger.info("AI queue worker initialized")

    def cog_unload(self):
        logger.info("Shutting down AI worker")
        self.worker_task.cancel()

    async def _ai_worker(self):
        logger.info("AI worker started")
        loop = asyncio.get_running_loop()

        while True:
            message = await self.queue.get()

            try:
                content = message.content.lower().strip()

                picked_key = await loop.run_in_executor(
                    None, ai_pick_autoresponse, content
                )

                if not picked_key:
                    logger.debug("Worker: no response for message")
                    continue

                response = autoresponses[picked_key]

                await message.channel.send(
                    f"{response}\n{message.author.mention}"
                )

                logger.info(
                    "Responded with key=%s user=%s",
                    picked_key,
                    message.author,
                )

            except Exception:
                logger.exception("Unhandled error in AI worker")

            finally:
                self.queue.task_done()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id != TARGET_CHANNEL_ID:
            return

        if isinstance(message.author, discord.Member) and any(
            role.id == IGNORED_ROLE_ID for role in message.author.roles
        ):
            logger.debug("Skipped message: AI Proof role")
            return

        logger.debug(
            "Enqueued message: channel=%s author=%s content=%r",
            message.channel.id,
            message.author,
            message.content,
        )

        await self.queue.put(message)

# =====================
# SETUP
# =====================

async def setup(bot: commands.Bot):
    logger.info("Registering ReplaceOtherBots cog (AI FAQ queue mode)")
    await bot.add_cog(ReplaceOtherBots(bot))
