import discord
from discord.ext import commands

class Butter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # use a set for fast membership checks
        self._butter_users = {1339158762128146463, 932981222622249001, 1117143387695497278}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignore bots and DMs
        if message.author.bot or message.guild is None:
            return

        if message.author.id in self._butter_users:
            try:
                await message.add_reaction("🧈")
            except discord.Forbidden:
                # missing permissions to add reactions — silently ignore
                pass
            except Exception:
                # avoid bubbling unexpected errors from this listener
                pass

async def setup(bot):
    await bot.add_cog(Butter(bot))
