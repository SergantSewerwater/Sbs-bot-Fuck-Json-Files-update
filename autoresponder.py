import os
import discord
from discord import app_commands
from discord.ext import commands
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

TARGET_CHANNEL_ID = 899784386038333555
ADMIN_CHANNEL_ID = 928182236459696128
IGNORED_ROLE_ID = 1429783971654406195


class AutoResponder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.autoresponses = {}
        bot.loop.create_task(self.load_from_db())

    # ========================
    # 🔄 DATABASE LOAD
    # ========================
    async def load_from_db(self):
        data = supabase.table("autoresponses").select("*").execute()
        self.autoresponses.clear()

        for row in data.data:
            self.autoresponses[row["name"]] = {
                "keywords": row["keywords"],
                "response": row["response"]
            }

        print(f"✅ Loaded {len(self.autoresponses)} autoresponses from Supabase.")

    # ========================
    # 🔹 AUTORESPONSE LISTENER
    # ========================
    @commands.Cog.listener("on_message")
    async def autoresponse_listener(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id != TARGET_CHANNEL_ID:
            return

        if isinstance(message.author, discord.Member):
            if any(role.id == IGNORED_ROLE_ID for role in message.author.roles):
                return

        content = message.content.lower()

        for data in self.autoresponses.values():
            if any(k in content for k in data["keywords"]):
                await message.reply(data["response"], mention_author=False)
                break

    # ========================
    # 🔒 CHANNEL LOCK
    # ========================
    def admin_channel_only():
        def predicate(interaction: discord.Interaction):
            return interaction.channel_id == ADMIN_CHANNEL_ID
        return app_commands.check(predicate)

    # ========================
    # 📋 VIEW ALL
    # ========================
    @app_commands.command(name="ar_list")
    @admin_channel_only()
    async def ar_list(self, interaction: discord.Interaction):
        if not self.autoresponses:
            await interaction.response.send_message("No autoresponses found.", ephemeral=True)
            return

        msg = "**Autoresponse Lists:**\n"
        for name, data in self.autoresponses.items():
            msg += f"\n**{name}**\nKeywords: {', '.join(data['keywords'])}\nResponse: {data['response']}"

        await interaction.response.send_message(msg, ephemeral=True)

    # ========================
    # ➕ ADD LIST
    # ========================
    @app_commands.command(name="ar_add_list")
    @admin_channel_only()
    async def ar_add_list(self, interaction: discord.Interaction, name: str, response: str, keywords: str):
        keyword_list = [k.strip().lower() for k in keywords.split(",")]

        supabase.table("autoresponses").insert({
            "name": name,
            "keywords": keyword_list,
            "response": response
        }).execute()

        await self.load_from_db()
        await interaction.response.send_message(f"✅ Created list **{name}**.", ephemeral=True)

    # ========================
    # ➕ ADD KEYWORDS
    # ========================
    @app_commands.command(name="ar_add_keyword")
    @admin_channel_only()
    async def ar_add_keyword(self, interaction: discord.Interaction, name: str, keywords: str):
        if name not in self.autoresponses:
            await interaction.response.send_message("List does not exist.", ephemeral=True)
            return

        new_keys = [k.strip().lower() for k in keywords.split(",")]
        updated = list(set(self.autoresponses[name]["keywords"] + new_keys))

        supabase.table("autoresponses").update({
            "keywords": updated
        }).eq("name", name).execute()

        await self.load_from_db()
        await interaction.response.send_message(f"✅ Keywords added to **{name}**.", ephemeral=True)

    # ========================
    # ➖ REMOVE KEYWORDS
    # ========================
    @app_commands.command(name="ar_remove_keyword")
    @admin_channel_only()
    async def ar_remove_keyword(self, interaction: discord.Interaction, name: str, keywords: str):
        if name not in self.autoresponses:
            await interaction.response.send_message("List does not exist.", ephemeral=True)
            return

        remove_keys = [k.strip().lower() for k in keywords.split(",")]
        updated = [k for k in self.autoresponses[name]["keywords"] if k not in remove_keys]

        supabase.table("autoresponses").update({
            "keywords": updated
        }).eq("name", name).execute()

        await self.load_from_db()
        await interaction.response.send_message(f"✅ Keywords removed from **{name}**.", ephemeral=True)

    # ========================
    # ✏️ EDIT RESPONSE
    # ========================
    @app_commands.command(name="ar_edit_response")
    @admin_channel_only()
    async def ar_edit_response(self, interaction: discord.Interaction, name: str, new_response: str):
        supabase.table("autoresponses").update({
            "response": new_response
        }).eq("name", name).execute()

        await self.load_from_db()
        await interaction.response.send_message(f"✅ Updated response for **{name}**.", ephemeral=True)

    # ========================
    # ❌ DELETE LIST
    # ========================
    @app_commands.command(name="ar_delete_list")
    @admin_channel_only()
    async def ar_delete_list(self, interaction: discord.Interaction, name: str):
        supabase.table("autoresponses").delete().eq("name", name).execute()

        await self.load_from_db()
        await interaction.response.send_message(f"🗑️ Deleted list **{name}**.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoResponder(bot))
