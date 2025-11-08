# Find_Key.py
import discord
from discord import app_commands
from discord.ext import commands
import os
import re
from difflib import get_close_matches
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing SUPABASE_URL or SERVICE_ROLE_KEY in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Table names ---
GDSONG_TABLE = "gdsongdata"
NONGDSONG_TABLE = "nongdsongdata"


# --- Loaders ---
def load_songdata():
    """Fetch songs from both tables, formatted as '(Author) - (Title)'."""
    combined = {}

    try:
        gd_res = supabase.table(GDSONG_TABLE).select("*").execute()
        nongd_res = supabase.table(NONGDSONG_TABLE).select("*").execute()
        all_data = (gd_res.data or []) + (nongd_res.data or [])

        for row in all_data:
            title = row.get("title")
            author = row.get("author") or "Unknown Artist"
            if not title:
                continue

            # Use parentheses around author and title as requested
            full_name = f"({author}) - ({title})"
            combined[full_name] = {
                "title": title,
                "author": author,
                "bpm": row.get("bpm"),
                "key": row.get("key_signature"),
                "time_signature": row.get("time_signature"),
                "changes": row.get("changes") or [],
            }

        print(f"✅ Loaded {len(combined)} songs from Supabase.")
    except Exception as e:
        print(f"⚠️ Failed to fetch song data from Supabase: {e}")

    return combined


songdata = load_songdata()


# --- Cog ---
class FindKey(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- Helpers ----------
    @staticmethod
    def _norm(s: str) -> str:
        """Normalize for matching."""
        s = s.lower()
        s = re.sub(r"[^a-z0-9\s]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _best_suggestions(query: str, names, n=25):
        """Return fuzzy + substring matches."""
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
        """Find best match among '(Author) - (Title)' keys and by title-only / author-title input."""
        if not query:
            return None, None

        # Exact match (including parentheses)
        if query in names:
            return query, None

        # Case-insensitive exact full-key match
        lower_map = {name.lower(): name for name in names}
        if query.lower() in lower_map:
            corrected = lower_map[query.lower()]
            return corrected, f"Matched case-insensitive → **{corrected}**"

        q_norm = self._norm(query)

        # If user provided "author - title" without parentheses, try to match both author and title
        if "-" in query:
            parts = [p.strip() for p in query.split("-", 1)]
            if len(parts) == 2:
                left_norm, right_norm = self._norm(parts[0]), self._norm(parts[1])
                for name in names:
                    info = songdata.get(name, {})
                    if self._norm(info.get("author", "")) == left_norm and self._norm(info.get("title", "")) == right_norm:
                        return name, f"Matched author and title → **{name}**"

        # Title-only exact normalized match (useful when user types only the song name)
        title_matches = [name for name in names if self._norm(songdata.get(name, {}).get("title", "")) == q_norm]
        if len(title_matches) == 1:
            return title_matches[0], f"Matched song title → **{title_matches[0]}**"

        # Unique substring match (checks both full key and title)
        subs = [name for name in names if query.lower() in name.lower() or q_norm in self._norm(songdata.get(name, {}).get("title", ""))]
        if len(subs) == 1:
            return subs[0], f"Unique substring match → **{subs[0]}**"

        # Fallback to fuzzy match on full keys
        fuzzy = get_close_matches(query, names, n=1, cutoff=0.6)
        if fuzzy:
            return fuzzy[0], f"No exact match. Closest → **{fuzzy[0]}**"

        return None, None

    # ---------- Autocomplete ----------
    async def song_autocomplete(self, interaction: discord.Interaction, current: str):
        names = list(songdata.keys())
        suggestions = self._best_suggestions(current, names, n=25)
        return [app_commands.Choice(name=name, value=name) for name in suggestions]

    # ---------- Command ----------
    @app_commands.command(name="find_key", description="Get the key, BPM, and time signature of a song")
    @app_commands.describe(song="Enter 'Artist - Song' or just the song name")
    @app_commands.autocomplete(song=song_autocomplete)
    async def find_key(self, interaction: discord.Interaction, song: str):
        names = list(songdata.keys())
        chosen, reason = self._autocorrect_title(song, names)

        if not chosen:
            suggestions = self._best_suggestions(song, names, n=10)
            if suggestions:
                await interaction.response.send_message(
                    f"❌ No exact match for `{song}`.\nDid you mean: " +
                    ", ".join(f"`{s}`" for s in suggestions[:5]) + "?",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"❌ No results for `{song}`.",
                    ephemeral=True,
                )
            return

        song_info = songdata.get(chosen, {})
        bpm = song_info.get("bpm", "Unknown")
        key = song_info.get("key", "Unknown")
        time_sig = song_info.get("time_signature")
        author = song_info.get("author", "Unknown Artist")
        title = song_info.get("title", chosen)

        # Use the requested formatting: (song author) - (song name)
        header = f"🎵 **{author} - {title}**"
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

        await interaction.response.send_message(msg)


# ---------- setup ----------
async def setup(bot: commands.Bot):
    await bot.add_cog(FindKey(bot))
    print(f"✅ Find_Key cog loaded — {len(songdata)}")
