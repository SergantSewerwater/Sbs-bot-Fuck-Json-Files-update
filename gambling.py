import math
import random
import os
import discord
from discord import app_commands
from discord.ext import commands
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


# ---------------------- GAMBLING COG ----------------------
class Gambling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.all_points = fetch_points()

    @app_commands.command(name="gamble", description="LET'S GO GAMBLING!!!!!")
    @app_commands.describe(points="How many Slop Points to gamble", color="Choose red, black, or green")
    async def gamble(self, interaction: discord.Interaction, points: int, color: str):
        self.all_points = fetch_points()
        if points < 0:
            await interaction.response.send_message("You cannot gamble a negative amount of Slop Points.")
            return

        user_id = str(interaction.user.id)

        if user_id not in self.all_points or self.all_points[user_id]["points"] <= 0:
            await interaction.response.send_message("Broke bitch.")
            return

        if self.all_points[user_id]["points"] - points < 0:
            await interaction.response.send_message("You can't gamble into debt.")
            return

        if points == 0:
            await interaction.response.send_message("This idiot just tried to gamble 0 slop points 🤣")
            return

        if color not in ['red', 'black', 'green']:
            await interaction.response.send_message("Imagine making up a colour name of all things 🤣")
            return

        outcome = random.choices(['red', 'black', 'green'], weights=[49.5, 49.5, 1], k=1)[0]

        change = points * 4 if color == outcome and color == "green" else points if color == outcome else -points

        if user_id in OWNER_IDS:
            users = [id for id in self.all_points if id not in OWNER_IDS]
            for id in users:
                self.all_points[id]["points"] -= change // len(users)
            self.all_points[user_id]["points"] += change
        else:
            for oid in OWNER_IDS:
                self.all_points[oid]["points"] -= change // 3
            self.all_points[user_id]["points"] += change
        result = "won" if change > 0 else "lost"
        await interaction.response.send_message(
            f"You {result}! You now have {self.all_points[user_id]['points']} Slop Points."
        )

        save_points(self.all_points)


# ---------------------- SETUP ----------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Gambling(bot))
