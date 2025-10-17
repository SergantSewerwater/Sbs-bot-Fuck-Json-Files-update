import discord
from discord import app_commands
from discord.ext import commands
import os
import io
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ===== CONFIG =====
ACAPELLA_DIR = r"C:\Users\matsj\Desktop\SBSbot\acapellas"  # Local folder
CREDENTIALS_FILE = "credentials.json"  # Must stay local
DRIVE_FOLDER_ID = "1w3WELaTSVhwG5AFmGqFeyWhN6c5wEhgT"
CACHE_DURATION = 300  # seconds
DISCORD_FILE_LIMIT = 25 * 1024 * 1024  # 25 MB
# =================

class Acapella(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cached_files = []  # List of (name, path_or_id, size)
        self.cache_timestamp = 0
        self.drive_service = self.setup_drive_service()
        self.bot.loop.create_task(self.preload_cache())

    async def preload_cache(self):
        await self.bot.wait_until_ready()
        self.refresh_cache()
        print("✅ Acapella cache preloaded.")

    def setup_drive_service(self):
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        return build("drive", "v3", credentials=creds)

    def get_local_files(self):
        """Return list of (filename, full_path, None) for local files"""
        return [(f, os.path.join(root, f), None)
                for root, _, files in os.walk(ACAPELLA_DIR)
                for f in files]

    def get_drive_files(self):
        """Return list of (filename, file_id, size) for Google Drive files"""
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
        return drive_files

    def refresh_cache(self):
        """Combine local and Drive files into cached_files"""
        local = self.get_local_files()
        drive = self.get_drive_files()
        self.cached_files = local + drive
        self.cache_timestamp = time.time()
        print("✅ Acapella cached files:", [f[0] for f in self.cached_files])

    def get_all_files(self):
        """Return cached files, refresh if expired"""
        if time.time() - self.cache_timestamp > CACHE_DURATION:
            self.refresh_cache()
        return self.cached_files

    async def autocomplete_songs(self, interaction: discord.Interaction, current: str):
        files = self.get_all_files()
        matches = [f[0] for f in files if current.lower() in f[0].lower()]
        return [app_commands.Choice(name=f, value=f) for f in matches[:25]]

    @app_commands.command(
        name="acapella",
        description="Find and send an acapella file for a given song"
    )
    @app_commands.describe(song_name="Name of the song to find")
    @app_commands.autocomplete(song_name=autocomplete_songs)
    async def acapella_command(self, interaction: discord.Interaction, song_name: str):
        # Defer the interaction to avoid 10062 if fetching takes time
        await interaction.response.defer(ephemeral=False)

        files = self.get_all_files()
        match = next((f for f in files if song_name.lower() in f[0].lower()), None)

        if not match:
            await interaction.followup.send(
                f"❌ I do not have an acapella for that song."
            )
            return

        # Local file
        if match[2] is None:
            await interaction.followup.send(
                f"🎤 Here's the acapella:",
                file=discord.File(match[1])
            )
        else:
            # Google Drive file
            file_name, file_id, file_size = match
            if file_size <= DISCORD_FILE_LIMIT:
                # Fetch file data from Drive
                request = self.drive_service.files().get_media(fileId=file_id)
                file_data = io.BytesIO(request.execute())
                await interaction.followup.send(
                    f"🎤 Here's the acapella for **{file_name}**:",
                    file=discord.File(file_data, filename=file_name)
                )
            else:
                # File too large for Discord, send Drive link
                link = f"https://drive.google.com/file/d/{file_id}/view"
                await interaction.followup.send(
                    f"🎤 File too large for Discord. Here’s the Google Drive link for **{file_name}**:\n{link}"
                )

# ---------------------- setup ----------------------
async def setup(bot):
    await bot.add_cog(Acapella(bot))
    print("✅ Acapella commands loaded.")
