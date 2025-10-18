import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
import logging
import os
from dotenv import load_dotenv
from supabase import create_client, Client

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

GUILD_ID = 1411767823730085971

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
    """Upsert (update or insert) all points into Supabase with ints."""
    try:
        payload = [
            {"user_id": uid, "name": data["name"], "points": int(data["points"])}
            for uid, data in points.items()
        ]
        if payload:
            supabase.table("points").upsert(payload, on_conflict="user_id").execute()
    except Exception as e:
        logger.exception(f"Failed to save points: {e}")

# ----------------------- MAIN COG -----------------------
class Imitate(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_game = None
        self.active_task = None

        self.imitations = fetch_imitations()
        self.points = fetch_points()
        self.imitations_lower = {k.lower(): v for k, v in self.imitations.items()}

    # ---------------- Autocomplete ----------------
    async def keyword_autocomplete(self, interaction: discord.Interaction, current: str):
        matches = [key for key in self.imitations.keys() if current.lower() in key.lower()]
        return [app_commands.Choice(name=match, value=match) for match in matches[:25]]

    # ---------------- /imitate ----------------
    @app_commands.command(name="imitate", description="Imitate an SFH person")
    @app_commands.describe(keyword="Pick who to imitate")
    @app_commands.autocomplete(keyword=keyword_autocomplete)
    async def imitate(self, interaction: discord.Interaction, keyword: str):
        if keyword.lower() not in self.imitations_lower:
            await interaction.response.send_message("❌ That person isn't cool enough to be made fun of", ephemeral=True)
            return

        imitation = random.choice(self.imitations_lower[keyword.lower()])

        while "RANDOM_KEYWORD_NAME" in imitation:
            other_keywords = [k for k in self.imitations.keys() if k.lower() != keyword.lower()]
            replacement = random.choice(other_keywords) if other_keywords else "someone"
            imitation = imitation.replace("RANDOM_KEYWORD_NAME", replacement, 1)

        await interaction.response.send_message(imitation)

    # ---------------- /imitate_game ----------------
    @app_commands.command(name="imitate_game", description="Start an imitation game")
    async def imitate_game(self, interaction: discord.Interaction):
        if self.active_game:
            await interaction.response.send_message("A game is already active!", ephemeral=True)
            return

        keyword = random.choice(list(self.imitations.keys()))
        imitation = random.choice(self.imitations[keyword])

        while "RANDOM_KEYWORD_NAME" in imitation:
            other_keywords = [k for k in self.imitations.keys() if k != keyword]
            replacement = random.choice(other_keywords) if other_keywords else "someone"
            imitation = imitation.replace("RANDOM_KEYWORD_NAME", replacement, 1)

        self.active_game = {"keyword": keyword.lower(), "channel": interaction.channel, "start_time": None}
        await interaction.response.send_message(f"Guess who said this:\n\n{imitation}\n\n")
        self.active_game["start_time"] = asyncio.get_event_loop().time()
        self.active_task = asyncio.create_task(self._end_game_after_delay(interaction.channel, keyword))

    async def _end_game_after_delay(self, channel, keyword):
        try:
            await asyncio.sleep(30)
            if self.active_game:
                await channel.send(f"⏰ Time's up! Nobody guessed correctly. The answer was **{keyword}**.")
                self.active_game = None
                self.active_task = None
        except discord.NotFound:
            self.active_game = None
            self.active_task = None

    # ---------------- Message Listener ----------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.active_game or message.author.bot:
            return
        if message.channel != self.active_game["channel"]:
            return

        guess = message.content.strip().lower()
        user_id = str(message.author.id)
        username = str(message.author)

        if guess not in self.imitations_lower:
            return

        if guess == self.active_game["keyword"]:
            total_time = 30
            elapsed = asyncio.get_event_loop().time() - self.active_game["start_time"]
            time_left = max(0, total_time - elapsed)
            points_awarded = max(1, round(time_left / 6))

            if user_id not in self.points:
                self.points[user_id] = {"name": username, "points": 0}

            self.points[user_id]["points"] += points_awarded
            self.points[user_id]["name"] = username
            save_points(self.points)
            self.points = fetch_points()

            await message.reply(f"✅ You won! You now have {self.points[user_id]['points']} Slop Points. (+{points_awarded})")
            self.active_game = None
            if self.active_task:
                self.active_task.cancel()
                self.active_task = None
        else:
            if user_id not in self.points:
                self.points[user_id] = {"name": username, "points": 0}
            self.points[user_id]["points"] -= 1
            save_points(self.points)
            self.points = fetch_points()
            try:
                await message.add_reaction("❌")
            except discord.Forbidden:
                pass

    # ---------------- /imitate_points ----------------
    @app_commands.command(name="imitate_points", description="Check your Slop Points")
    async def imitate_points(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data = self.points.get(user_id, {"name": str(interaction.user), "points": 0})
        await interaction.response.send_message(f"You have {data['points']} points.")

    # ---------------- /imitate_leaderboard ----------------
    @app_commands.command(name="imitate_leaderboard", description="Show the Slop Points leaderboard")
    async def imitate_leaderboard(self, interaction: discord.Interaction):
        if not self.points:
            await interaction.response.send_message("No one has any Slop Points yet!", ephemeral=True)
            return

        sorted_users = sorted(self.points.items(), key=lambda item: item[1]["points"], reverse=True)
        embed = discord.Embed(title="🏆 Slop Points Leaderboard", color=discord.Color.gold())

        for rank, (uid, data) in enumerate(sorted_users[:10], start=1):
            embed.add_field(name=f"#{rank} – {data['name']}", value=f"{data['points']} points", inline=False)

        await interaction.response.send_message(embed=embed)

    # ---------------- /reload_data ----------------
    @app_commands.command(name="reload_data", description="Reload imitation and points data from Supabase")
    async def reload_data(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.imitations = fetch_imitations()
        self.imitations_lower = {k.lower(): v for k, v in self.imitations.items()}
        self.points = fetch_points()
        await interaction.followup.send("✅ Reloaded imitation data and points from Supabase!")

# ----------------------- Setup -----------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Imitate(bot))
