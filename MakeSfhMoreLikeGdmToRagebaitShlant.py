import discord
from discord.ext import commands

class AttachmentReactor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_channel_id = 1079516597506551928  # your correct channel ID

        # Custom emoji IDs (replace with your own where needed)
        self.upvote_emoji = discord.PartialEmoji(name="upvote", id=974675635861598218)
        self.downvote_emoji = discord.PartialEmoji(name="downvote", id=974675713519153193)

        # blocked_emojis must be strings so we can compare with str(reaction.emoji)
        self.blocked_emojis = {
            str(self.upvote_emoji),   # e.g. "<:upvote:9746...>"
            str(self.downvote_emoji), # e.g. "<:downvote:9746...>"
            "🔥",
            "🔇",
        }

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignore bot messages
        if message.author.bot:
            return

        # only trigger in target channel
        if message.channel.id != self.target_channel_id:
            return

        # skip if no attachments
        if not message.attachments:
            return

        # check for audio attachments and add reactions
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("audio/"):
                await message.add_reaction(self.upvote_emoji)
                await message.add_reaction(self.downvote_emoji)
                await message.add_reaction("🔥")
                await message.add_reaction("🔇")
                break  # only react once per message

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Prevent message authors from reacting to their own posts with blocked emojis."""
        message = reaction.message

        # ignore bot reactions
        if user.bot:
            return

        # only apply in the target channel
        if message.channel.id != self.target_channel_id:
            return

        # only act if the reactor is the message author
        if user.id != message.author.id:
            return

        # compare string forms to handle custom and unicode emojis consistently
        if str(reaction.emoji) in self.blocked_emojis:
            try:
                await reaction.remove(user)
            except discord.Forbidden:
                # missing Manage Messages permission or Remove Reactions permission
                print("⚠️ Missing permission to remove reactions.")
            except discord.HTTPException:
                print("⚠️ Failed to remove reaction due to HTTP error.")

async def setup(bot):
    await bot.add_cog(AttachmentReactor(bot))
