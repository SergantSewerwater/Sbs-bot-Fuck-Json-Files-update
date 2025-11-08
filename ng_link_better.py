import os
import re
import random

import aiohttp
import logging
import discord
from discord import app_commands
from discord.ext import commands
from playwright.async_api import async_playwright
from supabase import create_client, Client
from dotenv import load_dotenv

# ---------------------- SUPABASE INIT ----------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

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

# --- Logging Configuration ---
logger = logging.getLogger("NewgroundsAudio")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class NewgroundsAudio(commands.Cog):
    """Cog for fetching and embedding Newgrounds audio files."""

    def __init__(self, bot):
        self.bot = bot
        self.temp_path = os.getenv("TEMP_AUDIO_PATH", "./temp_audio")
        os.makedirs(self.temp_path, exist_ok=True)
        logger.info(f"Initialized NewgroundsAudio cog with TEMP_AUDIO_PATH={self.temp_path}")
        self.points = fetch_points()

    @app_commands.command(
        name="ngaudio",
        description="Fetch and embed a Newgrounds song (from ID or URL)."
    )
    @app_commands.describe(
        input_value="Newgrounds audio ID or URL (e.g. 505813 or https://www.newgrounds.com/audio/listen/505813)",
        author="Song author (so it won't break if it changes on the site)",
        title="Song title (so it won't break if it changes on the site)"
    )
    async def ngaudio(self, interaction: discord.Interaction, input_value: str, author: str, title: str):
        """Slash command that fetches and embeds a Newgrounds song."""
        user_id = str(interaction.user.id)
        self.points = fetch_points()    

        if random.randint(1, 1000) == 1:
            self.points[user_id]["points"] += 5000
            await interaction.followup.send("You just won the slop lottery, you have received 5000 Slop Points")
            save_points(self.points)
            logger.info(f"User {interaction.user} won the slop lottery.")
            return
        
        logger.info(f"Command /ngaudio invoked by {interaction.user} with input: {input_value}")
        await interaction.response.defer(thinking=True)
        logger.info(f"/ngaudio invoked by {interaction.user} | input='{input_value}', author='{author}', title='{title}'")
        await interaction.response.defer(thinking=True)

        # --- Extract numeric ID from URL or input ---
        match = re.search(r"(\d+)", input_value)
        if not match:
            logger.warning(f"No valid audio ID found in input: {input_value}")
            await interaction.followup.send("❌ Could not find a valid audio ID in your input.")
            return

        audio_id = int(match.group(1))
        logger.info(f"Extracted Newgrounds audio ID: {audio_id}")

        # --- Try to fetch the CDN link ---
        link = await self.fetch_audio_ng_link(audio_id)
        if not link:
            logger.error(f"Failed to fetch audio.ng link for ID {audio_id}")
            await interaction.followup.send(f"❌ Could not find a valid audio.ng link for **{title}** by **{author}**.")
            return

        logger.info(f"Found CDN link for {audio_id}: {link}")

        filename = link.split("/")[-1].split("?")[0]
        file_path = os.path.join(self.temp_path, filename)

        # --- Attempt to download the file ---
        file_downloaded = False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(link) as resp:
                    if resp.status == 200:
                        with open(file_path, "wb") as f:
                            f.write(await resp.read())
                        file_downloaded = True
                        logger.info(f"Downloaded file to {file_path}")
                    else:
                        logger.warning(f"Failed to download file (HTTP {resp.status}) from {link}")
        except Exception as e:
            logger.exception(f"Error downloading {link}: {e}")

        # --- Build the embed ---
        embed = discord.Embed(
            title=f"🎵 {title}",
            description=f"By **{author}**\n[Listen on Newgrounds](https://www.newgrounds.com/audio/listen/{audio_id})",
            color=discord.Color.orange()
        )
        embed.add_field(name="Direct File", value=f"[{filename}]({link})")
        embed.set_footer(text="Fetched from Newgrounds CDN (audio.ngfiles.com)")
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/0/0a/Newgrounds_Logo.svg")

        # --- Send file if available, otherwise just the link ---
        try:
            if file_downloaded:
                file = discord.File(file_path, filename=filename)
                await interaction.followup.send(embed=embed, file=file)
                logger.info(f"Sent embed + file for {title} ({audio_id}) to Discord.")
            else:
                await interaction.followup.send(embed=embed)
                logger.info(f"Sent embed without file for {title} ({audio_id}) due to download failure.")
        except Exception as e:
            logger.exception(f"Error sending message to Discord: {e}")
            await interaction.followup.send(f"⚠️ Could not send file for **{title}**, but here's the link:\n{link}")

        # --- Cleanup downloaded file ---
        if file_downloaded:
            try:
                os.remove(file_path)
                logger.info(f"Deleted temporary file {file_path}")
            except Exception as e:
                logger.warning(f"Could not delete temporary file {file_path}: {e}")

    async def fetch_audio_ng_link(self, audio_id: int):
        """Fetch the direct audio.ngfiles.com link from a Newgrounds listen page using Playwright."""
        url = f"https://www.newgrounds.com/audio/listen/{audio_id}"
        logger.info(f"Fetching Newgrounds page for ID {audio_id}: {url}")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=15000)
                html = await page.content()
                await browser.close()

            match = re.search(r'https:\/\/audio\.ngfiles\.com\/\d+\/[^\s"\']+\.mp3\?f\d+', html)
            if match:
                return match.group(0)
            else:
                logger.warning(f"No CDN link found in page HTML for ID {audio_id}")
                return None

        except Exception as e:
            logger.exception(f"Playwright error while fetching {url}: {e}")
            return None


# --- Required setup for your loader ---
async def setup(bot):
    await bot.add_cog(NewgroundsAudio(bot))
