import discord
from discord import app_commands
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
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
async def get_misc_value(attribute: str, default: int = 0) -> int:
    """Fetch the count of an attribute from Supabase."""
    res = supabase.from_("miscinfo").select("count").eq("attribute", attribute).execute()
    data = res.data
    if data:
        return data[0]["count"]
    return default

async def set_misc_value(attribute: str, value: int):
    """Set the count of an attribute in Supabase (update if exists, insert if not)."""
    res = supabase.from_("miscinfo").update({"count": value}).eq("attribute", attribute).execute()
    if res.count == 0:
        supabase.from_("miscinfo").insert({"attribute": attribute, "count": value}).execute()


# --- Bot setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

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
    "autoresponder",
    "scambanner",
]

# --- Events ---
@bot.event
async def on_ready():
    try:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                logging.info(f"✅ Loaded {cog} extension.")
                print(f"✅ Loaded {cog} extension.")
            except Exception as e:
                logging.error(f"❌ Failed to load {cog}: {e}")
                print(f"❌ Failed to load {cog}: {e}")

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
            current_count = await get_misc_value("ping_count", 0)
            new_count = current_count + 1
            await set_misc_value("ping_count", new_count)
            await message.channel.send(f"Pong!\n-# Count: {new_count}")
        return

    await bot.process_commands(message)

# --- Run bot ---
bot.run(token)

