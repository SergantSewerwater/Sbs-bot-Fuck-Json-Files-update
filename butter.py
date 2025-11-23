import discord
from discord.ext import commands
from discord import app_commands

class Butter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener
    async def on_message(self, message: discord.Message):
        if message.author.id == 932981222622249001:
            await message.add_reaction("🧈")

async def setup(bot):
    await bot.add_cog(Butter(bot))
