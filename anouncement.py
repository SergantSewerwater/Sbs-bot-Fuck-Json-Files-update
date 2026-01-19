import discord
from discord.ext import commands

CHANNEL_IDS = [90363092144449542, 1413643518139695224]
EMOJIS = ["🇳", "🇷", "🇪", "🇮", "🇬"]

class RacismRemover(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        print("REACTION") 

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member):
        if user.bot:
            return

        if reaction.message.channel.id not in CHANNEL_IDS:
            return

        print(f"Reaction {reaction.emoji} added by {user} in {reaction.message.channel.name}")

        if str(reaction.emoji) in EMOJIS:
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
                print(f"Removed {reaction.emoji} from {user}")
            except discord.Forbidden:
                print("Missing permissions to remove reaction")

async def setup(bot):
    await bot.add_cog(RacismRemover(bot))
