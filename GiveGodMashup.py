import discord
from discord import app_commands
from discord.ext import commands
import random
import io
import time
import asyncio
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ===== CONFIG =====
CREDENTIALS_FILE = "credentials.json"
DRIVE_FOLDER_ID = "11PzE9St295B0DcAPqJSfDyOKM4XYUdOV"
DISCORD_FILE_LIMIT = 25 * 1024 * 1024  # 25 MB
CACHE_DURATION = 300  # seconds
# ==================


class GiveGodMashup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.drive_service = self.setup_drive_service()
        self.cached_files = []
        self.cache_timestamp = 0
        self.bot.loop.create_task(self.preload_cache())

    async def preload_cache(self):
        await self.bot.wait_until_ready()
        self.refresh_cache()
        print("✅ GiveGodMashup cache preloaded.")

    def setup_drive_service(self):
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        return build("drive", "v3", credentials=creds)

    def get_drive_files(self):
        if time.time() - self.cache_timestamp > CACHE_DURATION or not self.cached_files:
            self.refresh_cache()
        return self.cached_files

    def refresh_cache(self):
        drive_files = []
        page_token = None
        query = f"'{DRIVE_FOLDER_ID}' in parents and trashed=false"
        while True:
            results = self.drive_service.files().list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, size)",
                pageToken=page_token
            ).execute()
            for item in results.get("files", []):
                size = int(item.get("size", 0))
                drive_files.append((item["name"], item["id"], size))
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        self.cached_files = drive_files
        self.cache_timestamp = time.time()
        print(f"GiveGodMashup: cached {len(self.cached_files)} files.")

    # -----------------------------
    # The actual command
    # -----------------------------
    @app_commands.command(
        name="give_good_mashup",
        description="Get a totally great and bangin' mashup"
    )
    async def give_good_mashup(self, interaction: discord.Interaction):
        await interaction.response.defer()

        files = self.get_drive_files()
        if not files:
            await interaction.followup.send("Haha no slop 4 u", ephemeral=True)
            return

        file_name, file_id, file_size = random.choice(files)

        if file_size > DISCORD_FILE_LIMIT:
            link = f"https://drive.google.com/file/d/{file_id}/view"
            await interaction.followup.send(
                f"Slop too sloppy, here’s the Google Drive link for **{file_name}**:\n{link}"
            )
            return

        def blocking_download():
            request = self.drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            return fh

        try:
            buf = await asyncio.to_thread(blocking_download)
            await interaction.followup.send(
                "Heres your fresh sloppy slop slopslop #1 slop sloppy",
                file=discord.File(buf, filename=file_name)
            )
        except Exception as e:
            link = f"https://drive.google.com/file/d/{file_id}/view"
            await interaction.followup.send(
                f"⚠️ Couldn’t download **{file_name}** (error: {e}). Here’s the link instead:\n{link}"
            )


async def setup(bot):
    await bot.add_cog(GiveGodMashup(bot))
    print("✅ GiveGodMashup loaded.")
