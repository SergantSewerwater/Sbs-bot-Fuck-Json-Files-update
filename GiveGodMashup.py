import discord
from discord import app_commands
from discord.ext import commands
import random
import io
import os
import time
import asyncio
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
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
        self.points = fetch_points()

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
        name="give_sergeant_singing",
        description="Get Sergeant's totally godly and amazing voice in your sbs bot"
    )
    async def give_good_mashup(self, interaction: discord.Interaction):
        self.points = fetch_points()
        user_id = str(interaction.user.id)

        if random.randint(1, 1000) == 1:
            self.points[user_id]["points"] += 5000
            await interaction.followup.send("You just won the slop lottery, you have received 5000 Slop Points")
            save_points(self.points)
            return
        
        await interaction.response.defer(thinking=True)

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
