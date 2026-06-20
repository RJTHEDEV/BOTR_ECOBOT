import discord
from discord.ext import commands

class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(invoke_without_command=True, description="Manage server settings.")
    @discord.app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        await ctx.send("Use `/config view` or `/config set <setting> <value>`.")

    @config.command(name="view", description="View current server settings.")
    @discord.app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def view_config(self, ctx):
        async with self.bot.db.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            await self.bot.db.execute("INSERT INTO guild_settings (guild_id) VALUES (?)", (ctx.guild.id,))
            await self.bot.db.commit()
            row = (ctx.guild.id, None, 3, '⭐', None, None, None, None)

        guild_id, sb_chan, sb_thresh, sb_emoji, log_chan, auto_role, live_role, bot_admin = row

        embed = discord.Embed(title=f"⚙️ Server Settings for {ctx.guild.name}", color=discord.Color.blue())
        
        sb_channel_str = f"<#{sb_chan}>" if sb_chan else "Not set"
        log_channel_str = f"<#{log_chan}>" if log_chan else "Not set"
        auto_role_str = f"<@&{auto_role}>" if auto_role else "Not set"
        live_role_str = f"<@&{live_role}>" if live_role else "Not set"
        bot_admin_str = f"<@&{bot_admin}>" if bot_admin else "Not set"

        embed.add_field(name="⭐ Starboard", value=f"Channel: {sb_channel_str}\nThreshold: {sb_thresh}\nEmoji: {sb_emoji}", inline=False)
        embed.add_field(name="📝 Logging", value=f"Channel: {log_channel_str}", inline=False)
        embed.add_field(name="🎭 Roles", value=f"Auto Role: {auto_role_str}\nLive Role: {live_role_str}", inline=False)
        embed.add_field(name="🛡️ Admin", value=f"Bot Admin Role: {bot_admin_str}", inline=False)

        await ctx.send(embed=embed)

    @config.command(name="set_starboard", description="Configure starboard settings.")
    @discord.app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def set_starboard(self, ctx, channel: discord.TextChannel = None, threshold: int = 3, emoji: str = "⭐"):
        channel_id = channel.id if channel else None
        await self.bot.db.execute("""
            INSERT INTO guild_settings (guild_id, starboard_channel_id, starboard_threshold, starboard_emoji) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET 
            starboard_channel_id=excluded.starboard_channel_id,
            starboard_threshold=excluded.starboard_threshold,
            starboard_emoji=excluded.starboard_emoji
        """, (ctx.guild.id, channel_id, threshold, emoji))
        await self.bot.db.commit()
        await ctx.send("✅ Starboard settings updated.")

    @config.command(name="set_log", description="Set the logging channel.")
    @discord.app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def set_log(self, ctx, channel: discord.TextChannel = None):
        channel_id = channel.id if channel else None
        await self.bot.db.execute("""
            INSERT INTO guild_settings (guild_id, log_channel_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET log_channel_id=excluded.log_channel_id
        """, (ctx.guild.id, channel_id))
        await self.bot.db.commit()
        await ctx.send("✅ Log channel updated.")

    @config.command(name="set_roles", description="Set auto-role and live-role.")
    @discord.app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def set_roles(self, ctx, auto_role: discord.Role = None, live_role: discord.Role = None):
        auto_id = auto_role.id if auto_role else None
        live_id = live_role.id if live_role else None
        await self.bot.db.execute("""
            INSERT INTO guild_settings (guild_id, auto_role_id, live_role_id) VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET 
            auto_role_id=excluded.auto_role_id,
            live_role_id=excluded.live_role_id
        """, (ctx.guild.id, auto_id, live_id))
        await self.bot.db.commit()
        await ctx.send("✅ Role settings updated.")

async def setup(bot):
    await bot.add_cog(Config(bot))
