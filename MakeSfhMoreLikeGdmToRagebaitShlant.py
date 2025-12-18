from asyncio.log import logger
import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from discord import app_commands
import logging






# ----------------------- SUPABASE SETUP -----------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

# ----------------------- HELPERS -----------------------
def fetch_imitations():
    try:
        response = supabase.table("imitations").select("*").execute()

        data = response.data or []
        imitations = {}
        for row in data:
            name = row.get("name")
            quotes = row.get("imitations") or []
            if isinstance(quotes, str):
                import json
                try:
                    quotes = json.loads(quotes)
                except Exception:
                    quotes = [quotes]
            imitations[name] = quotes
        return imitations
    except Exception as e:
        logger.exception(f"Failed to fetch imitations: {e}")
        return {}

def fetch_points():
    """Fetch user points from Supabase."""
    try:
        response = supabase.table("points").select("*").execute()
        data = response.data or []
        points = {}
        for row in data:
            user_id = str(row.get("user_id"))
            points[user_id] = {
                "name": row.get("name", "Unknown#0000"),
                "points": int(row.get("points", 0))
            }
        return points
    except Exception as e:
        logger.exception(f"Failed to fetch points: {e}")
        return {}

def save_points(points):
    """Upsert (update or insert) all points into Supabase."""
    try:
        payload = [
            {"user_id": uid, "name": data["name"], "points": data["points"]}
            for uid, data in points.items()
        ]
        supabase.table("points").upsert(payload, on_conflict="user_id").execute()
    except Exception as e:
        logger.exception(f"Failed to save points: {e}")





class AttachmentReactor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_channel_id = 1079516597506551928 

       
        self.upvote_emoji = discord.PartialEmoji(name="upvote", id=974675635861598218)
        self.downvote_emoji = discord.PartialEmoji(name="downvote", id=974675713519153193)

  
        self.blocked_emojis = {
            str(self.upvote_emoji),   
            str(self.downvote_emoji), 
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
        
        await message.add_reaction(self.upvote_emoji)
        await message.add_reaction(self.downvote_emoji)
        await message.add_reaction("🔥")
        await message.add_reaction("🔇")

 # --- Add points when someone upvotes an audio message ---
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        message = reaction.message


        if user.bot:
            return


        if message.channel.id != self.target_channel_id:
            return
        
        if message.author.id == 1279417773013078098 and user.id == 1341476810747023452:
             return
            


        if str(reaction.emoji) == str(self.upvote_emoji) and user.id != message.author.id:
            points = fetch_points()

            author_id = str(message.author.id)
            author_name = str(message.author)
            save_points(points)

            if author_id not in points:
                points[author_id] = {"name": author_name, "points": 0}


            points[author_id]["points"] += 3
            points[author_id]["name"] = author_name

 
            save_points(points)
            return


        if str(reaction.emoji) == str(self.downvote_emoji) and user.id != message.author.id:
            points = fetch_points()

            author_id = str(message.author.id)
            author_name = str(message.author)

 
            if author_id not in points:
                points[author_id] = {"name": author_name, "points": 0}


            points[author_id]["points"] -= 3
            points[author_id]["name"] = author_name


            save_points(points)
            return


        if str(reaction.emoji) == ("🔥") and user.id != message.author.id:
            points = fetch_points()

            author_id = str(message.author.id)
            author_name = str(message.author)


            if author_id not in points:
                points[author_id] = {"name": author_name, "points": 0}


            points[author_id]["points"] += 7
            points[author_id]["name"] = author_name

            save_points(points)
            return
        

        if str(reaction.emoji) == ("🔇") and user.id != message.author.id:
            points = fetch_points()

            author_id = str(message.author.id)
            author_name = str(message.author)


            if author_id not in points:
                points[author_id] = {"name": author_name, "points": 0}


            points[author_id]["points"] -= 7
            points[author_id]["name"] = author_name


            save_points(points)
            return

async def setup(bot):
    await bot.add_cog(AttachmentReactor(bot))
