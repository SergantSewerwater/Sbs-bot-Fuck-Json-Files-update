import discord
from discord.ext import commands
import logging
from typing import Set

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
    "jukebox": "Want a tutorial on how to use Jukebox? You can find one [here](https://youtu.be/qfTO4nBLsbk?si=YGlr4J3DuRbYHcZ9)\nHaving problems with Jukebox? Read <#1201831020890951680> and <#1308752971743629363>\nIf you still have issues, report them in <#1302962232015192115>",
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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots early
        if message.author.bot:
            return

        try:
            # --- Delete stuff in #submit-here
            if message.channel.id == SUBMIT_CHANNEL_ID:
                if message.author.id != 1272790489380421643:
                    self.logger.info("Deleting message from %s in submit channel %s", message.author, message.channel.id)
                    try:
                        await message.delete()
                    except Exception:
                        self.logger.exception("Failed to delete message in submit channel from %s", message.author)
                    return

            # --- Auto responses in the target channel
            if message.channel.id == TARGET_CHANNEL_ID:
                if isinstance(message.author, discord.Member) and any(role.id == IGNORED_ROLE_ID for role in message.author.roles):
                    self.logger.debug("Skipping autoresponse because user has ignored role: %s", message.author)
                else:
                    content = message.content.lower()
                    for keyword, response in autoresponses.items():
                        if keyword in content:
                            self.logger.info("Autoresponding to %s for keyword '%s'", message.author, keyword)
                            await message.channel.send(f"{response}\n{message.author.mention}")
                            return

            # --- Sticky message behavior
            if STICKY_CONTENT and message.channel.id in STICKY_CHANNELS:
                if message.author != self.bot.user:
                    # Remove the bot's previous sticky message (if any)
                    async for msg in message.channel.history(limit=50):
                        if msg.author == self.bot.user:
                            try:
                                await msg.delete()
                                self.logger.debug("Deleted previous sticky message %s in channel %s", msg.id, message.channel.id)
                            except Exception:
                                self.logger.exception("Failed to delete old sticky message %s", msg.id)
                            break

                    self.logger.info("Posting sticky message to channel %s", message.channel.id)
                    await message.channel.send(STICKY_CONTENT)

        except Exception:
            self.logger.exception("Uncaught exception in ReplaceOtherBots.on_message")
        finally:
            # Ensure commands still work when on_message is present
            await self.bot.process_commands(message)

# --- StickyBot
STICKY_CHANNELS = {
 1453008993692942436
}

STICKY_CONTENT = "hello"


# --- Member Count ---
MEMBER_COUNT_CHANNEL_ID = 1453008993692942436

class MemberCount(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def update_member_count(self, guild: discord.Guild):
        member_count = max((guild.member_count or 0) - 5, 0)

        channel = guild.get_channel(MEMBER_COUNT_CHANNEL_ID)
        if channel is None or not isinstance(channel, discord.TextChannel):
            return

        # Delete previous bot messages
        async for msg in channel.history(limit=50):
            if msg.author == self.bot.user:
                await msg.delete()

        # Send updated count
        await channel.send(f"👥 **Member Count:** {member_count}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.update_member_count(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.update_member_count(member.guild)




async def setup(bot: commands.Bot):
    logger.info("Registering ReplaceOtherBots and MemberCount cogs")
    await bot.add_cog(ReplaceOtherBots(bot))
    await bot.add_cog(MemberCount(bot))
