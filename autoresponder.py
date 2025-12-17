from email import message
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


# --- scambanner ---
@commands.Cog.listener()
async def on_message(self, message: discord.Message):
    # Ignore bots
    if message.guild is None or message.guild.id != 899784386038333551:
        return
    
    if message.author.bot:
        return
    

    # Ensure this is a guild member (not a DM user)
    if not isinstance(message.author, discord.Member):
        return

    # Ignore members with the ignored role
    if any(role.id == IGNORED_ROLE_ID for role in message.author.roles):
        return


    

# Detect attachments that are images
def attachment_is_image(att: discord.Attachment) -> bool:
    return bool(att.content_type) and att.content_type.startswith("image/")


# --- scambanner ---
@commands.Cog.listener()
async def on_message(self, message: discord.Message):
    # Ignore DMs & wrong guild
    if message.guild is None or message.guild.id != 899784386038333551:
        return

    # Ignore bots
    if message.author.bot:
        return

    # Ensure this is a guild member
    if not isinstance(message.author, discord.Member):
        return

    # Ignore members with the ignored role (level 2+)
    if any(role.id == IGNORED_ROLE_ID for role in message.author.roles):
        return

    # Check attachment count AND image-only
    if len(message.attachments) >= 3 and all(
        attachment_is_image(att) for att in message.attachments
    ):
       
        try:
            await message.author.send(
                "You have been banned by the automatic scam detector for sending "
                "3 or more image attachments in a single message.\n\n"
                "If you believe this was a mistake, please contact **sergeantsewerwater**.\n"
                "Users who reach level 2 or higher are ignored by this system."
            )
        except discord.Forbidden:
            pass

   
        try:
            await message.delete()
        except discord.Forbidden:
            pass

      
        try:
            await message.author.ban(
                reason="Sent 3+ image attachments (auto scamban)"
            )
        except discord.Forbidden:
            print("Missing permissions to ban this member.")
        except discord.HTTPException as e:
            print(f"Failed to ban member: {e}")

        return


            


        
async def setup(bot: commands.Bot):
    await bot.add_cog(AutoResponder(bot))
