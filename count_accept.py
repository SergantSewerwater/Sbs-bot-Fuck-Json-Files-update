import discord
from discord import app_commands
from discord.ext import commands
import logging
import re

TARGET_CHANNEL_ID = 899784386038333551
logger = logging.getLogger(__name__)

class CountAccept(commands.Cog):
    """Count occurrences of a keyword in a specific channel's entire history."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="count_accept",
        description="Count how many times a keyword has been mentioned in the acceptance channel."
    )
    @app_commands.describe(keyword="Keyword to count (whole-word, case-insensitive)")
    async def count_accept(self, interaction: discord.Interaction, keyword: str):
        await interaction.response.defer(thinking=True)
        if not keyword or not keyword.strip():
            await interaction.followup.send("Please provide a non-empty keyword.")
            return

        channel = self.bot.get_channel(TARGET_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(TARGET_CHANNEL_ID)
            except Exception:
                logger.exception("Failed to fetch channel %s", TARGET_CHANNEL_ID)
                await interaction.followup.send("Failed to access the target channel.")
                return

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.followup.send("Target channel is not readable.")
            return

        pattern = re.compile(r"\b" + re.escape(keyword) + r"\b", flags=re.IGNORECASE)
        count = 0
        try:
            async for msg in channel.history(limit=None, oldest_first=True):
                if not msg.content:
                    continue
                matches = pattern.findall(msg.content)
                if matches:
                    count += len(matches)
            logger.info("count_accept: keyword=%r count=%d", keyword, count)
            await interaction.followup.send(f"'{keyword}' was mentioned {count} times in the channel (starting at 0).")
        except Exception:
            logger.exception("Error while scanning channel history for keyword=%r", keyword)
            await interaction.followup.send("An error occurred while scanning channel history.")

async def setup(bot: commands.Bot):
    await bot.add_cog(CountAccept(bot))