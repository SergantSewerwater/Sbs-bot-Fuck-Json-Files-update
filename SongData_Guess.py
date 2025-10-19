import os
import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
import math
from supabase import create_client, Client
from dotenv import load_dotenv
import time

TEST_SERVER_ID = 1411767823730085971

# ---------------------- SUPABASE INIT ----------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

# ---------------------- DATA FETCHERS ----------------------
def fetch_points():
    """Load all user points from Supabase"""
    res = supabase.table("points").select("*").execute()
    points = {}
    for row in res.data or []:
        user_id = str(row["user_id"])
        points[user_id] = {"name": row.get("name", "Unknown"), "points": row.get("points", 0)}
    return points

def save_points(points):
    """Push updated points back to Supabase"""
    payload = []
    for user_id, info in points.items():
        payload.append({
            "user_id": user_id,
            "name": info.get("name", "Unknown"),
            "points": math.ceil(info.get("points", 0))
        })
    if payload:
        supabase.table("points").upsert(payload, on_conflict="user_id").execute()

def fetch_songdata(table_name: str):
    """Fetch song data from the specified Supabase table"""
    res = supabase.table(table_name).select("*").execute()
    songs = {}
    for row in res.data or []:
        title = row.get("title")
        if not title:
            continue
        songs[title] = {
            "bpm": row.get("bpm"),
            "key": row.get("key_signature"),
            "author": row.get("author"),
            "difficulty": row.get("difficulty") or "Unknown",
            "changes": row.get("changes") or [],
        }
    # optional debug:
    # print(f"Fetched {len(songs)} songs from {table_name}")
    return songs

# ---------------------- MAIN COG ----------------------
class SongDataGuess(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games = {}  # channel_id -> dict

    async def _run_guess_game(self, interaction: discord.Interaction, table_name: str, label: str):
        songdata = fetch_songdata(table_name)
        candidates = [s for s, v in songdata.items() if v.get("key") and v.get("bpm")]
        if not candidates:
            await interaction.response.send_message(f"No songs with key and BPM info found in {label}.", ephemeral=True)
            return

        song = random.choice(candidates)
        key = songdata[song]["key"].strip().lower()
        bpm = str(int(float(songdata[song]["bpm"])))
        author = songdata[song].get("author", "Unknown")
        difficulty_val = songdata[song].get("difficulty", "Unknown")

        channel_id = interaction.channel.id
        if channel_id in self.active_games:
            await interaction.response.send_message("Don't play multiple games at once!", ephemeral=True)
            return

        # register active game
        self.active_games[channel_id] = {"song": song, "key": key, "bpm": bpm, "answered": False}
        await interaction.response.send_message(
            f"🎵 Guess the key and BPM for: **{author} - {song}**! Difficulty: **{difficulty_val}**\n"
            f"Type both the key and BPM in chat within 30 seconds."
        )

        valid_modes = ["major", "minor", "phrygian", "dorian", "mixolydian",
                       "blues", "altered", "super locrian", "lydian", "locrian"]
        notes = ["a", "b", "c", "d", "e", "f", "g"]
        accidentals = ["#", "b", "♭", "♯"]

        def extract_bpm(content: str):
            import re
            nums = re.findall(r"\b\d+\b", content)
            return nums[0] if nums else None

        def extract_key(content: str):
            c = content.lower()
            for note in notes:
                for acc in [""] + accidentals:
                    for mode in valid_modes:
                        form = f"{note}{acc} {mode}"
                        if form in c:
                            return form
            return None

        start_time = time.monotonic()
        points = fetch_points()

        async def handle_message(msg: discord.Message):
            # only consider messages in same channel and not from bots
            if msg.channel.id != channel_id or msg.author.bot:
                return

            content = msg.content.lower()
            guessed_bpm = extract_bpm(content)
            guessed_key = extract_key(content)
            if not guessed_bpm and not guessed_key:
                return

            user_id = str(msg.author.id)
            if user_id not in points:
                points[user_id] = {"name": msg.author.name, "points": 0}

            correct_bpm = guessed_bpm == bpm
            correct_key = guessed_key == key

            if guessed_bpm and guessed_key:
                if correct_bpm and correct_key:
                    if not self.active_games[channel_id]["answered"]:
                        self.active_games[channel_id]["answered"] = True
                        elapsed = time.monotonic() - start_time
                        try:
                            await msg.add_reaction("✅")
                        except discord.Forbidden:
                            pass
                        # call end_round method on this cog
                        await self.end_round(interaction, msg, song, key, bpm, difficulty_val, elapsed, table_name)
            else:
                # penalize guesses that are invalid (optional)
                points[user_id]["points"] -= 1
                save_points(points)
                try:
                    await msg.add_reaction("❌")
                except discord.Forbidden:
                    pass

        # add listener, sleep for the round duration, then cleanup
        self.bot.add_listener(handle_message, "on_message")
        try:
            await asyncio.sleep(30)
            if not self.active_games[channel_id]["answered"]:
                await interaction.channel.send(f"⏰ Time's up! Correct answer: **Key: {key.upper()} | BPM: {bpm}**")
        finally:
            self.bot.remove_listener(handle_message, "on_message")
            self.active_games.pop(channel_id, None)

    async def end_round(self, interaction: discord.Interaction, msg: discord.Message, song: str, key: str, bpm: str, difficulty_val, elapsed: float, table_name: str):
        # fetch stored difficulty, fallback to "easy"
        try:
            response = supabase.table(table_name).select("difficulty").eq("title", song).execute()
            stored_difficulty = (
                response.data[0]["difficulty"].lower().strip()
                if response.data and response.data[0].get("difficulty")
                else "easy"
            )
        except Exception as e:
            print(f"⚠️ Failed to fetch difficulty from Supabase: {e}")
            stored_difficulty = "easy"

        max_points = {"easy": 5, "medium": 10, "hard": 15}.get(stored_difficulty, 5)
        points_awarded = max(1, round(max_points * ((30 - elapsed) / 30)))

        points = fetch_points()
        user_id = str(msg.author.id)
        if user_id not in points:
            points[user_id] = {"name": msg.author.name, "points": 0}

        points[user_id]["points"] += points_awarded
        save_points(points)

        await interaction.channel.send(
            f"✅ Correct! {msg.author.mention} gets **{points_awarded} Slop Point(s)**!\n"
            f"**Key:** {key.upper()} | **BPM:** {bpm}\n"
            f"*(Based on stored difficulty: {stored_difficulty})*"
        )

        # Ask whether to update difficulty (only message author may respond)
        await interaction.channel.send(
            "How difficult was this question? Reply with `easy`, `medium`, `hard`, or `none` to skip updating."
        )

        def diff_check(m: discord.Message):
            return (
                m.author.id == msg.author.id
                and m.channel.id == interaction.channel.id
                and m.content.lower().strip() in ["easy", "medium", "hard", "none"]
            )

        try:
            diff_msg = await self.bot.wait_for("message", timeout=15.0, check=diff_check)
            new_difficulty = diff_msg.content.lower().strip()
        except asyncio.TimeoutError:
            new_difficulty = "none"

        if new_difficulty != "none":
            supabase.table(table_name).update({"difficulty": new_difficulty}).eq("title", song).execute()
            await interaction.channel.send(f"✅ Difficulty updated to **{new_difficulty}** for **{song}**.")
        else:
            await interaction.channel.send("Difficulty change skipped.")

    # ---------------- app commands (slash) ----------------
    @app_commands.command(name="guess_gdsong_key", description="Guess the key and BPM of a random GD song")
    async def guess_gdsong_key(self, interaction: discord.Interaction):
        # fetch points is internal to the cog methods if needed
        await self._run_guess_game(interaction, "gdsongdata", "GD songs")

    @app_commands.command(name="guess_non_gdsong_key", description="Guess the key and BPM of a random non-GD song")
    async def guess_non_gdsong_key(self, interaction: discord.Interaction):
        await self._run_guess_game(interaction, "nongdsongdata", "Non-GD songs")

# ---------------------- SETUP ----------------------
async def setup(bot: commands.Bot):
    cog = SongDataGuess(bot)
    await bot.add_cog(cog)


