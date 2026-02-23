import discord
from discord.ext import commands
import logging
import time
from typing import Dict, Optional
import requests

# =====================
# CONFIG
# =====================

# 🔧 TEMP TEST CHANNEL
TARGET_CHANNEL_ID = 1475506808826101924  # <-- your testing channel

IGNORED_ROLE_ID = 1429783971654406195
SUBMIT_CHANNEL_ID = 1352915632936718386

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"

# =====================
# LOGGER
# =====================

logger = logging.getLogger("sbsbot.ReplaceOtherBots")
logging.basicConfig(
    level=logging.DEBUG,  # 🔧 DEBUG FOR TESTING
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# =====================
# AUTORESPONSES
# =====================

autoresponses = {
    "espanol": "Este chat es solo en inglés.",
    "español": "Este chat es solo en inglés.",
    "spanish": "Este chat es solo en inglés.",
    "russian": "Этот чат только для англоговорящих",
    "русский": "Этот чат только для англоговорящих",
    "showcase": (
        "Don't understand how the \"showcase\" field works?\n"
        "Put a YouTube link into the \"showcase\" field so the site can generate a thumbnail."
    ),
    "geode": (
        "Version 2.208 of Geometry Dash broke Geode. "
        "Once the developers update Geode, it will work again."
    ),
    "jukebox": (
        "Want a tutorial on how to use Jukebox? You can find one [here](https://youtu.be/qfTO4nBLsbk?si=YGlr4J3DuRbYHcZ9)\nHaving problems with Jukebox? Read <#1201831020890951680> and <#1308752971743629363>\nIf you still have issues, report them in <#1302962232015192115>",
    ),
    "upload": "Wanna submit your own song(s)? Read the pinned post.",
    "submit": "Wanna submit your own song(s)? Read the pinned post.",
    "song": "Looking for songs? Check Jukebox or the SongFileHub website.",
    "nong": "Looking for songs? Check Jukebox or the SongFileHub website.",
    "where": "Read the pinned FAQ or ask in the help channel.",
    "why": "Read the pinned FAQ or ask in the help channel.",
    "how": "Read the pinned FAQ or ask in the help channel.",
    "?": "Read the pinned FAQ or ask in the help channel.",
}

# =====================
# AI PROMPT
# =====================

AI_PROMPT_TEMPLATE = """
You are an FAQ intent classifier for the SongFileHub Discord server.

Context:
- Geometry Dash community
- SongFileHub submissions
- Songs and NONGs are custom music
- Showcase field requires a YouTube link
- Jukebox and Geode are GD-related tools

Task:
1. Determine if the message is a QUESTION.
2. If so, choose the BEST matching autoresponse key.
3. If none fit, respond with NONE.

Rules:
- Respond ONLY with one key or NONE
- No explanations

Keys:
{keys}

Message:
"{message}"
"""

def ai_pick_autoresponse(message: str) -> Optional[str]:
    prompt = AI_PROMPT_TEMPLATE.format(
        keys=", ".join(autoresponses.keys()),
        message=message
    )

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 6
                }
            },
            timeout=10
        )

        data = r.json()
        logger.debug("AI raw JSON: %s", data)

        # ---- robust response extraction ----
        if "response" in data and isinstance(data["response"], str):
            result = data["response"].strip()

        elif "message" in data and "content" in data["message"]:
            result = data["message"]["content"].strip()

        else:
            logger.error("Unknown AI response format")
            return None

    except Exception:
        logger.exception("AI request failed")
        return None

    if not result:
        logger.debug("AI returned empty result")
        return None

    logger.info("AI decision: %r → %r", message, result)

    if result == "NONE":
        return None

    if result in autoresponses:
        return result

    logger.warning("AI returned invalid key: %r", result)
    return None

# =====================
# COG
# =====================

class ReplaceOtherBots(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cooldowns: Dict[tuple, float] = {}
        self._cooldown_seconds = 30.0

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # 🔍 CONFIRM MESSAGE RECEIPT
        logger.debug(
            "Message received: channel=%s author=%s content=%r",
            message.channel.id,
            message.author,
            message.content
        )

        if message.channel.id != TARGET_CHANNEL_ID:
            return

        if isinstance(message.author, discord.Member) and any(
            role.id == IGNORED_ROLE_ID for role in message.author.roles
        ):
            logger.debug("Skipping: user has AI Proof role")
            return

        picked_key = ai_pick_autoresponse(message.content)

        if not picked_key:
            logger.debug("No autoresponse selected")
            return

        now = time.time()
        cooldown_key = (message.channel.id, message.author.id, picked_key)
        last = self._cooldowns.get(cooldown_key, 0.0)

        if now - last < self._cooldown_seconds:
            logger.debug("Cooldown hit for key=%s user=%s", picked_key, message.author)
            return

        self._cooldowns[cooldown_key] = now
        response = autoresponses[picked_key]

        await message.channel.send(f"{response}\n{message.author.mention}")

# =====================
# SETUP
# =====================

async def setup(bot: commands.Bot):
    logger.info("Registering ReplaceOtherBots cog (AI FAQ testing mode)")
    await bot.add_cog(ReplaceOtherBots(bot))
