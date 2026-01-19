import discord
from discord.ext import commands

def normalize_emoji(e: str) -> str:
    return e.replace("\uFE0F", "")

CHANNEL_IDS = [903630921444495420, 1413643518139695224]
EMOJIS = ["🇳", "🇷", "🇪", "🇮", "🇬"]

class RacismRemover(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("RacismRemover cog loaded")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        if payload.channel_id not in CHANNEL_IDS:
            return

        emoji = str(payload.emoji).replace("\uFE0F", "")
        if emoji not in EMOJIS:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return

        message = await channel.fetch_message(payload.message_id)

        try:
            user = discord.Object(id=payload.user_id)
            await message.remove_reaction(payload.emoji, user)
            print("Reaction removed successfully")
        except discord.Forbidden:
            print("Missing Manage Messages permission")

async def setup(bot):
    await bot.add_cog(RacismRemover(bot))
