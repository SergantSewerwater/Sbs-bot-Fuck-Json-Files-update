import discord
from discord.ext import commands

TARGET_CHANNEL_ID = 899784386038333555
IGNORED_ROLE_ID = 1429783971654406195

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

class AutoResponder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- No Questions In General ---
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
# --- Delete Stuff In #Submit-Here
@commands.Cog.listener()
async def on_message(self, message: discord.Message):
    if message.channel.id != 1352915632936718386:
        return

    if message.author.id != 1272790489380421643:
        await message.delete()
        return



# --- StickyBot
STICKY_CHANNELS = {
 1349678108768469037
}

STICKY_CONTENT = ""

@commands.Cog.listener()
async def on_message(self, message: discord.Message):
    if not STICKY_CONTENT:
        return
    if message.channel.id not in STICKY_CHANNELS:
        return

    if message.author == self.bot.user:
        return

    channel = message.channel

    async for msg in channel.history(limit=20):
        if msg.author == self.bot.user:
            await msg.delete()
            break

    await channel.send(STICKY_CONTENT)
    await self.bot.process_commands(message)

# --- Member Count ---
MEMBER_COUNT_CHANNEL_ID = 1453008993692942436

class MemberCount(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def update_member_count(self, guild: discord.Guild):
        member_count = max(guild.member_count - 5, 0)

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
    await bot.add_cog(AutoResponder(bot))
