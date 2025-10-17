import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import aiofiles
import subprocess
from pathlib import Path
import asyncio
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Use .env variable, fallback to "temp_audio" if not set
TEMP_DIR = Path(os.getenv("TEMP_AUDIO_PATH", "temp_audio"))
TEMP_DIR.mkdir(exist_ok=True, parents=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB cap

def pitch_shift(source, dest, semitones):
    factor = 2 ** (semitones / 12)
    filter_str = f"asetrate=44100*{factor},aresample=44100,atempo={1/factor}"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(source), "-filter:a", filter_str, "-b:a", "320K", str(dest)],
        check=True,
    )

def time_stretch(source, dest, bpm_from, bpm_to):
    factor = bpm_to / bpm_from
    filter_str = f"atempo={factor}"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(source), "-filter:a", filter_str, "-b:a", "320K", str(dest)],
        check=True,
    )

class PitchStretch(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Start cleanup loop
        self.bot.loop.create_task(self.cleanup_temp_folder())

    # -------- Utility: stream download --------
    async def download_file(self, url: str, dest: Path):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return False
                async with aiofiles.open(dest, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        await f.write(chunk)
        return True

    # -------- /pitch --------
    @app_commands.command(name="pitch", description="Pitch shift an audio file by -12 to +12 semitones")
    @app_commands.describe(semitones="Number of semitones to shift (-12 to +12)", file="Attach an audio file")
    async def pitch(self, interaction: discord.Interaction, semitones: float, file: discord.Attachment):
        if not (-12 <= semitones <= 12):
            await interaction.response.send_message("❌ Semitones must be between -12 and 12.", ephemeral=True)
            return
        if file.size > MAX_FILE_SIZE:
            await interaction.response.send_message("❌ File too large! Max size is 50MB.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        input_path = TEMP_DIR / f"input_{interaction.id}_{file.filename}"
        output_path = TEMP_DIR / f"output_{interaction.id}.mp3"

        try:
            # Stream download
            ok = await self.download_file(file.url, input_path)
            if not ok:
                await interaction.followup.send("❌ Failed to download the file.")
                return

            pitch_shift(input_path, output_path, semitones)

            await interaction.followup.send(
                f"✅ Pitched `{file.filename}` by {semitones} semitones.",
                file=discord.File(output_path),
            )

        except subprocess.CalledProcessError as e:
            await interaction.followup.send(f"❌ FFmpeg error: {e}")
        finally:
            for path in (input_path, output_path):
                if path.exists():
                    try:
                        path.unlink()
                    except Exception:
                        pass

    # -------- /stretch --------
    @app_commands.command(name="stretch", description="Time-stretch an audio file to a target BPM")
    @app_commands.describe(original_bpm="Original BPM of the track", target_bpm="Target BPM", file="Attach an audio file")
    async def stretch(self, interaction: discord.Interaction, original_bpm: float, target_bpm: float, file: discord.Attachment):
        if original_bpm <= 0 or target_bpm <= 0:
            await interaction.response.send_message("❌ BPM must be greater than 0.", ephemeral=True)
            return
        if file.size > MAX_FILE_SIZE:
            await interaction.response.send_message("❌ File too large! Max size is 50MB.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        input_path = TEMP_DIR / f"input_{interaction.id}_{file.filename}"
        output_path = TEMP_DIR / f"output_{interaction.id}.mp3"

        try:
            # Stream download
            ok = await self.download_file(file.url, input_path)
            if not ok:
                await interaction.followup.send("❌ Failed to download the file.")
                return

            time_stretch(input_path, output_path, original_bpm, target_bpm)

            await interaction.followup.send(
                f"✅ Stretched `{file.filename}` from {original_bpm} BPM to {target_bpm} BPM.",
                file=discord.File(output_path),
            )

        except subprocess.CalledProcessError as e:
            await interaction.followup.send(f"❌ FFmpeg error: {e}")
        finally:
            for path in (input_path, output_path):
                if path.exists():
                    try:
                        path.unlink()
                    except Exception:
                        pass

    # -------- Cleanup loop --------
    async def cleanup_temp_folder(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                for file_path in TEMP_DIR.iterdir():
                    if file_path.is_file():
                        try:
                            file_path.unlink()
                        except Exception as e:
                            print(f"Failed to delete {file_path}: {e}")
                await asyncio.sleep(60)
            except Exception as e:
                print(f"Cleanup task error: {e}")
                await asyncio.sleep(60)

async def setup(bot: commands.Bot):
    await bot.add_cog(PitchStretch(bot))
