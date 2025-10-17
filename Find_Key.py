# Find_Key.py
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import re
from difflib import get_close_matches
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SERVICE_ROLE_KEY")  # safer via .env

# --- Create Supabase client ---
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing SUPABASE_URL or SERVICE_ROLE_KEY in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Table names ---
GDSONG_TABLE = "gdsongdata"       # must match your Supabase table name exactly
NONGDSONG_TABLE = "nongdsongdata"  # adjust if your table uses different name casing


# --- Loaders ---
def load_songdata():
    """Fetch both GD and Non-GD song data from Supabase safely."""
    combined = {}

    try:
        gd_res = supabase.table(GDSONG_TABLE).select("*").execute()
        nongd_res = supabase.table(NONGDSONG_TABLE).select("*").execute()
        gd_data = gd_res.data or []
        nongd_data = nongd_res.data or []

        for row in gd_data + nongd_data:
            title = row.get("title")
            if not title:
                continue
            combined[title] = {
                "bpm": row.get("bpm"),
                "key": row.get("key_signature"),
                "author": row.get("author"),
                "time_signature": row.get("time_signature"),
                "changes": row.get("changes") or []
            }

        print(f"✅ Loaded {len(combined)} total songs from Supabase.")
    except Exception as e:
        print(f"⚠️ Failed to fetch song data from Supabase: {e}")
        import traceback
        traceback.print_exc()

    return combined


# --- Load data at startup ---
songdata = load_songdata()


class FindKey(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- helpers ----------
    @staticmethod
    def _norm(s: str) -> str:
        """Normalize strings for matching."""
        s = s.lower()
        s = re.sub(r"[^a-z0-9\s]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _best_suggestions(query: str, names, n=25):
        """Return up to n suggestions combining substring + fuzzy matches."""
        if not query:
            return list(names)[:n]

        norm_query = FindKey._norm(query)
        sub_matches = [name for name in names if norm_query in FindKey._norm(name)]
        fuzzy_matches = get_close_matches(query, names, n=n, cutoff=0.3)

        seen = set()
        merged = []
        for lst in (sub_matches, fuzzy_matches):
            for name in lst:
                if name not in seen:
                    seen.add(name)
                    merged.append(name)
                if len(merged) >= n:
                    break
            if len(merged) >= n:
                break
        return merged

    def _autocorrect_title(self, query: str, names):
        """Return (chosen_name, reason_str) or (None, None) if no confident match."""
        if query in names:
            return query, None

        lower_map = {name.lower(): name for name in names}
        if query.lower() in lower_map:
            corrected = lower_map[query.lower()]
            return corrected, f"Matched case-insensitive to **{corrected}**"

        subs = [name for name in names if query.lower() in name.lower()]
        if len(subs) == 1:
            return subs[0], f"Unique substring match → **{subs[0]}**"

        fuzzy = get_close_matches(query, names, n=1, cutoff=0.6)
        if fuzzy:
            return fuzzy[0], f"No exact match. Using closest match → **{fuzzy[0]}**"

        return None, None

    # ---------- autocomplete ----------
    async def song_autocomplete(self, interaction: discord.Interaction, current: str):
        names = list(songdata.keys())
        suggestions = self._best_suggestions(current, names, n=25)
        return [app_commands.Choice(name=name, value=name) for name in suggestions]

    # ---------- command ----------
    @app_commands.command(
        name="find_key",
        description="Get the key, BPM, and time signature of a song"
    )
    @app_commands.describe(song="The name of the song")
    @app_commands.autocomplete(song=song_autocomplete)
    async def find_key(self, interaction: discord.Interaction, song: str):
        names = list(songdata.keys())
        chosen, reason = self._autocorrect_title(song, names)

        if not chosen:
            suggestions = self._best_suggestions(song, names, n=10)
            if suggestions:
                await interaction.response.send_message(
                    f"❌ No match for '{song}'. Did you mean: " +
                    ", ".join(f"`{s}`" for s in suggestions) + "?",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ No song found for '{song}'.",
                    ephemeral=True
                )
            return

        song_info = songdata.get(chosen, {})
        bpm = song_info.get("bpm", "Unknown")
        key = song_info.get("key", "Unknown")
        time_sig = song_info.get("time_signature")
        author = song_info.get("author")

        header = f"🎵 **{chosen}**"
        if author:
            header += f" *(by {author})*"
        if reason:
            header += f"\n_{reason}_"

        msg = header + f"\n- **BPM:** {bpm}\n- **Key:** {key}"
        if time_sig:
            msg += f"\n- **Time Signature:** {time_sig}"

        changes = song_info.get("changes", [])
        if changes:
            msg += "\n**Changes:**"
            for ch in changes:
                if "bpm" in ch:
                    msg += f"\n> {ch['time']} → {ch['bpm']} BPM"
                if "key" in ch:
                    msg += f"\n> {ch['time']} → {ch['key']}"

        await interaction.response.send_message(msg, ephemeral=False)


# ---------- setup ----------
async def setup(bot: commands.Bot):
    try:
        await bot.add_cog(FindKey(bot))
        print(
            f"✅ Find_Key cog loaded — {len(songdata)} songs available "
            f"(fuzzy autocomplete + autocorrect enabled)"
        )
    except Exception as e:
        print(f"❌ Failed to load Find_Key cog: {e}")
        import traceback
        traceback.print_exc()
