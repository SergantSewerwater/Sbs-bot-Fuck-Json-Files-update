import discord
from discord.ext import commands
from discord import app_commands

CHANNEL_IDS = [90363092144449542, 1413643518139695224]
EMOJIS = ["🇳", "🇷", "🇪", "🇮", "🇬"]

class RacismRemover(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return

        if reaction.message.channel.id not in CHANNEL_IDS:
            return
        
        print()(f"Reaction {reaction.emoji} added by {user} in channel {reaction.message.channel.name}.")
        
        for emoji in EMOJIS:
            if reaction.emoji == emoji:
                try:
                    await reaction.message.remove_reaction(reaction.emoji, user)
                    print()(f"Removed {emoji} reaction from {user} in channel {reaction.message.channel.name}.")
                except discord.Forbidden:
                    print()(f"Failed to remove reaction: missing permissions.")

async def setup(bot):
    await bot.add_cog(RacismRemover(bot))
