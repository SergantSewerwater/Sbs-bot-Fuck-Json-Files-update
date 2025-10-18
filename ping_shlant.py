import discord
from discord import app_commands
from discord.ext import commands

# the cog or something idk
class PingShlant(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    # literally just pings shlant
    @app_commands.command(name="ping_shlant", description="Pings Shlant. yea that's it")
    async def ping_shlant(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"<@530140140211798016>")

# cog loader
async def setup(bot: commands.Bot):
    await bot.add_cog(PingShlant(bot))
