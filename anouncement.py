import discord
from discord.ext import commands

CHANNEL_IDS = [90363092144449542, 1413643518139695224]
EMOJIS = ["🇳", "🇷", "🇪", "🇮", "🇬"]

class RacismRemover(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("RacismRemover cog loaded")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        print("REACTION FIRED")
        # Ignore bot reactions
        if payload.user_id == self.bot.user.id:
            return

        # Only watch specific channels
        if payload.channel_id not in CHANNEL_IDS:
            return

        emoji = str(payload.emoji)

        # Only watch specific emojis
        if emoji not in EMOJIS:
            return

        print(
            f"Reaction {emoji} added by user {payload.user_id} "
            f"in channel {payload.channel_id}"
        )

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None or not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(payload.message_id)
            member = channel.guild.get_member(payload.user_id)

            if member is None:
                return

            await message.remove_reaction(payload.emoji, member)
            print(f"Removed {emoji} reaction from {member}")

        except discord.Forbidden:
            print("Missing permissions to remove reaction")
        except discord.NotFound:
            print("Message or reaction no longer exists")

async def setup(bot):
    await bot.add_cog(RacismRemover(bot))
