import discord
from discord import app_commands
from discord.ext import commands
from difflib import get_close_matches

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
    "C# Major": "Db Major", "D# Major": "Eb Major", "F# Major": "Gb Major",
    "G# Major": "Ab Major", "A# Major": "Bb Major",
    "A# Minor": "Bb Minor", "C# Minor": "Db Minor", "D# Minor": "Eb Minor",
    "F# Minor": "Gb Minor", "G# Minor": "Ab Minor",
    "G# Mixolydian": "Ab Mixolydian", "A# Mixolydian": "Bb Mixolydian",
    "C# Mixolydian": "Db Mixolydian", "D# Mixolydian": "Eb Mixolydian",
    "F# Mixolydian": "Gb Mixolydian",
    "G# Dorian": "Ab Dorian", "A# Dorian": "Bb Dorian", "D# Dorian": "Eb Dorian",
    "F# Dorian": "Gb Dorian", "C# Dorian": "Db Dorian",
    "A# Phrygian": "Bb Phrygian", "D# Phrygian": "Eb Phrygian",
    "F# Phrygian": "Gb Phrygian", "G# Phrygian": "Ab Phrygian",
    "C# Lydian": "Db Lydian", "D# Lydian": "Eb Lydian",
    "F# Lydian": "Gb Lydian", "G# Lydian": "Ab Lydian", "A# Lydian": "Bb Lydian",
    "A# Locrian": "Bb Locrian", "C# Locrian": "Db Locrian",
    "D# Locrian": "Eb Locrian", "F# Locrian": "Gb Locrian", "G# Locrian": "Ab Locrian"
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
        result = calculate_semitones(key_from, key_to)
        await interaction.response.send_message(result)

async def setup(bot: commands.Bot):
    await bot.add_cog(SemitoneCalculator(bot))
