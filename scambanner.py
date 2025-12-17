import discord
from discord.ext import commands

IGNORED_ROLE_ID = 1429783971654406195

# Detect attachments that are images
def attachment_is_image(att: discord.Attachment) -> bool:
    return bool(att.content_type) and att.content_type.startswith("image/")

class ScamBanner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- listener ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.guild.id != 899784386038333551:
            return
        
        # Ensure this is a guild member
        if not isinstance(message.author, discord.Member):
            return
        
        if any(role.id == IGNORED_ROLE_ID for role in message.author.roles):
            return
        
        if len(message.attachments) >= 4 and all(
            attachment_is_image(att) for att in message.attachments
        ):
            try:
                await message.author.ban(
                    reason="Sent 4+ image attachments (auto scamban)"
                )
            except discord.Forbidden:
                print("Missing permissions to ban this member.")
            except discord.HTTPException as e:
                print(f"Failed to ban member: {e}")

            try:
                await message.delete()
            except discord.Forbidden:
                pass
       
            try:
                await message.author.send(
                    "You have been banned by the automatic scam detector for sending 4 or more image attachments in a single message.\n"
                    "If you believe this was a mistake, please contact **sergeantsewerwater**.\n"
                    "Users who reach level 2 or higher are ignored by this system."
                )
            except discord.Forbidden:
                pass

async def setup(bot: commands.Bot):
    await bot.add_cog(ScamBanner(bot))
