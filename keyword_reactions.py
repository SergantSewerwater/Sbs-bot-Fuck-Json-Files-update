import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    raise ValueError("SUPABASE_URL or SERVICE_ROLE_KEY not found in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

# Role ID required to add/remove keywords
KEYWORD_MANAGER_ROLE_ID = 899796185966075905


class KeywordReactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._keyword_cache = {}  # Cache for keywords: {keyword_lower: emoji}
        self._cache_loaded = False
        self.load_keywords()

    def has_keyword_manager_role(self, user: discord.Member) -> bool:
        """Check if user has the keyword manager role."""
        return any(role.id == KEYWORD_MANAGER_ROLE_ID for role in user.roles)

    def load_keywords(self):
        """Load all keywords from Supabase into cache."""
        try:
            res = supabase.table("keyword_reactions").select("keyword, emoji").execute()
            self._keyword_cache = {}
            for row in res.data or []:
                # Store keywords in lowercase for case-insensitive matching
                keyword_lower = row["keyword"].lower()
                self._keyword_cache[keyword_lower] = row["emoji"]
            self._cache_loaded = True
            print(f"[KeywordReactions] Loaded {len(self._keyword_cache)} keywords from Supabase")
        except Exception as e:
            print(f"[KeywordReactions] Error loading keywords: {e}")
            self._keyword_cache = {}

    @app_commands.command(name="addkeyword", description="Add a keyword that triggers an emoji reaction")
    @app_commands.describe(
        keywords="The keyword(s) to watch for, separated by commas (case-insensitive)",
        emoji="The emoji to react with"
    )
    async def add_keyword(self, interaction: discord.Interaction, keywords: str, emoji: str):
        """Add new keyword-emoji pair(s) to the database. Multiple keywords can be comma-separated."""
        # Check role permission
        if not isinstance(interaction.user, discord.Member) or not self.has_keyword_manager_role(interaction.user):
            await interaction.response.send_message(
                "❌ You need the Keyword Manager role to add keywords!",
                ephemeral=True
            )
            return

        try:
            # Validate emoji (basic check - Discord emoji or unicode)
            if not emoji or len(emoji) == 0:
                await interaction.response.send_message("❌ Please provide a valid emoji!", ephemeral=True)
                return

            # Split keywords by comma and clean them
            keyword_list = [kw.strip().lower() for kw in keywords.split(",")]
            keyword_list = [kw for kw in keyword_list if kw]  # Remove empty strings

            if not keyword_list:
                await interaction.response.send_message("❌ Please provide at least one valid keyword!", ephemeral=True)
                return

            # Check for existing keywords
            existing_keywords = []
            new_keywords = []
            
            for keyword_clean in keyword_list:
                existing = supabase.table("keyword_reactions").select("*").eq("keyword", keyword_clean).execute()
                if existing.data:
                    existing_keywords.append(keyword_clean)
                else:
                    new_keywords.append(keyword_clean)

            # Insert new keywords
            if new_keywords:
                payload = [
                    {
                        "keyword": kw,
                        "emoji": emoji,
                        "added_by": str(interaction.user.id)
                    }
                    for kw in new_keywords
                ]
                supabase.table("keyword_reactions").insert(payload).execute()

                # Update cache
                for kw in new_keywords:
                    self._keyword_cache[kw] = emoji

            # Build response message
            response_parts = []
            if new_keywords:
                response_parts.append(f"✅ Added {len(new_keywords)} keyword(s): {', '.join([f'`{kw}`' for kw in new_keywords])} → {emoji}")
            if existing_keywords:
                response_parts.append(f"⚠️ Already existed: {', '.join([f'`{kw}`' for kw in existing_keywords])}")

            await interaction.response.send_message(
                "\n".join(response_parts),
                ephemeral=False
            )
        except Exception as e:
            print(f"[KeywordReactions] Error adding keyword: {e}")
            await interaction.response.send_message(
                f"❌ Error adding keyword: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="removekeyword", description="Remove a keyword reaction")
    @app_commands.describe(keywords="The keyword(s) to remove, separated by commas")
    async def remove_keyword(self, interaction: discord.Interaction, keywords: str):
        """Remove keyword-emoji pair(s) from the database. Multiple keywords can be comma-separated."""
        # Check role permission
        if not isinstance(interaction.user, discord.Member) or not self.has_keyword_manager_role(interaction.user):
            await interaction.response.send_message(
                "❌ You need the Keyword Manager role to remove keywords!",
                ephemeral=True
            )
            return

        try:
            # Split keywords by comma and clean them
            keyword_list = [kw.strip().lower() for kw in keywords.split(",")]
            keyword_list = [kw for kw in keyword_list if kw]  # Remove empty strings

            if not keyword_list:
                await interaction.response.send_message("❌ Please provide at least one valid keyword!", ephemeral=True)
                return

            # Check for existing keywords and delete them
            removed_keywords = []
            not_found_keywords = []

            for keyword_clean in keyword_list:
                existing = supabase.table("keyword_reactions").select("*").eq("keyword", keyword_clean).execute()
                if not existing.data:
                    not_found_keywords.append(keyword_clean)
                else:
                    supabase.table("keyword_reactions").delete().eq("keyword", keyword_clean).execute()
                    removed_keywords.append(keyword_clean)
                    
                    # Update cache
                    if keyword_clean in self._keyword_cache:
                        del self._keyword_cache[keyword_clean]

            # Build response message
            response_parts = []
            if removed_keywords:
                response_parts.append(f"✅ Removed {len(removed_keywords)} keyword(s): {', '.join([f'`{kw}`' for kw in removed_keywords])}")
            if not_found_keywords:
                response_parts.append(f"⚠️ Not found: {', '.join([f'`{kw}`' for kw in not_found_keywords])}")

            await interaction.response.send_message(
                "\n".join(response_parts),
                ephemeral=False
            )
        except Exception as e:
            print(f"[KeywordReactions] Error removing keyword: {e}")
            await interaction.response.send_message(
                f"❌ Error removing keyword: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="listkeywords", description="List all keyword reactions")
    async def list_keywords(self, interaction: discord.Interaction):
        """List all current keyword-emoji pairs."""
        try:
            if not self._keyword_cache:
                await interaction.response.send_message(
                    "📋 No keywords configured yet.",
                    ephemeral=False
                )
                return

            # Build embed
            embed = discord.Embed(
                title="📋 Keyword Reactions",
                description=f"Total: {len(self._keyword_cache)} keywords",
                color=discord.Color.blue()
            )

            # Add fields (discord max 25 fields, so limit for safety)
            for i, (keyword, emoji) in enumerate(list(self._keyword_cache.items())[:25]):
                embed.add_field(name=keyword, value=emoji, inline=True)

            await interaction.response.send_message(embed=embed, ephemeral=False)
        except Exception as e:
            print(f"[KeywordReactions] Error listing keywords: {e}")
            await interaction.response.send_message(
                f"❌ Error listing keywords: {str(e)}",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """React to messages containing keywords."""
        # Ignore bot messages and system messages
        if message.author.bot or message.author == self.bot.user:
            return

        # Skip if cache not loaded
        if not self._cache_loaded or not self._keyword_cache:
            return

        try:
            message_lower = message.content.lower()
            reacted = False

            # Check each keyword
            for keyword, emoji in self._keyword_cache.items():
                # Check if keyword appears as a word (with word boundaries)
                if keyword in message_lower:
                    try:
                        await message.add_reaction(emoji)
                        reacted = True
                    except discord.errors.HTTPException as e:
                        print(f"[KeywordReactions] Could not add reaction {emoji}: {e}")

        except Exception as e:
            print(f"[KeywordReactions] Error in on_message: {e}")


async def setup(bot):
    await bot.add_cog(KeywordReactions(bot))
