import discord
from discord import app_commands
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import asyncio
from supabase import create_client

# --- Load environment variables ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")
token = os.getenv("DISCORD_TOKEN")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    raise ValueError("SUPABASE_URL or SERVICE_ROLE_KEY not found in environment variables.")
if not token:
    raise ValueError("DISCORD_TOKEN not found in environment variables.")

# --- Create Supabase client ---
supabase = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

# --- Logging ---
logging.basicConfig(
    level=logging.DEBUG,
    filename='discord.log',
    encoding='utf-8',
    filemode='w',
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)

# --- Blocked channels ---
BLOCKED_CHANNEL_IDS = [
    1352915632936718386,
]

# --- Supabase helpers ---
# These helpers run potentially-blocking supabase calls in the default executor to avoid blocking the event loop.
async def get_misc_value(attribute: str, default: int = 0) -> int:
    """Fetch the count of an attribute from Supabase (runs in executor)."""
    loop = asyncio.get_running_loop()

    def _sync_get():
        res = supabase.from_("miscinfo").select("count").eq("attribute", attribute).execute()
        data = getattr(res, "data", None)
        if data:
            return data[0]["count"]
        return default

    try:
        return await loop.run_in_executor(None, _sync_get)
    except Exception:
        logging.exception("Failed to fetch misc value %s", attribute)
        return default

async def set_misc_value(attribute: str, value: int):
    """Set the count of an attribute in Supabase (runs in executor)."""
    loop = asyncio.get_running_loop()

    def _sync_set():
        res = supabase.from_("miscinfo").update({"count": value}).eq("attribute", attribute).execute()
        if getattr(res, "count", 0) == 0:
            supabase.from_("miscinfo").insert({"attribute": attribute, "count": value}).execute()

    try:
        await loop.run_in_executor(None, _sync_set)
    except Exception:
        logging.exception("Failed to set misc value %s to %s", attribute, value)


# --- Bot setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# --- Ping buffering to avoid frequent DB writes ---
_ping_lock: asyncio.Lock = asyncio.Lock()
_ping_persisted: int = 0
_ping_pending: int = 0
_ping_flush_task: asyncio.Task | None = None
_ping_flush_interval: int = 10  # seconds between flushes to Supabase

def case_insensitive_prefix(bot, message):
    prefixes = ['slop ']
    content = message.content.lower()
    for prefix in prefixes:
        if content.startswith(prefix):
            return prefix
    return commands.when_mentioned(bot, message)

bot = commands.Bot(command_prefix=case_insensitive_prefix, intents=intents, case_insensitive=True)

BOT_VERSION = "2.0.2"
GUILD_ID = 1411767823730085971

COGS = [
    "acapella_commands",
    "Find_Key",
    "GiveGodMashup",
    "semitone_calculator",
    "Imitate",
    "pitchnstretch",
    "jsondump",
    "SlopGenReal",
    "gambling",
    "SongData_Guess",
    "MakeSfhMoreLikeGdmToRagebaitShlant",
    "ping_shlant",
    "Detect_Slop",
    "ng_link_better",
    "Alltendance",
    "butter",
    "ReplaceOtherBots",
    "scambanner",
    "count_accept",
]

# --- Events ---
@bot.event
async def on_ready():

    # Initialize ping buffering primitives
    global _ping_lock, _ping_persisted, _ping_flush_task
    if _ping_lock is None:
        _ping_lock = asyncio.Lock()

    try:
        # Load extensions
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                logging.info(f"✅ Loaded {cog} extension.")
                print(f"✅ Loaded {cog} extension.")
            except Exception as e:
                logging.error(f"❌ Failed to load {cog}: {e}")
                print(f"❌ Failed to load {cog}: {e}")

        # Load persisted ping value once using executor-safe helper
        try:
            _ping_persisted = await get_misc_value("ping_count", 0)
            logging.info("Initial ping_count loaded: %s", _ping_persisted)
        except Exception:
            logging.exception("Failed to load initial ping_count; defaulting to 0")
            _ping_persisted = 0

        # Start background flush task (if not already running)
        if _ping_flush_task is None or _ping_flush_task.done():
            _ping_flush_task = asyncio.create_task(_ping_flush_loop())

        guild = discord.Object(id=GUILD_ID)
        synced_guild = await bot.tree.sync(guild=guild)
        synced_global = await bot.tree.sync()

        logging.info(f"Synced {len(synced_guild)} guild command(s) to guild {GUILD_ID}.")
        logging.info(f"Synced {len(synced_global)} global command(s).")

        print("Guild registered commands:", [(cmd.name, cmd.description) for cmd in synced_guild])
        print("Global registered commands:", [(cmd.name, cmd.description) for cmd in synced_global])
        print(f"🤖 Bot is ready. Logged in as {bot.user}")
        print(f"BOT_VERSION: {BOT_VERSION}")

    except Exception as e:
        logging.error(f"❌ Failed during on_ready: {e}")
        print(f"❌ Failed during on_ready: {e}")

@bot.event
async def on_message(message):
    if message.content.lower() == "slop ping":
        if message.channel.id not in BLOCKED_CHANNEL_IDS:
            # Use buffered ping counter to avoid frequent DB writes
            global _ping_pending, _ping_persisted
            async with _ping_lock:
                _ping_pending += 1
                local_total = _ping_persisted + _ping_pending

            await message.channel.send(f"Pong!\n-# Count: {local_total}")
        return

    await bot.process_commands(message)

# --- Background flush loop ---
async def _ping_flush_loop():
    global _ping_pending, _ping_persisted
    while True:
        await asyncio.sleep(_ping_flush_interval)
        # Atomically take pending value
        async with _ping_lock:
            pending = _ping_pending
            _ping_pending = 0
        if pending <= 0:
            continue

        new_total = _ping_persisted + pending
        loop = asyncio.get_running_loop()

        def _sync_flush():
            res = supabase.from_("miscinfo").update({"count": new_total}).eq("attribute", "ping_count").execute()
            if getattr(res, "count", 0) == 0:
                supabase.from_("miscinfo").insert({"attribute": "ping_count", "count": new_total}).execute()

        try:
            await loop.run_in_executor(None, _sync_flush)
            _ping_persisted = new_total
            logging.info("Flushed %s pings to Supabase; new total %s", pending, new_total)
        except Exception:
            logging.exception("Failed to flush ping buffer to Supabase; re-adding pending")
            # Re-add pending back to buffer for retry
            async with _ping_lock:
                _ping_pending += pending


# --- Run bot ---
bot.run(token)

