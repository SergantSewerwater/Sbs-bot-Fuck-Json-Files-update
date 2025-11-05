import os
import re
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands


class NewgroundsAudio(commands.Cog):
    """Cog for fetching and embedding Newgrounds audio files."""

    def __init__(self, bot):
        self.bot = bot
        self.temp_path = os.getenv("TEMP_AUDIO_PATH", "./temp_audio")

        # Ensure temp directory exists
        os.makedirs(self.temp_path, exist_ok=True)

    @app_commands.command(
        name="ngaudio",
        description="Fetch and embed a Newgrounds song (from ID or URL)."
    )
    async def ngaudio(self, interaction: discord.Interaction, input_value: str):
        """Slash command that fetches the direct audio.ngfiles.com link and embeds the audio."""
        await interaction.response.defer(thinking=True)

        # Extract numeric ID
        match = re.search(r"(\d+)", input_value)
        if not match:
            await interaction.followup.send("❌ Could not find a valid audio ID in your input.")
            return

        audio_id = int(match.group(1))

        # Get CDN link
        link = await self.fetch_audio_ng_link(audio_id)
        if not link:
            await interaction.followup.send("❌ Could not find a valid audio.ng link. The track may be private or unavailable.")
            return

        # Try to get file name
        filename = link.split("/")[-1].split("?")[0]
        file_path = os.path.join(self.temp_path, filename)

        # Download the file
        async with aiohttp.ClientSession() as session:
            async with session.get(link) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"❌ Failed to download file (HTTP {resp.status}).")
                    return
                with open(file_path, "wb") as f:
                    f.write(await resp.read())

        # Create embed
        embed = discord.Embed(
            title="🎵 Newgrounds Audio",
            description=f"[Listen on Newgrounds](https://www.newgrounds.com/audio/listen/{audio_id})",
            color=discord.Color.orange()
        )
        embed.add_field(name="Direct File", value=f"[{filename}]({link})")
        embed.set_footer(text="Fetched from Newgrounds CDN (audio.ngfiles.com)")

        # Attach audio file
        file = discord.File(file_path, filename=filename)
        embed.set_author(name=f"ID: {audio_id}")
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/0/0a/Newgrounds_Logo.svg")

        await interaction.followup.send(embed=embed, file=file)

        # Optional cleanup
        try:
            os.remove(file_path)
        except Exception:
            pass

    async def fetch_audio_ng_link(self, audio_id: int):
        """Fetch the direct audio.ngfiles.com link from a Newgrounds listen page."""
        url = f"https://www.newgrounds.com/audio/listen/{audio_id}"
        headers = {"User-Agent": "Mozilla/5.0"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()

        match = re.search(r'https:\/\/audio\.ngfiles\.com\/\d+\/[^\s"\']+\.mp3\?f\d+', html)
        return match.group(0) if match else None


# ✅ async setup for your loader
async def setup(bot):
    await bot.add_cog(NewgroundsAudio(bot))
