import discord
from discord.ext import commands
from discord import app_commands

class Butter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener
    async def on_message(self, message: discord.Message):
        if message.author.id in [1339158762128146463, 932981222622249001, 1117143387695497278]:
            await message.add_reaction("🧈")

async def setup(bot):
    await bot.add_cog(Butter(bot))
