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

# Configure logging for this cog
logger = logging.getLogger("NewgroundsAudio")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Configure logging for this cog
logger = logging.getLogger("NewgroundsAudio")
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
    @app_commands.describe(input_value="Newgrounds audio ID or URL")
    async def ngaudio(self, interaction: discord.Interaction, input_value: str):
        """Slash command that fetches the direct audio.ngfiles.com link and embeds the audio."""
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



        match = re.search(r"(\d+)", input_value)
        if not match:
            logger.warning(f"No audio ID found in input: {input_value}")
            await interaction.followup.send("❌ Could not find a valid audio ID in your input.")
            return

        audio_id = int(match.group(1))
        logger.info(f"Extracted audio ID: {audio_id}")

        link = await self.fetch_audio_ng_link(audio_id)
        if not link:
            logger.error(f"Could not fetch audio.ng link for ID {audio_id}")
            await interaction.followup.send("❌ Could not find an audio.ng link. The track may be private or unavailable.")
            return

        logger.info(f"Fetched CDN link: {link}")

        filename = link.split("/")[-1].split("?")[0]
        file_path = os.path.join(self.temp_path, filename)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(link) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to download {link} (HTTP {resp.status})")
                        await interaction.followup.send(f"❌ Failed to download file (HTTP {resp.status}).")
                        return
                    with open(file_path, "wb") as f:
                        f.write(await resp.read())
            logger.info(f"Downloaded file to {file_path}")
        except Exception as e:
            logger.exception(f"Error downloading file {link}: {e}")
            await interaction.followup.send("❌ Error downloading the audio file.")
            return

        # Create embed
        embed = discord.Embed(
            title="🎵 Newgrounds Audio",
            description=f"[Listen on Newgrounds](https://www.newgrounds.com/audio/listen/{audio_id})",
            color=discord.Color.orange()
        )
        embed.add_field(name="Direct File", value=f"[{filename}]({link})")
        embed.set_footer(text="Fetched from Newgrounds CDN (audio.ngfiles.com)")
        embed.set_author(name=f"ID: {audio_id}")
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/0/0a/Newgrounds_Logo.svg")

        try:
            file = discord.File(file_path, filename=filename)
            await interaction.followup.send(embed=embed, file=file)
            logger.info(f"Sent embed and file {filename} to Discord")
        except Exception as e:
            logger.exception(f"Error sending file to Discord: {e}")
            await interaction.followup.send("❌ Error sending the audio file to Discord.")

        # Cleanup
        try:
            os.remove(file_path)
            logger.info(f"Deleted temporary file {file_path}")
        except Exception:
            pass

    # im just gonna hope i did ts right
    async def fetch_audio_ng_link(self, audio_id: int):
        """Fetch the direct audio.ngfiles.com link from a Newgrounds listen page."""
        url = f"https://www.newgrounds.com/audio/listen/{audio_id}"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url)
            html = await page.content()
            await browser.close()

        match = re.search(r'https:\/\/audio\.ngfiles\.com\/\d+\/[^\s"\']+\.mp3\?f\d+', html)
        return match.group(0) if match else None

# Async setup function for modern loader
async def setup(bot):
    await bot.add_cog(NewgroundsAudio(bot))
