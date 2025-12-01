import discord
from discord.ext import commands
import datetime
import re
from typing import Union

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_regex = re.compile(r"(discord\.gg\/|discord\.com\/invite\/)([a-zA-Z0-9]+)")

    async def get_log_channel(self, guild_id, log_type):
        """Get the channel ID for a specific log type."""
        # Check specific log type first
        async with self.bot.db.execute("SELECT channel_id FROM log_settings WHERE guild_id = ? AND log_type = ?", (guild_id, log_type)) as cursor:
            row = await cursor.fetchone()
            if row: return row[0]
        
        # Fallback to 'all'
        async with self.bot.db.execute("SELECT channel_id FROM log_settings WHERE guild_id = ? AND log_type = 'all'", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            if row: return row[0]
        
        return None

    async def is_ignored(self, guild_id, target_id, ignore_type):
        """Check if a user or channel is ignored."""
        async with self.bot.db.execute("SELECT 1 FROM log_ignores WHERE guild_id = ? AND ignore_type = ? AND target_id = ?", (guild_id, ignore_type, target_id)) as cursor:
            return await cursor.fetchone() is not None

    async def log_event(self, guild, log_type, embed):
        """Helper to send log embed to the configured channel."""
        channel_id = await self.get_log_channel(guild.id, log_type)
        if not channel_id: return

        channel = guild.get_channel(channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass

    # --- Commands ---
    @commands.hybrid_group(name="log", description="Manage logging settings.")
    @commands.has_permissions(administrator=True)
    async def log_cmd(self, ctx):
        await ctx.send("Use `/log set`, `/log disable`, or `/log ignore`.")

    @log_cmd.command(description="Set a logging channel for a specific category.")
    async def set(self, ctx, log_type: str, channel: str):
        await ctx.defer()
        
        channel_obj = None
        
        # 1. Try Converter (Handles IDs, Mentions, Exact Names)
        try:
            channel_obj = await commands.TextChannelConverter().convert(ctx, channel)
        except:
            pass
            
        # 2. Manual Search (Case-insensitive name match)
        if not channel_obj:
            target_name = channel.lower().replace("#", "").strip()
            for ch in ctx.guild.text_channels:
                if ch.name.lower() == target_name:
                    channel_obj = ch
                    break
        
        if not channel_obj:
            await ctx.send(f"❌ Could not find channel: `{channel}`. Make sure I have permission to see it.")
            return

        """
        log_type: join_leave, messages, voice, other, market_alerts, or all
        """
        valid_types = ["join_leave", "messages", "voice", "other", "market_alerts", "all"]
        if log_type not in valid_types:
            await ctx.send(f"Invalid type. Choose from: {', '.join(valid_types)}")
            return

        try:
            print(f"Setting log: Guild={ctx.guild.id}, Type={log_type}, Channel={channel_obj.id}")
            await self.bot.db.execute("INSERT OR REPLACE INTO log_settings (guild_id, log_type, channel_id) VALUES (?, ?, ?)", (ctx.guild.id, log_type, channel_obj.id))
            await self.bot.db.commit()
            print("Database commit successful")
            await ctx.send(f"✅ Logging for **{log_type}** set to {channel_obj.mention}.")
        except Exception as e:
            print(f"Error setting log: {e}")
            await ctx.send(f"❌ Error setting log: {e}")

    @log_cmd.command(description="Disable logging for a category.")
    async def disable(self, ctx, log_type: str):
        await ctx.defer()
        await self.bot.db.execute("DELETE FROM log_settings WHERE guild_id = ? AND log_type = ?", (ctx.guild.id, log_type))
        await self.bot.db.commit()
        await ctx.send(f"🚫 Logging for **{log_type}** disabled.")

    @log_cmd.group(name="ignore", description="Manage ignored channels/users.")
    async def ignore_cmd(self, ctx):
        await ctx.send("Use `/log ignore add` or `/log ignore list`.")

    @ignore_cmd.command(description="Ignore a channel or user.")
    async def add(self, ctx, target: str):
        await ctx.defer()
        # Try to resolve target
        try:
            # Check if channel
            channel = await commands.TextChannelConverter().convert(ctx, target)
            t_type, t_id = "channel", channel.id
        except:
            try:
                # Check if user
                user = await commands.MemberConverter().convert(ctx, target)
                t_type, t_id = "user", user.id
            except:
                await ctx.send("Could not resolve target. Please mention a channel or user.")
                return

        await self.bot.db.execute("INSERT OR IGNORE INTO log_ignores (guild_id, ignore_type, target_id) VALUES (?, ?, ?)", (ctx.guild.id, t_type, t_id))
        await self.bot.db.commit()
        await ctx.send(f"🔇 Ignored {t_type}: {target}")

    @ignore_cmd.command(name="list", description="List ignored items.")
    async def list_ignores(self, ctx):
        await ctx.defer()
        async with self.bot.db.execute("SELECT ignore_type, target_id FROM log_ignores WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("No ignored items.")
            return

        desc = ""
        for t_type, t_id in rows:
            if t_type == "channel":
                desc += f"📺 <#{t_id}>\n"
            elif t_type == "user":
                desc += f"👤 <@{t_id}>\n"
        
        embed = discord.Embed(title="Ignored Items", description=desc, color=discord.Color.dark_grey())
        await ctx.send(embed=embed)

    # --- Events ---

    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = discord.Embed(title="Member Joined", description=f"{member.mention} {member.name}", color=discord.Color.green())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
        embed.set_footer(text=f"ID: {member.id}")
        await self.log_event(member.guild, "join_leave", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = discord.Embed(title="Member Left", description=f"{member.mention} {member.name}", color=discord.Color.red())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        await self.log_event(member.guild, "join_leave", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot: return
        if before.content == after.content: return

        embed = discord.Embed(title="Message Edited", description=f"In {before.channel.mention} by {before.author.mention}", color=discord.Color.orange())
        embed.add_field(name="Before", value=before.content[:1024] or "[No Content]", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "[No Content]", inline=False)
        embed.set_footer(text=f"ID: {before.id}")
        await self.log_event(before.guild, "messages", embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: return

        embed = discord.Embed(title="Message Deleted", description=f"In {message.channel.mention} by {message.author.mention}", color=discord.Color.red())
        embed.add_field(name="Content", value=message.content[:1024] or "[No Content]", inline=False)
        embed.set_footer(text=f"ID: {message.id}")
        await self.log_event(message.guild, "messages", embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel: return # State change (mute/deafen) not channel move

        embed = discord.Embed(color=discord.Color.blue())
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        
        if before.channel is None:
            # Joined
            embed.title = "Joined Voice Channel"
            embed.description = f"{member.mention} joined **{after.channel.name}**"
            embed.color = discord.Color.green()
        elif after.channel is None:
            # Left
            embed.title = "Left Voice Channel"
            embed.description = f"{member.mention} left **{before.channel.name}**"
            embed.color = discord.Color.red()
        else:
            # Moved
            embed.title = "Moved Voice Channel"
            embed.description = f"{member.mention} moved from **{before.channel.name}** to **{after.channel.name}**"
            embed.color = discord.Color.orange()

        await self.log_event(member.guild, "voice", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles != after.roles:
            # Role change
            added = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)
            
            if added:
                role_names = ", ".join([r.name for r in added])
                embed = discord.Embed(title="Roles Added", description=f"{after.mention}: {role_names}", color=discord.Color.blue())
                await self.log_event(after.guild, "other", embed)
            if removed:
                role_names = ", ".join([r.name for r in removed])
                embed = discord.Embed(title="Roles Removed", description=f"{after.mention}: {role_names}", color=discord.Color.orange())
                await self.log_event(after.guild, "other", embed)
        
        if before.nick != after.nick:
            embed = discord.Embed(title="Nickname Changed", description=f"{after.mention}", color=discord.Color.blue())
            embed.add_field(name="Before", value=before.nick or "[None]")
            embed.add_field(name="After", value=after.nick or "[None]")
            await self.log_event(after.guild, "other", embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = discord.Embed(title="Member Banned", description=f"{user.mention} {user.name}", color=discord.Color.red())
        embed.set_footer(text=f"ID: {user.id}")
        await self.log_event(guild, "other", embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        embed = discord.Embed(title="Member Unbanned", description=f"{user.mention} {user.name}", color=discord.Color.green())
        embed.set_footer(text=f"ID: {user.id}")
        await self.log_event(guild, "other", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(title="Channel Created", description=f"{channel.mention} ({channel.name})", color=discord.Color.green())
        await self.log_event(channel.guild, "other", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(title="Channel Deleted", description=f"{channel.name}", color=discord.Color.red())
        await self.log_event(channel.guild, "other", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = discord.Embed(title="Role Created", description=f"{role.name}", color=discord.Color.green())
        await self.log_event(role.guild, "other", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = discord.Embed(title="Role Deleted", description=f"{role.name}", color=discord.Color.red())
        await self.log_event(role.guild, "other", embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if before.name != after.name:
            embed = discord.Embed(title="Role Updated", description=f"Name changed from **{before.name}** to **{after.name}**", color=discord.Color.orange())
            await self.log_event(after.guild, "other", embed)

async def setup(bot):
    await bot.add_cog(Logging(bot))
