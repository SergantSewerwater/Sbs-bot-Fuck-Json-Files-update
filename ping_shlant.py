import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import random
from supabase import create_client, Client
from dotenv import load_dotenv
from Find_Key import songdata

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

# the cog or something idk
class PingShlant(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.points = fetch_points()
    
    # literally just pings shlant
    @app_commands.command(name="ping_shlant", description="Pings Shlant. yea that's it")
    async def ping_shlant(self, interaction: discord.Interaction):
        self.points = fetch_points()
        user_id = str(interaction.user.id)

        if random.randint(1, 1000) == 1:
            self.points[user_id]["points"] += 5000
            await interaction.response.send_message("You just won the slop lottery, you have received 5000 Slop Points")
            save_points(self.points)
            return
        
        if random.randint(1, 20) == 1:
            await interaction.response.send_message(f"<@1435850784410701835>")
            return

        await interaction.response.send_message(f"<@530140140211798016>")
        return
    
    @app_commands.command(name="self_ban", description="ban yourslef")
    async def self_ban(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        songs_174 = [name for name, data in songdata.items() if data.get("bpm") == 174]
        
        if songs_174:
            message = "Songs with 174 BPM:\n" + "\n".join(songs_174)
            try:
                await interaction.user.send(message)
                await interaction.followup.send("DM sent with 174 BPM songs!")
            except discord.Forbidden:
                await interaction.followup.send("I couldn't DM you. Please enable DMs from server members.")
        else:
            await interaction.followup.send("No songs found with 174 BPM.")

# cog loader
async def setup(bot: commands.Bot):
    await bot.add_cog(PingShlant(bot))
