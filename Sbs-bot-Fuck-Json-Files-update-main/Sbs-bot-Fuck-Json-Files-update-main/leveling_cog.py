import os
import logging
import asyncio
import aiosqlite
import discord
from discord.ext import commands

try:
    from discordLevelingSystem import DiscordLevelingSystem
except Exception:
    DiscordLevelingSystem = None


class LevelingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dls = None
        self.db_path = os.path.join(os.getcwd(), 'DiscordLevelingSystem.db')

    async def cog_load(self):
        # Ensure DB exists (create with the expected schema if missing)
        if not os.path.exists(self.db_path):
            try:
                conn = await aiosqlite.connect(self.db_path)
                await conn.execute(
                    '''CREATE TABLE leaderboard (
                        guild_id INT NOT NULL,
                        member_id INT NOT NULL,
                        member_name TEXT NOT NULL,
                        member_level INT NOT NULL,
                        member_xp INT NOT NULL,
                        member_total_xp INT NOT NULL
                    );'''
                )
                await conn.commit()
                await conn.close()
            except Exception:
                logging.exception('Failed to create leveling database')

        if DiscordLevelingSystem is None:
            logging.error('discordLevelingSystem package not available; leveling disabled')
            return

        # Initialize the library and connect to DB
        try:
            self.dls = DiscordLevelingSystem(rate=1, per=5.00, announce_level_up=True, bot=self.bot)
            await self.dls.switch_connection(self.db_path)
            logging.info('DiscordLevelingSystem initialized and connected to %s', self.db_path)
        except Exception:
            logging.exception('Failed to initialize DiscordLevelingSystem')

        # Test Supabase connection
        supabase = getattr(self.bot, 'supabase', None)
        if supabase:
            try:
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, self._test_supabase_connection, supabase)
            except Exception:
                logging.exception('Failed to test Supabase connection')

    def _test_supabase_connection(self, supabase):
        """Test if Supabase is reachable and dls_levels table exists."""
        try:
            # Try to fetch one row (or get empty list if no rows exist)
            res = supabase.from_('dls_levels').select('user_id').limit(1).execute()
            logging.info('✅ Supabase connection successful. dls_levels table accessible.')
        except Exception as e:
            logging.error('❌ Supabase connection failed: %s', str(e))

    @commands.Cog.listener('on_message')
    async def on_message(self, message):
        # Ignore bots and DMs
        if message.author.bot or message.guild is None:
            return

        if not self.dls:
            return

        try:
            await self.dls.award_xp(amount=[15, 25], message=message)
        except Exception:
            logging.exception('Error awarding XP for message %s', getattr(message, 'id', None))
            return

        # Fetch member data once (optimized)
        try:
            md = await self.dls.get_data_for(message.author)
            if not md:
                return
        except Exception:
            logging.exception('Failed to fetch member data for %s', getattr(message.author, 'id', None))
            return

        # Log the XP award
        logging.info('XP awarded to %s (ID: %s) | Level: %s | XP: %s / Total XP: %s | Rank: %s', 
                     md.name, md.id_number, md.level, md.xp, md.total_xp, md.rank)

        # Mirror member data to Supabase (non-blocking)
        supabase = getattr(self.bot, 'supabase', None)
        if supabase:
            logging.debug('Supabase client found, syncing user %s', md.id_number)
            # Run Supabase upsert in executor to avoid blocking
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, self._sync_to_supabase, supabase, md)
        else:
            logging.warning('Supabase client not found on bot object')

    def _sync_to_supabase(self, supabase, md):
        """Sync member data to Supabase (non-async, runs in executor)."""
        try:
            user_id = md.id_number
            username = md.name
            level = md.level
            xp = md.xp
            total_xp = md.total_xp
            rank = md.rank

            logging.info('[SUPABASE] Starting sync for user %s (%s)', user_id, username)

            update_payload = {
                'username': username,
                'level': level,
                'xp': xp,
                'total_xp': total_xp,
                'rank': rank,
            }

            # Try update first
            logging.info('[SUPABASE] Attempting UPDATE for user %s with data: level=%s, xp=%s, total_xp=%s, rank=%s', 
                        user_id, level, xp, total_xp, rank)
            
            res = supabase.from_('dls_levels').update(update_payload).eq('user_id', user_id).execute()

            logging.info('[SUPABASE] UPDATE response: %s', res)
            rows_affected = getattr(res, 'count', None)
            logging.info('[SUPABASE] Rows affected by UPDATE: %s (type: %s)', rows_affected, type(rows_affected).__name__)

            # Treat None as 0 (no rows affected)
            if rows_affected is None:
                rows_affected = 0

            if rows_affected == 0:
                logging.info('[SUPABASE] No rows updated, attempting INSERT for user %s', user_id)
                ins_payload = {
                    'user_id': user_id,
                    'username': username,
                    'level': level,
                    'xp': xp,
                    'total_xp': total_xp,
                    'rank': rank,
                }
                logging.info('[SUPABASE] INSERT payload: %s', ins_payload)
                try:
                    insert_res = supabase.from_('dls_levels').insert(ins_payload).execute()
                    logging.info('[SUPABASE] INSERT response: %s', insert_res)
                    logging.info('✅ Inserted leveling record for %s (ID: %s)', username, user_id)
                except Exception as insert_err:
                    # If it's a duplicate key error, it means the record exists but UPDATE didn't find it
                    # This can happen with Supabase RLS or permission issues
                    err_str = str(insert_err)
                    if '23505' in err_str or 'duplicate key' in err_str.lower():
                        logging.info('ℹ️  Record already exists for user %s, falling back to direct update', username)
                        # Try a direct fetch and re-update with RLS bypass
                        try:
                            # Re-attempt update with explicit column names
                            supabase.from_('dls_levels').update(update_payload).eq('user_id', user_id).execute()
                            logging.info('✅ Updated (fallback) leveling record for %s (ID: %s)', username, user_id)
                        except Exception:
                            logging.error('Fallback update also failed, but continuing')
                    else:
                        raise
            else:
                logging.info('✅ Updated leveling record for %s (ID: %s)', username, user_id)
        except Exception as e:
            logging.error('❌ [SUPABASE] Failed to sync for user %s: %s', md.id_number, str(e))
            logging.exception('[SUPABASE] Full exception traceback')

    @commands.hybrid_command(name='level', description='Check your level, XP, and rank')
    async def level_command(self, ctx: commands.Context, member: discord.Member = None):
        """Check your or another member's level and XP"""
        if not self.dls:
            await ctx.send('❌ Leveling system is not available')
            return

        target = member or ctx.author

        try:
            md = await self.dls.get_data_for(target)
            if not md:
                await ctx.send(f'❌ No leveling data found for {target.mention}')
                return

            embed = discord.Embed(
                title=f'{target.name}\'s Level Info',
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name='Level', value=str(md.level), inline=True)
            embed.add_field(name='XP (Current)', value=str(md.xp), inline=True)
            embed.add_field(name='Total XP', value=str(md.total_xp), inline=True)
            embed.add_field(name='Rank', value=str(md.rank) if md.rank else 'Unranked', inline=True)
            embed.set_footer(text=f'User ID: {md.id_number}')

            await ctx.send(embed=embed)
        except Exception:
            logging.exception('Error fetching level data for %s', target.id)
            await ctx.send(f'❌ Error retrieving level data for {target.mention}')

    @commands.hybrid_command(name='xp_leaderboard', description='Show the XP leaderboard')
    async def xp_leaderboard_command(self, ctx: commands.Context, limit: int = 10):
        """Show the top members by XP"""
        if not self.dls:
            await ctx.send('❌ Leveling system is not available')
            return

        if limit < 1 or limit > 100:
            await ctx.send('❌ Limit must be between 1 and 100')
            return

        try:
            members_data = await self.dls.each_member_data(ctx.guild, sort_by='xp', limit=limit)
            
            if not members_data:
                await ctx.send('❌ No leveling data found in this server')
                return

            # Reverse to get highest xp first (each_member_data sorts ascending by default)
            members_data = list(reversed(members_data))

            embed = discord.Embed(
                title=f'🏆 XP Leaderboard - Top {len(members_data)}',
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )

            leaderboard_text = ''
            for idx, md in enumerate(members_data, start=1):
                medal = '🥇' if idx == 1 else '🥈' if idx == 2 else '🥉' if idx == 3 else f'{idx}.'
                leaderboard_text += f'{medal} **{md.name}** - Level {md.level} | {md.xp} XP (Total: {md.total_xp})\n'

            embed.description = leaderboard_text or 'No data'
            embed.set_footer(text=f'{ctx.guild.name}')

            await ctx.send(embed=embed)
        except Exception:
            logging.exception('Error fetching leaderboard data for %s', ctx.guild.id)
            await ctx.send('❌ Error retrieving leaderboard data')


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))
