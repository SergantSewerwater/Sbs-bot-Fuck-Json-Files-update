import discord
from discord import app_commands
from discord.ext import commands
from difflib import get_close_matches
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

# === Data ===
keys = [
    ["C Major", "Db Major", "D Major", "Eb Major", "E Major", "F Major", "F# Major", "G Major","Ab Major", "A Major", "Bb Major", "B Major"],
    ["A Minor", "Bb Minor", "B Minor", "C Minor", "C# Minor", "D Minor", "D# Minor", "E Minor", "F Minor", "F# Minor", "G Minor", "G# Minor"],
    ["G Mixolydian","Ab Mixolydian", "A Mixolydian", "Bb Mixolydian", "B Mixolydian", "C Mixolydian", "C# Mixolydian", "D Mixolydian", "Eb Mixolydian", "E Mixolydian", "F Mixolydian", "F# Mixolydian"],
    ["D Dorian", "Eb Dorian", "E Dorian", "F Dorian", "F# Dorian", "G Dorian", "G# Dorian","A Dorian", "Bb Dorian", "B Dorian", "C Dorian", "C# Dorian"],
    ["E Phrygian", "F Phrygian", "F# Phrygian", "G Phrygian", "G# Phrygian","A Phrygian", "A# Phrygian", "B Phrygian", "C Phrygian", "C# Phrygian", "D Phrygian", "D# Phrygian"],
    ["F Lydian", "Gb Lydian", "G Lydian","Ab Lydian", "A Lydian", "Bb Lydian", "B Lydian", "C Lydian", "Db Lydian", "D Lydian", "Eb Lydian", "E Lydian"],
    ["B Locrian", "C Locrian", "C# Locrian", "D Locrian", "D# Locrian", "E Locrian", "F Locrian", "F# Locrian", "G Locrian", "G# Locrian","A Locrian", "A# Locrian"]
]

enharmony = {
    "Db Major": "C# Major", "Eb Major": "D# Major", "Gb Major": "F# Major",
    "Ab Major": "G# Major", "Bb Major": "A# Major",
    "Bb Minor": "A# Minor", "Db Minor": "C# Minor", "Eb Minor": "D# Minor",
    "Gb Minor": "F# Minor", "Ab Minor": "G# Minor",
    "Ab Mixolydian": "G# Mixolydian", "Bb Mixolydian": "A# Mixolydian",
    "Db Mixolydian": "C# Mixolydian", "Eb Mixolydian": "D# Mixolydian",
    "Gb Mixolydian": "F# Mixolydian",
    "Ab Dorian": "G# Dorian", "Bb Dorian": "A# Dorian", "Eb Dorian": "D# Dorian",
    "Gb Dorian": "F# Dorian", "Db Dorian": "C# Dorian",
    "Bb Phrygian": "A# Phrygian", "Eb Phrygian": "D# Phrygian",
    "Gb Phrygian": "F# Phrygian", "Ab Phrygian": "G# Phrygian",
    "Db Lydian": "C# Lydian", "Eb Lydian": "D# Lydian",
    "Gb Lydian": "F# Lydian", "Ab Lydian": "G# Lydian", "Bb Lydian": "A# Lydian",
    "Bb Locrian": "A# Locrian", "Db Locrian": "C# Locrian",
    "Eb Locrian": "D# Locrian", "Gb Locrian": "F# Locrian", "Ab Locrian": "G# Locrian"
}

# Normalize keys
def normalize_key(key: str) -> str:
    key_title = key.strip().title()
    return enharmony.get(key_title, key_title)

# Precompute normalized keys for lookup
normalized_keys = [[normalize_key(k) for k in mode] for mode in keys]

# Flatten all keys for fuzzy autocomplete
all_keys_flat = sorted({k for mode in normalized_keys for k in mode})

# ----------------- Semitone Calculation -----------------
def calculate_semitones(key_1: str, key_2: str) -> str:
    key_1_norm = normalize_key(key_1)
    key_2_norm = normalize_key(key_2)

    index_1 = index_2 = None
    for mode in normalized_keys:
        if index_1 is None and key_1_norm in mode:
            index_1 = mode.index(key_1_norm)
        if index_2 is None and key_2_norm in mode:
            index_2 = mode.index(key_2_norm)
        if index_1 is not None and index_2 is not None:
            break

    if index_1 is None and index_2 is None:
        return f"This idiot just made up 2 keys 🤣"
    elif index_1 is None:
        return f"Man idk what the fuck a '{key_1}' is"
    elif index_2 is None:
        return f"Man idk what the fuck a '{key_2}' is"

    diff = index_2 - index_1
    if diff == 0:
        return f"No pitching needed for {key_1_norm} and {key_2_norm}."

    if diff > 6:
        diff -= 12
    elif diff < -6:
        diff += 12
    diff_str = f"+{diff}" if diff > 0 else str(diff)

    if abs(diff) == 6:
        return f"You need to pitch {key_1_norm} ±6 semitones to get to {key_2_norm}."
    elif abs(diff) == 1:
        return f"You need to pitch {key_1_norm} {diff_str} semitone to get to {key_2_norm}."
    else:
        return f"You need to pitch {key_1_norm} {diff_str} semitones to get to {key_2_norm}."

# ----------------- Cog -----------------
class SemitoneCalculator(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.points = fetch_points()

    async def key_autocomplete(self, interaction: discord.Interaction, current: str):
        # Fuzzy autocomplete for keys (flats preferred).
        matches = get_close_matches(current.title(), all_keys_flat, n=25, cutoff=0.1)
        return [app_commands.Choice(name=m, value=m) for m in matches]

    @app_commands.command(
        name="semitone_calculator",
        description="Calculate semitone difference between two keys."
    )
    @app_commands.describe(
        key_from="The original key of the song",
        key_to="The target key to pitch to"
    )
    @app_commands.autocomplete(key_from=key_autocomplete, key_to=key_autocomplete)
    async def semitone_calculator(self, interaction: discord.Interaction, key_from: str, key_to: str):
        self.points = fetch_points()
        user_id = str(interaction.user.id)

        if random.randint(1, 1000) == 1:
            self.points[user_id]["points"] += 5000
            await interaction.response.send_message("You just won the slop lottery, you have received 5000 Slop Points")
            save_points(self.points)
            return

        result = calculate_semitones(key_from, key_to)
        await interaction.response.send_message(result)

async def setup(bot: commands.Bot):
    await bot.add_cog(SemitoneCalculator(bot))
