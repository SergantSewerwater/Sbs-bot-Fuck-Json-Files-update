import random

import discord
from discord import app_commands
from discord.ext import commands

# function that returns output for /decree
def decree_output():
    # list of responses and conflicts
    responses = [
        "Offbeat",
        "Offsync",
        "Offbpm",
        "Offkey",
        "Real offbar",
        "Shlant offbar",
        "Bad 5 semiflomble",
        "Vocals too loud",
        "Vocals too quiet",
        "Bad mixing",
        "Bad acapella",
        "BPM diff",
        "Key diff",
        "Bad pitch quality",
        "Offvibe",
        "Offenergy",
        "Audio clipping",
        "Offglup",
    ]
    weird_responses = [
        "no",
        "bad stinky bad bad stinky badbad bad stinky #1 worst mashup bad",
        "Never touch an audio editing software again",
    ]
    positive_responses = [
        "Good mashup",
        "Accept worthy",
        "Best mashup ever yes #1 starboard worthy",
    ]
    conflicts = {
        "Vocals too loud": {"Vocals too quiet", "Bad mixing"},
        "Vocals too quiet": {"Vocals too loud", "Bad mixing"},
        "Offkey": {"Bad 5 semiflomble"},
        "Bad 5 semiflomble": {"Offkey"},
        "Bad mixing": {"Vocals too loud", "Vocals too quiet"},
        "Offbpm": {"Offbeat", "Offsync", "Real offbar", "Shlant offbar"},
        "Offsync": {"Offbpm"},
        "Offbeat": {"Offbpm", "Shlant offbar"},
        "Real offbar": {"Offbpm", "Shlant offbar"},
        "Shlant offbar": {"Offbpm", "Offbeat", "Real offbar"},
    }

    # the actual thing
    random_fucking_number = random.randint(0, 4)
    if random_fucking_number == 0:
        return random.choice(positive_responses)
    elif random_fucking_number == 4:
        return random.choice(weird_responses)
    
    else:
        items = []
        for _ in range(random_fucking_number):
            # idk how this works but it does i guess
            while True:
                item = random.choice(responses)
                if item in items or any(item in conflicts.get(existing, set()) for existing in items):
                    continue
                items.append(item)
                break
        return " + ".join(items)

# the cog or something idk
class DecreeCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    # ----- /decree -----
    @app_commands.command(name="decree", description="Judges a mashup with advanced MashupGPT technology")
    async def decree(self, interaction: discord.Interaction):
        await interaction.response.send_message(decree_output())

# cog loader
async def setup(bot: commands.Bot):
    await bot.add_cog(DecreeCommand(bot))
