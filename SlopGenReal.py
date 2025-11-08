import discord
from discord import app_commands
from discord.ext import commands
import os
import random
from supabase import create_client, Client
from dotenv import load_dotenv
from semitone_calculator import normalize_key, normalized_keys

# --- Config / Supabase ---
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

# --- Debug flags ---
DEBUG = False
DEBUG_IGNORE_KEY_RULES = False
DEBUG_IGNORE_BPM_RULES = False
DEBUG_SHOW_ALL_ATTEMPTS = False
DEBUG_SHOW_BPM_CHANGE = True

# --- Music theory helpers ---
key_map = {"C":0,"C#":1,"D":2,"D#":3,"E":4,"F":5,"F#":6,"G":7,"G#":8,"A":9,"A#":10,"B":11}

mode_intervals = {
    "Major": [0, 2, 4, 5, 7, 9, 11],
    "Ionian": [0, 2, 4, 5, 7, 9, 11],
    "Lydian": [0, 2, 4, 6, 7, 9, 11],
    "Mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "Minor": [0, 2, 3, 5, 7, 8, 10],
    "Aeolian": [0, 2, 3, 5, 7, 8, 10],
    "Dorian": [0, 2, 3, 5, 7, 9, 10],
    "Phrygian": [0, 1, 3, 5, 7, 8, 10],
    "Locrian": [0, 1, 3, 5, 6, 8, 10],
    "m": [0, 2, 3, 5, 7, 8, 10]
}

relative_key_groups = [
    ["C Major", "A Minor", "E Phrygian", "D Dorian", "G Mixolydian", "B Locrian", "F Lydian"],
    ["Db Major", "Bb Minor", "F Phrygian", "Eb Dorian", "Ab Mixolydian", "C Locrian", "Gb Lydian"],
    ["D Major", "B Minor", "Gb Phrygian", "E Dorian", "A Mixolydian", "Db Locrian", "G Lydian"],
    ["Eb Major", "C Minor", "G Phrygian", "F Dorian", "Bb Mixolydian", "D Locrian", "Ab Lydian"],
    ["E Major", "Db Minor", "Ab Phrygian", "Gb Dorian", "B Mixolydian", "Eb Locrian", "A Lydian"],
    ["F Major", "D Minor", "A Phrygian", "G Dorian", "C Mixolydian", "E Locrian", "Bb Lydian"],
    ["Gb Major", "Eb Minor", "Bb Phrygian", "Ab Dorian", "Db Mixolydian", "F Locrian", "B Lydian"],
    ["G Major", "E Minor", "B Phrygian", "A Dorian", "D Mixolydian", "Gb Locrian", "C Lydian"],
    ["Ab Major", "F Minor", "C Phrygian", "Bb Dorian", "Eb Mixolydian", "G Locrian", "Db Lydian"],
    ["A Major", "Gb Minor", "Db Phrygian", "B Dorian", "E Mixolydian", "Ab Locrian", "D Lydian"],
    ["Bb Major", "G Minor", "D Phrygian", "C Dorian", "F Mixolydian", "A Locrian", "Eb Lydian"],
    ["B Major", "Ab Minor", "Eb Phrygian", "Db Dorian", "Gb Mixolydian", "Bb Locrian", "E Lydian"],
]

relative_keys = {}
for group in relative_key_groups:
    for key in group:
        relative_keys[key] = [k for k in group if k != key]

list1 = [
    ("Creo - Atmosphere", 128, "F#m"), 
    ("dj-Nate - Clubstep", 128, "Em"), 
    ("Panda Eyes - Antipixel", 128, "C#m"), 
    ("Jewelz123 - Silent Hill Dubstep", 70, "Gm"), 
    ("Bossfight - Milky Ways", 183, "Em"), ("Hinkik - Time Leaper", 87.5, "A#m"), 
    ("Hinkik - Outbreaker", 128, "C#m"), 
    ("Hinkik - Ena", 128, "Dm"), 
    ("Creo - Idolize", 80, "B Lydian"), 
    ("Creo - Red Haze", 80, "F"), 
    ("R4bbit - Make It Drop", 135, "Gm"), 
    ("Schtiffles - In The Tigers Den", 132, "Cm"), 
    ("Creo - In Circles", 92.5, "D#m"), 
    ("Virtual Riot - Idols", 128, "Gm"), 
    ("Vierre Cloud - Moment", 171.25, "A#m+0.5"), 
    ("Waterflame - Ricochet Love", 165, "A#m"), 
    ("Waterflame - Time Machine", 143, "F# Dorian+0.5"), 
    ("Creo - Flow", 64, "C Phrygian"),
    ("Xtrullor - Disordered Worlds", 133, "C#m"),
    ("Creo - Never Make It", 114, "G#m")
]

list2 = [
    ("Ke$ha - Take It Off", 125, "Fm"),
    ("Ke$ha - Die Young", 128, "E"),
    ("Ke$ha - We R Who We R", 120, "Cm"),
    ("Cartoon - On & On", 87, "B"),
    ("Lady Gaga - Applause", 140, "Gm"),
    ("LMFAO - Sexy And I Know It", 130, "Gm"),
    ("Kendrick Lamar - Reincarnated", 91.1, ""),
    ("The Black Eyed Peas - Rock That Body", 125, "Dm"),
    ("The Weeknd - Heartless", 85, "D#m"),
    ("Kanye West - Good Life", 84.99, "C#"),
    ("Kanye West - Black Skinhead", 130, ""),
    ("Flo Rida - Good Feeling", 128, "C#m"),
    ("Lil' Nas X - J Christ", 75, "A Phrygian"),
    ("Demi Lovato - Heart Attack", 87, "G#"),
    ("Miley Cyrus - Party In The USA", 96, "F#"),
    ("One Direction - What Makes You Beautiful", 125, "E"),
    ("Eminem - Beautiful", 66, "F Minor"),
    ("femtanyl, ISSBROKIE - NASTYWERKKKK!", 133, "")
    ("Imagine Dragons - Bones", 114, "A#m")
]

BANNED_COMBOS_FILE = "banned_combos.json"

def get_default_banned_combos():
    return [
        ("Creo - Atmosphere", "Ke$ha - Take It Off"),
        ("Kanye West - Good Life", "Vierre Cloud - Moment"),
        ("Hinkik - Outbreaker", "One Direction - What Makes You Beautiful"),
        ("Hinkik - Time Leaper", "Cartoon - On & On"),
        ("Panda Eyes - Antipixel", "Ke$ha - We R Who We R"),
        ("Panda Eyes - Antipixel", "The Black Eyed Peas - Rock That Body"),
        ("Virtual Riot - Idols", "The Black Eyed Peas - Rock That Body"),
        ("R4bbit - Make It Drop", "Kanye West - Black Skinhead"),
        ("Creo - Red Haze", "Lil' Nas X - J Christ"),
        ("Bossfight - Milky Ways", "Kendrick Lamar - Reincarnated"),
        ("dj-Nate - Clubstep", "Flo Rida - Good Feeling"),
        ("Jewelz123 - Silent Hill Dubstep", "Lady Gaga - Applause"),
        ("Creo - Idolize", "Demi Lovato - Heart Attack"),
        ("Waterflame - Ricochet Love", "The Weeknd - Heartless"),
        ("Hinkik - Ena", "Ke$ha - Die Young"),
        ("Hinkik - Ena", "One Direction - What Makes You Beautiful"),
        ("Hinkik - Outbreaker", "Ke$ha - Die Young"),
        ("Panda Eyes - Antipixel", "Ke$ha - Die Young"),
        ("Panda Eyes - Antipixel", "One Direction - What Makes You Beautiful"),
        ("Creo - In Circles", "Miley Cyrus - Party In The USA"),
        ("Panda Eyes - Antipixel", "Flo Rida - Good Feeling"),
        ("Schtiffles - In The Tigers Den", "Flo Rida - Good Feeling"),
        ("Hinkik - Outbreaker", "Flo Rida - Good Feeling"),
        ("R4bbit - Make It Drop", "LMFAO - Sexy And I Know It"),
    ]



custom_semitone_diff = {
    "Creo - Atmosphere": (3, 3),
    "dj-Nate - Clubstep": (5, 4),
    "Panda Eyes - Antipixel": (3, 2),
    "Jewelz123 - Silent Hill Dubstep": (5, 3),
    "Bossfight - Milky Ways": (3, 2),
    "Hinkik - Time Leaper": (3, 2),
    "Hinkik - Outbreaker": (4, 3),
    "Hinkik - Ena": (3, 2),
    "Creo - Idolize": (3, 3),
    "Creo - Red Haze": (3, 3),
    "R4bbit - Make It Drop": (4, 2),
    "Schtiffles - In The Tigers Den": (3, 4),
    "Creo - In Circles": (3, 3),
    "Virtual Riot - Idols": (3, 4),
    "Vierre Cloud - Moment": (3.5, 4.5),
    "Waterflame - Ricochet Love": (3, 3),
    "Waterflame - Time Machine": (2.5, 3.5),
    "Creo - Flow": (2, 2),
}

custom_bpm_diff = {
    "Ke$ha - Take It Off": (12, 15),
    "Ke$ha - Die Young": (8, 12),
    "Ke$ha - We R Who We R": (5, 15),
    "Cartoon - On & On": (3, 3),
    "Lady Gaga - Applause": (8, 15),
    "LMFAO - Sexy And I Know It": (11, 10),
    "Kendrick Lamar - Reincarnated": (4.1, 8),
    "The Black Eyed Peas - Rock That Body": (6, 19),
    "The Weeknd - Heartless": (7, 4),
    "Kanye West - Good Life": (2.99, 12.1),
    "Kanye West - Black Skinhead": (7, 15),
    "Flo Rida - Good Feeling": (10, 12),
    "Lil' Nas X - J Christ": (3, 8),
    "Demi Lovato - Heart Attack": (7, 5),
    "Miley Cyrus - Party In The USA": (14, 4),
    "One Direction - What Makes You Beautiful": (10, 15),
    "Eminem - Beautiful": (7, 10.44),
    
}

def parse_key(key_str):
    if not key_str:
        return None, None, None, ""
    micro = 0
    if '+' in key_str:
        key_str, micro = key_str.split('+'); micro = float(micro)
    elif '-' in key_str and not key_str.startswith('-'):
        key_str, micro = key_str.split('-'); micro = -float(micro)
    parts = key_str.split()
    root = parts[0]
    mode = parts[1] if len(parts) > 1 else ("m" if root.endswith('m') else "")
    if root.endswith('m') and mode == "m":
        root = root[:-1]
    semitone = key_map.get(root)
    if semitone is None:
        return None, None, None, key_str
    semitone += micro
    intervals = mode_intervals.get(mode, mode_intervals["Major"])
    note_set = sorted(((semitone + i) % 12 for i in intervals))
    return semitone, mode, note_set, f"{root} {mode}".strip()

def semitone_distance(s1, s2):
    diff = s2 - s1
    if diff > 6:
        diff -= 12
    elif diff < -6:
        diff += 12
    return diff

def key_compatible(k1, k2, song1=None):
    def normalize_mode(mode):
        if mode == "m":
            return "Minor"
        if mode == "Ionian":
            return "Major"
        return mode

    # Try parse_key first
    s1, mode1, notes1, norm1 = parse_key(k1)
    s2, mode2, notes2, norm2 = parse_key(k2)

    # Helper: index-based diff using semitone_calculator normalized_keys (enharmonic-aware)
    def index_diff_from_semitonecalculator(n1, n2):
        try:
            nk1 = normalize_key(n1)
            nk2 = normalize_key(n2)
        except Exception:
            return None
        for mode in normalized_keys:
            if nk1 in mode and nk2 in mode:
                i1 = mode.index(nk1)
                i2 = mode.index(nk2)
                diff = i2 - i1
                if diff > 6:
                    diff -= 12
                elif diff < -6:
                    diff += 12
                return float(diff)
        return None

    # If parse failed for either, try index-based fallback
    if s1 is None or s2 is None:
        idx = index_diff_from_semitonecalculator(norm1 or k1, norm2 or k2)
        if idx is not None:
            return True, idx
        return None, None

    # Collect relationship candidates
    relationship_candidates = []

    # Relative keys (compare normalized names)
    if normalize_key(norm2) in [normalize_key(r) for r in relative_keys.get(norm1, [])]:
        relationship_candidates.append(('relative', semitone_distance(s1, s2)))

    # Parent key logic
    mode_parent = {
        "Dorian": "Minor",
        "Phrygian": "Minor",
        "Aeolian": "Minor",
        "Locrian": "Minor",
        "Minor": "Minor",     
        "Major": "Major",    
        "Lydian": "Major",
        "Mixolydian": "Major",
    }
    def extract_root_and_mode(norm):
        parts = norm.split()
        if not parts:
            return "", ""
        root = parts[0]
        mode = parts[1] if len(parts) > 1 else ""
        return root, normalize_mode(mode)
    root1, nmode1 = extract_root_and_mode(norm1)
    root2, nmode2 = extract_root_and_mode(norm2)

    def is_parent_pair(root1, mode1, root2, mode2):
        if root1 != root2:
            return False
        if mode1 in mode_parent and mode2 in mode_parent:
            if (mode_parent[mode1] == mode2 and mode1 != mode2) or (mode_parent[mode2] == mode1 and mode1 != mode2):
                return True
        return False

    if is_parent_pair(root1, nmode1, root2, nmode2):
        relationship_candidates.append(('parent', semitone_distance(s1, s2)))

    # Custom semitone shift logic (respects your custom_semitone_diff map)
    max_down, max_up = custom_semitone_diff.get(str(song1), (2, 2))
    if max_down is None: max_down = 2
    if max_up is None: max_up = 2
    step = 0.25
    shifts = []
    val = -max_down
    while val <= max_up:
        shifts.append(val)
        val += step
    for shift in shifts:
        if notes2 is not None:
            shifted_notes2 = sorted(((n + shift) % 12 for n in notes2))
            if shifted_notes2 == notes1:
                relationship_candidates.append(('custom', shift))
                break

    # Add semitone_calculator index-based candidate (enharmonic-aware) if available
    idx = index_diff_from_semitonecalculator(norm1, norm2)
    if idx is not None:
        relationship_candidates.append(('index', idx))

    # If any relationships found, choose the one with the minimal abs(semitone)
    if relationship_candidates:
        best = min(relationship_candidates, key=lambda x: abs(x[1]))
        return True, best[1]

    # If nothing matches, return original semitone_distance (float), preserving micro offsets
    return False, semitone_distance(s1, s2)

def bpm_ok(bpm1, bpm2, song2=None):
    max_down, max_up = custom_bpm_diff.get(str(song2), (7.44, 10.76))
    for b in [bpm1, bpm1/2, bpm1*2]:
        change = b - bpm2
        if (0 <= change <= max_up) or (-max_down <= change < 0):
            return True
    return False

def generate_pairs(num_pairs=5):
    pairs = []
    used = set()
    attempts = 0
    while len(pairs) < num_pairs and attempts < 1000:
        attempts += 1
        a = random.choice(list1)
        b = random.choice(list2)
        if (a[0], b[0]) in banned_combos:
            continue
        if not DEBUG_IGNORE_KEY_RULES:
            key_ok, semitone_diff = key_compatible(a[2], b[2], a[0])
            if key_ok is None:
                if DEBUG:
                    print(f"Skipping key check for {a[0]} or {b[0]} (no key)")
                key_ok = True
                semitone_diff = 0
        else:
            key_ok, semitone_diff = True, 0
        bpm_okay = bpm_ok(a[1], b[1], b[0]) if not DEBUG_IGNORE_BPM_RULES else True
        if (a[0], b[0]) not in used and key_ok and bpm_okay:
            used.add((a[0], b[0]))
            _, _, _, norm_a = parse_key(a[2])
            _, _, _, norm_b = parse_key(b[2])
            pairs.append((a[0], a[1], norm_a, b[0], b[1], norm_b, semitone_diff))
        if DEBUG_SHOW_ALL_ATTEMPTS:
            print(f"Attempt {attempts}: {a[0]} x {b[0]} | Key OK: {key_ok} | BPM OK: {bpm_okay}")
    return pairs

# --- Supabase banned combos helpers ---
async def fetch_banned_combos():
    res = supabase.table("banned_combos").select("*").execute()
    return {(row["song1"], row["song2"]) for row in res.data}

async def add_banned_combo(song1, song2):
    supabase.table("banned_combos").insert({"song1": song1, "song2": song2}).execute()

async def remove_banned_combo(song1, song2):
    supabase.table("banned_combos").delete().eq("song1", song1).eq("song2", song2).execute()


# --- Role check ---
def has_jammer_role(interaction: discord.Interaction) -> bool:
    required_role_id = 938030258253361192
    member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
    if not member:
        return False
    return any(role.id == required_role_id for role in member.roles)


# --- Cog class ---
class SlopGenReal(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.points = fetch_points()

    async def generate_pairs(self, num_pairs=5):
        banned_combos = await fetch_banned_combos()
        pairs = []
        used = set()
        attempts = 0
        while len(pairs) < num_pairs and attempts < 1000:
            attempts += 1
            a = random.choice(list1)
            b = random.choice(list2)
            if (a[0], b[0]) in banned_combos:
                continue
            # Key/BPM checks (same as before)
            key_ok, semitone_diff = True, 0
            bpm_okay = True
            if not DEBUG_IGNORE_KEY_RULES:
                key_ok, semitone_diff = key_compatible(a[2], b[2], a[0])
                if key_ok is None:  # unknown key
                    key_ok, semitone_diff = True, 0
            if not DEBUG_IGNORE_BPM_RULES:
                bpm_okay = bpm_ok(a[1], b[1], b[0])
            if (a[0], b[0]) not in used and key_ok and bpm_okay:
                used.add((a[0], b[0]))
                _, _, _, norm_a = parse_key(a[2])
                _, _, _, norm_b = parse_key(b[2])
                pairs.append((a[0], a[1], norm_a, b[0], b[1], norm_b, semitone_diff))
        return pairs

    @app_commands.command(name="gen", description="Generate a starboardslop mashup idea")
    async def gen_slash(self, interaction: discord.Interaction):
        self.points = fetch_points()
        user_id = str(interaction.user.id)

        if random.randint(1, 1000) == 1:
            self.points[user_id]["points"] += 5000
            await interaction.response.send_message("You just won the slop lottery, you have received 5000 Slop Points")
            save_points(self.points)
            return

        pairs = await self.generate_pairs(1)
        lines = []
        for a, bpm_a, key_a, b, bpm_b, key_b, semitone_diff in pairs:
            semitone_count = abs(semitone_diff)
            semitone_word = "semitone" if semitone_count == 1 else "semitones"
            if semitone_diff > 0:
                direction_key = "down"
            elif semitone_diff < 0:
                direction_key = "up"
            else:
                direction_key = "none"
            lines.append(f"{a} ({bpm_a} BPM, {key_a}) x {b} ({bpm_b} BPM, {key_b}) → {semitone_count} {semitone_word} {direction_key}")
        output = "\n".join(lines)
        if len(output) > 1900:
            output = output[:1900] + "\n...(truncated)..."
        await interaction.response.send_message(output)

    @app_commands.command(name="add_ban", description="Ban a combo (Jammer role required)")
    @app_commands.describe(song1="Song from list1", song2="Song from list2")
    async def add_ban(self, interaction: discord.Interaction, song1: str, song2: str):
        if not has_jammer_role(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        list1_titles = [x[0] for x in list1]
        list2_titles = [x[0] for x in list2]
        if song1 not in list1_titles or song2 not in list2_titles:
            await interaction.response.send_message("Invalid songs.", ephemeral=True)
            return
        banned_combos = await fetch_banned_combos()
        if (song1, song2) in banned_combos:
            await interaction.response.send_message("Already banned.", ephemeral=True)
            return
        await add_banned_combo(song1, song2)
        await interaction.response.send_message(f"Banned {song1} x {song2}", ephemeral=True)

    @app_commands.command(name="remove_ban", description="Remove a banned combo (Jammer role required)")
    @app_commands.describe(song1="Song from list1", song2="Song from list2")
    async def remove_ban(self, interaction: discord.Interaction, song1: str, song2: str):
        if not has_jammer_role(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        banned_combos = await fetch_banned_combos()
        if (song1, song2) not in banned_combos:
            await interaction.response.send_message("Not banned.", ephemeral=True)
            return
        await remove_banned_combo(song1, song2)
        await interaction.response.send_message(f"Removed ban: {song1} x {song2}", ephemeral=True)

    # --- Autocomplete handlers ---
    @add_ban.autocomplete('song1')
    async def song1_autocomplete(self, interaction: discord.Interaction, current: str):
        titles = [x[0] for x in list1]
        return [
            app_commands.Choice(name=title, value=title)
            for title in titles if current.lower() in title.lower()
        ][:25]

    @add_ban.autocomplete('song2')
    async def song2_autocomplete(self, interaction: discord.Interaction, current: str):
        titles = [x[0] for x in list2]
        return [
            app_commands.Choice(name=title, value=title)
            for title in titles if current.lower() in title.lower()
        ][:25]

# --- Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(SlopGenReal(bot))