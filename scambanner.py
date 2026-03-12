import discord
from discord.ext import commands
import logging
import time
from typing import Dict

logger = logging.getLogger("sbsbot.ScamBanner")

IGNORED_ROLE_ID = 1429783971654406195

# Detect attachments that are images
def attachment_is_image(att: discord.Attachment) -> bool:
    return bool(att.content_type) and att.content_type.startswith("image/")

class ScamBanner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # small cooldown map to avoid processing same user repeatedly and spamming ban requests
        self._recent_flags: Dict[int, float] = {}
        self._per_user_cooldown = 60.0  # seconds

    # --- listener ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.guild is None or message.guild.id != 899784386038333551:
            return
        
        # Ensure this is a guild member
        if not isinstance(message.author, discord.Member):
            return
        
        if any(role.id == IGNORED_ROLE_ID for role in message.author.roles):
            return
        
        if len(message.attachments) >= 4 and all(
            attachment_is_image(att) for att in message.attachments
        ):
            now = time.time()
            last = self._recent_flags.get(message.author.id, 0.0)
            if now - last < self._per_user_cooldown:
                logger.info("Skipping auto scamban for %s due to cooldown", message.author)
                return

            self._recent_flags[message.author.id] = now

            try:
                await message.author.send(
                    "You have been banned by the automatic scam detector for sending 4 or more image attachments in a single message.\n"
                    "If you believe this was a mistake, please contact **sergeantsewerwater**.\n"
                    "Users who reach level 2 or higher are ignored by this system."
                )
            except discord.Forbidden:
                logger.debug("Missing permissions to send DM to user %s", message.author)

            try:
                await message.author.ban(
                    reason="Sent 4+ image attachments (auto scamban)"
                )
                logger.info("Auto-banned user %s for sending 4+ images", message.author)
            except discord.Forbidden:
                logger.warning("Missing permissions to ban user %s", message.author)
            except discord.HTTPException as e:
                logger.exception("Failed to ban member %s: %s", message.author, e)

            try:
                await message.delete()
            except discord.Forbidden:
                logger.warning("Missing permissions to delete message %s", message.id)
            except Exception:
                logger.exception("Failed to delete scamban message %s", message.id)

async def setup(bot: commands.Bot):
    await bot.add_cog(ScamBanner(bot))
