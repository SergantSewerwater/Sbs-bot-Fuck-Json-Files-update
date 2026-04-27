import discord
from discord import app_commands
from discord.ext import commands
import datetime
import logging

class EventUtils(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="check_submissions", description="Check top 5 most upvoted submissions in the event channel after a specific date")
    @app_commands.describe(date="Date in YYYY-MM-DD format (e.g., 2024-01-01) to check submissions after")
    async def check_submissions(self, interaction: discord.Interaction, date: str):
        # Check if user has the required role
        required_role_id = 899796185966075905
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        if not member or not any(role.id == required_role_id for role in member.roles):
            await interaction.response.send_message("❌ You do not have permission to use this command.")
            return

        try:
            # Parse the date
            after_date = datetime.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            await interaction.response.send_message("❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2024-01-01).")
            return

        # Channel and tag IDs
        channel_id = 1352870773588623404
        tag_id = 1412792568768495677

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            await interaction.response.send_message("❌ Channel not found.")
            return
        if not isinstance(channel, discord.ForumChannel):
            await interaction.response.send_message("❌ The specified channel is not a forum channel.")
            return

        await interaction.response.defer()

        submissions = []
        total_threads_checked = 0

        logging.info(f"Checking submissions after date: {after_date}")

        # Get all threads in the forum
        try:
            async for thread in channel.archived_threads(limit=1000):
                total_threads_checked += 1
                # Check if thread has the tag and is after the date
                if tag_id in [tag.id for tag in thread.applied_tags] and thread.created_at and thread.created_at >= after_date:
                    logging.info(f"Found submission: {thread.name}, created: {thread.created_at}, tags: {[t.name for t in thread.applied_tags]}")
                    submissions.append(thread)
            for thread in channel.threads:
                total_threads_checked += 1
                if tag_id in [tag.id for tag in thread.applied_tags] and thread.created_at and thread.created_at >= after_date:
                    logging.info(f"Found submission: {thread.name}, created: {thread.created_at}, tags: {[t.name for t in thread.applied_tags]}")
                    submissions.append(thread)
        except Exception as e:
            logging.error(f"Error fetching threads: {e}")
            await interaction.followup.send("❌ Error fetching submissions.")
            return

        logging.info(f"Total threads checked: {total_threads_checked}, submissions found: {len(submissions)}")

        if not submissions:
            await interaction.followup.send(f"No submissions found after the specified date with the event tag. Total threads checked: {total_threads_checked}")
            return

        # Calculate scores
        scored_submissions = []
        for thread in submissions:
            try:
                # Get the starter message
                starter_message = await thread.fetch_message(thread.id)
                logging.info(f"Thread {thread.name}: reactions {[getattr(r.emoji, 'name', str(r.emoji)) for r in starter_message.reactions]}")
                upvote_count = 0
                downvote_count = 0
                for reaction in starter_message.reactions:
                    if hasattr(reaction.emoji, 'name') and reaction.emoji.name.lower() == "upvote":
                        upvote_count = reaction.count
                    elif hasattr(reaction.emoji, 'name') and reaction.emoji.name.lower() == "downvote":
                        downvote_count = reaction.count
                score = upvote_count - downvote_count
                logging.info(f"Upvotes: {upvote_count}, Downvotes: {downvote_count}, Score: {score}")
                scored_submissions.append((thread, score))
            except Exception as e:
                logging.error(f"Error processing thread {thread.id}: {e}")
                continue

        # Sort by score descending
        scored_submissions.sort(key=lambda x: x[1], reverse=True)

        # Top 5
        top_5 = scored_submissions[:5]

        # Build response
        embed = discord.Embed(title="Top 5 Event Submissions", description=f"Submissions after {date}", color=0x00ff00)
        for i, (thread, score) in enumerate(top_5, 1):
            embed.add_field(name=f"{i}. {thread.name}", value=f"Score: {score}\n[Link]({thread.jump_url})", inline=False)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(EventUtils(bot))
