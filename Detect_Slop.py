import re
import discord
from discord.ext import commands

FORUM_CHANNEL_ID = 1352870773588623404

TITLE_PATTERN = re.compile(r"(.+?)\s*-\s*(.+?)\s*x\s*(.+?)\s*-\s*(.+)", re.IGNORECASE)

class ForumWatcher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def clean_title(self, title: str) -> str:
        """Trim extra metadata like emojis or info after ':' / '#' / '<' / '('."""
        title = title.strip()
        title = re.sub(r"^[^\w]+", "", title)  # remove leading emojis/symbols
        title = re.split(r"[:#<\(]", title)[0].strip()
        return title

    async def parse_title(self, title: str):
        """Parse a forum thread title into GD author/song and real song info."""
        cleaned_title = self.clean_title(title)
        match = TITLE_PATTERN.match(cleaned_title)
        if not match:
            return None
        gd_author, gd_song, song_author, song = match.groups()
        return {
            "gd_author": gd_author.strip(),
            "gd_song": gd_song.strip(),
            "song_author": song_author.strip(),
            "song": song.strip(),
        }

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        if thread.parent_id != FORUM_CHANNEL_ID:
            return

        parsed = await self.parse_title(thread.name)
        if not parsed:
            print(f"❌ Couldn't parse: {thread.name}")
            return

        # --- Clean and normalize all parts ---
        gd_author = parsed["gd_author"].lower().strip()
        gd_song = parsed["gd_song"].lower().strip()
        song_author = parsed["song_author"].lower().strip()
        song = parsed["song"].lower().strip()

        print(f"🧩 Parsed title: {parsed}")

        # Wait for author to post (Option 1)
        def check(msg: discord.Message):
            return msg.channel.id == thread.id and msg.author.id == thread.owner_id

        try:
            await self.bot.wait_for("message", check=check, timeout=3600)
            print(f"📩 Author posted in '{thread.name}', proceeding...")
        except TimeoutError:
            print(f"⌛ Timeout waiting for author in '{thread.name}'. No bot message sent.")
            return

        # === SINGLE-FIELD MESSAGES ===
        single_messages = []
        if gd_song == "applause":
            single_messages.append("shlant rn: 🤤")

        # === PREFIX SYSTEM ===
        prefixes = []

        # Song author based
        if song_author == "tech n9ne":
            prefixes.append("Tech N9ne")
        if song_author in ["ke$ha", "kesha"]:
            prefixes.append("Ke$ha")
        if song_author == "bbno$":
            prefixes.append("bbno")

        # GD song based
        if gd_song == "antipixel":
            prefixes.append("Antipixel")
        if gd_song == "flow":
            prefixes.append("flow")

        # Song based
        if song == "rock that body":
            prefixes.append("RTB")

        # GD author based
        if gd_author == "uhhh idk any overused gdsong artists":
            prefixes.append("dude what why did you make this your title")

        # Multi-condition checks
        if song_author in ["knife party", "koraii", "waterflame"] and song in ["give it up", "time machine", "think about it"]:
            prefixes.append("Rap")

        if song_author in ["charlie draker & far too loud", "charlie draker", "waterflame", "paragonx9"] and song in ["control: crowd", "crowd control", "nail gun", "infiltration"]:
            prefixes.append("Fast Rap")

        # === FINAL MESSAGE ===
        if single_messages and not prefixes:
            final_message = " + ".join(single_messages)
        if prefixes and not single_messages:
            final_message = f"{" ".join(prefixes)}slop"
        if prefixes and single_messages:
            final_message = f"{" + ".join(single_messages)} + {" ".join(prefixes)}slop"

        if final_message:
            await thread.send(final_message)
            print(f"✅ Sent message: {final_message}")
        else:
            print("ℹ️ No matching prefixes, no message sent.")


async def setup(bot):
    await bot.add_cog(ForumWatcher(bot))
