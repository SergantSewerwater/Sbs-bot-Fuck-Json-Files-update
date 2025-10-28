import re
import discord
from discord.ext import commands

FORUM_CHANNEL_ID = 1352870773588623404


TITLE_PATTERN = re.compile(r"(.+?)\s*-\s*(.+?)\s*x\s*(.+?)\s*-\s*(.+)", re.IGNORECASE)


class ForumWatcher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def parse_title(self, title: str):
        """Parse a forum thread title into its four parts."""
        match = TITLE_PATTERN.match(title)
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
    async def on_thread_create(self, thread):
        """Triggered when a new forum thread is created."""
        if thread.parent_id != FORUM_CHANNEL_ID:
            return
        


        parsed = await self.parse_title(thread.name)
        if not parsed:
            print(f"❌ Couldn't parse: {thread.name}")
            return

        print(f"🧩 New thread parsed: {parsed}")

        prefixes = []

        # NON Prefixes
        if parsed["song_author"].lower() == "Lady Gaga":
            await thread.send("shlant rn: 🤤")
        if parsed["gd_song"].lower() == "rok taht body":
            await thread.send("slop that body better")

            # Prefixes

        if parsed["song_author"].lower() == "tech n9ne":
            prefixes.append("Tech N9ne")

        if parsed["song_author"].lower() == "ke$ha" or "kesha":
            prefixes.append("Ke$ha")

        if parsed["song_author"].lower() == "bbno$":
           prefixes.append("bbno")

        if parsed["song"].lower() == "rock that body":
            prefixes.append("OMG its RTB hahahahahahahahahahahahah lmao loooooool i love that song it is just the best!")

        if parsed["gd_author"].lower() == "uhhh idk any overused gdsong artists":
            prefixes.append("dude what why did you make this your title")

        if parsed["gd_song"].lower() == "antipixel":
            prefixes.append("Antipixel")
        
        if parsed["gd_song"].lower() == "flow":
            prefixes.append("flow")
        
        if parsed["song_author"].lower() == "knife party" or "koraii"  or "waterflame" and parsed["song"].lower() == "give it up" or "time machine" or "think about it":
            prefixes.append("Rap")

        if parsed["song_author"].lower() == "charlie draker & far too loud" or "charlie draker"  or "waterflame" or "paragonx9" and parsed["song"].lower() == "control: crowd" or "crowd control" or "nail gun" or "infiltration":
            prefixes.append("Fast Rap")

    


        if prefixes:
            final_message = "".join(prefixes) + "slop"
            await thread.send(final_message)
            print(f"✅ Sent message: {final_message}")
        else:
            print("ℹ️ No matching prefixes, no message sent.")


async def setup(bot):
    await bot.add_cog(ForumWatcher(bot))
