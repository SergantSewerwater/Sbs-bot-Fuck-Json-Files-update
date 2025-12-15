import discord
from discord.ext import commands

TARGET_CHANNEL_ID = 899784386038333555
IGNORED_ROLE_ID = 1429783971654406195

# dict of auto responses
autoresponses = {
    "espanol": "Este chat es solo en inglés.",
    "español": "Este chat es solo en inglés.",
    "showcase": "Don't understand how the \"showcase\" field in <#1352915632936718386> works? Put a YouTube link into the \"showcase\" field to use the thumbnail for your submission\nMake sure that thumbnail isn't already used on the site",
    "upload": "Wanna submit your own song(s)? Read the pinned post in <#1352870773588623404>",
    "submit": "Wanna submit your own song(s)? Read the pinned post in <#1352870773588623404>",
    "file": "Looking for certain songs? You can find them on Jukebox or our website\nhttps://www.songfilehub.com/",
    "song": "Looking for certain songs? You can find them on Jukebox or our website\nhttps://www.songfilehub.com/",
    "where": "Have questions? Read <#1201831020890951680> and the pinned post in <#1352870773588623404>\nOtherwise, go to <#1302962232015192115>",
    "why": "Have questions? Read <#1201831020890951680> and the pinned post in <#1352870773588623404>\nOtherwise, go to <#1302962232015192115>",
    "how": "Have questions? Read <#1201831020890951680> and the pinned post in <#1352870773588623404>\nOtherwise, go to <#1302962232015192115>",
    "?": "Have questions? Read <#1201831020890951680> and the pinned post in <#1352870773588623404>\nOtherwise, go to <#1302962232015192115>",
}

class AutoResponder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- listener ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id != TARGET_CHANNEL_ID:
            return

        if isinstance(message.author, discord.Member):
            if any(role.id == IGNORED_ROLE_ID for role in message.author.roles):
                return
        
        content = message.content.lower()
        for keyword, response in autoresponses.items():
            if keyword in content:
                await message.channel.send(f"{response}\n{message.author.mention}")
                return
        
async def setup(bot: commands.Bot):
    await bot.add_cog(AutoResponder(bot))
