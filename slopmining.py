import discord
from discord import app_commands
from discord.ext import commands
import os
import random
from supabase import create_client, Client
from dotenv import load_dotenv

# ---------------------- SUPABASE INIT ----------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

OWNER_IDS = ["1279417773013078098", "1117143387695497278", "703364595321929730"]

# ---------------------- POINTS HELPERS ----------------------
def fetch_points():
    """Load all points from Supabase (normalize to ints)."""
    res = supabase.table("points").select("*").execute()
    points = {}
    for row in (res.data or []):
        points[str(row["user_id"])] = {
            "name": row.get("name", "Unknown"),
            "points": int(row.get("points", 0))
        }
    return points

def save_points(points: dict):
    """Upsert points to Supabase (store ints)."""
    payload = []
    for user_id, info in points.items():
        payload.append({
            "user_id": user_id,
            "name": info.get("name", "Unknown"),
            "points": int(info.get("points", 0))
        })
    if payload:
        supabase.table("points").upsert(payload).execute()

# cog
class SlopMining(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.points = fetch_points()
    
    @app_commands.command(name="slopmine", description="Mine some Slop Points!")
    async def slopmine(self, interaction: discord.Interaction):
        self.points = fetch_points()
        user_id = str(interaction.user.id)

        if random.randint(1, 1000) == 1:
            self.points[user_id]["points"] += 5000
            await interaction.response.send_message("You just won the slop lottery, you have received 5000 Slop Points")
            save_points(self.points)
            return
        
        outcome = random.randint(1, 100)
        if outcome <= 20:
            earned = random.randint(1, 3)
        elif outcome <= 40:
            earned = random.randint(4, 10)
        elif outcome <= 60:
            earned = random.randint(11, 50)
        elif outcome <= 80:
            earned = random.randint(51, 200)
        elif outcome <= 90:
            earned = random.randint(201, 500)
        elif outcome <= 95:
            earned = random.randint(501, 1000)
        elif outcome <= 99:
            earned = random.randint(1001, 2000)
        else:
            earned = 5000
        self.points[user_id]["points"] += earned
        await interaction.response.send_message(f"You mined {earned} Slop Points, you have {self.points[user_id]['points']} Slop Points.")
        save_points(self.points)
        return
    
# cog loader
async def setup(bot: commands.Bot):
    await bot.add_cog(SlopMining(bot))
