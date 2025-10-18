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
    """Load all points from Supabase"""
    res = supabase.table("points").select("*").execute()
    points = {}
    for row in res.data:
        points[str(row["user_id"])] = {
            "name": row.get("name", "Unknown"),
            "points": float(row.get("points", 0))
        }
    return points

def save_points(points: dict):
    """Upsert points to Supabase"""
    for user_id, info in points.items():
        supabase.table("points").upsert({
            "user_id": user_id,
            "name": info.get("name", "Unknown"),
            "points": math.ceil(info.get("points", 0))
        }).execute()


# ---------------------- GAMBLING COG ----------------------
class Gambling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="gamble", description="LET'S GO GAMBLING!!!!!")
    @app_commands.describe(points="How many Slop Points to gamble", color="Choose red, black, or green")
    async def gamble(self, interaction: discord.Interaction, points: int, color: str):
        if points < 0:
            await interaction.response.send_message("You cannot gamble a negative amount of Slop Points.")
            return

        user_id = str(interaction.user.id)
        all_points = fetch_points()

        if user_id in OWNER_IDS:
            await interaction.response.send_message("Ur in the 1% dont gamble away your riches bro")
            return

        if user_id not in all_points or all_points[user_id]["points"] <= 0:
            await interaction.response.send_message("Broke bitch.")
            return

        if all_points[user_id]["points"] - points < 0:
            await interaction.response.send_message("You can't gamble into debt.")
            return

        if points == 0:
            await interaction.response.send_message("This idiot just tried to gamble 0 slop points 🤣")
            return

        if color not in ['red', 'black', 'green']:
            await interaction.response.send_message("Imagine making up a colour name of all things 🤣")
            return

        outcome = random.choices(['red', 'black', 'green'], weights=[49.5, 49.5, 1], k=1)[0]

        if outcome == color:
            winnings = points * 4 if color == 'green' else points * 2
            # Deduct proportionally from owners with enough points
            payers = [oid for oid in OWNER_IDS if all_points.get(oid, {}).get("points", 0) >= winnings / len(OWNER_IDS)]
            if payers:
                for oid in payers:
                    all_points[oid]["points"] -= winnings / len(payers)
                all_points[user_id]["points"] += winnings
                await interaction.response.send_message(
                    f"You won! You now have {all_points[user_id]['points']} Slop Points."
                )
            else:
                await interaction.response.send_message("The banks have run out of money.")
        else:
            # Deduct losses proportionally from owners
            losers = [oid for oid in OWNER_IDS if all_points.get(oid, {}).get("points", 0) > 0]
            if losers:
                for oid in losers:
                    loss_per_owner = points / len(losers)
                    all_points[oid]["points"] -= loss_per_owner
            all_points[user_id]["points"] -= points
            await interaction.response.send_message(
                f"You lost! You now have {all_points[user_id]['points']} Slop Points."
            )

        save_points(all_points)


# ---------------------- SETUP ----------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Gambling(bot))
