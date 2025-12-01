import discord
from discord.ext import commands
import datetime
import asyncio

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def log_mod_action(self, guild, embed):
        """Helper to log mod actions using the Logging cog if available."""
        logging_cog = self.bot.get_cog("Logging")
        if logging_cog:
            await logging_cog.log_event(guild, "members", embed)

    async def add_infraction(self, guild_id, user_id, mod_id, type, reason):
        timestamp = datetime.datetime.now().isoformat()
        await self.bot.db.execute("INSERT INTO infractions (guild_id, user_id, mod_id, type, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?)", 
                                  (guild_id, user_id, mod_id, type, reason, timestamp))
        await self.bot.db.commit()

    # --- Commands ---
    @commands.hybrid_command(description="Kick a user.")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if member.top_role >= ctx.author.top_role:
            await ctx.send("You cannot kick this user.")
            return

        await member.kick(reason=reason)
        await self.add_infraction(ctx.guild.id, member.id, ctx.author.id, "Kick", reason)
        
        embed = discord.Embed(description=f"**{member.mention} was kicked**", color=discord.Color.orange())
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Mod: {ctx.author}")
        await ctx.send(embed=embed)
        await self.log_mod_action(ctx.guild, embed)

    @commands.hybrid_command(description="Ban a user.")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if member.top_role >= ctx.author.top_role:
            await ctx.send("You cannot ban this user.")
            return

        await member.ban(reason=reason)
        await self.add_infraction(ctx.guild.id, member.id, ctx.author.id, "Ban", reason)

        embed = discord.Embed(description=f"**{member.mention} was banned**", color=discord.Color.red())
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Mod: {ctx.author}")
        await ctx.send(embed=embed)
        await self.log_mod_action(ctx.guild, embed)

    @commands.hybrid_command(description="Timeout (mute) a user.")
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
        # Parse duration (e.g., 10m, 1h)
        unit = duration[-1]
        try:
            val = int(duration[:-1])
        except:
            await ctx.send("Invalid duration format (e.g., 10m, 1h).")
            return

        delta = None
        if unit == 'm': delta = datetime.timedelta(minutes=val)
        elif unit == 'h': delta = datetime.timedelta(hours=val)
        elif unit == 'd': delta = datetime.timedelta(days=val)
        else:
            await ctx.send("Invalid unit. Use m, h, or d.")
            return

        if member.top_role >= ctx.author.top_role:
            await ctx.send("You cannot mute this user.")
            return

        await member.timeout(delta, reason=reason)
        await self.add_infraction(ctx.guild.id, member.id, ctx.author.id, "Mute", reason)

        embed = discord.Embed(description=f"**{member.mention} was muted for {duration}**", color=discord.Color.yellow())
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Mod: {ctx.author}")
        await ctx.send(embed=embed)
        await self.log_mod_action(ctx.guild, embed)

    @commands.hybrid_command(description="Remove timeout from a user.")
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        await member.timeout(None)
        await ctx.send(f"🔊 {member.mention} has been unmuted.")

    @commands.hybrid_command(description="Warn a user.")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        await self.add_infraction(ctx.guild.id, member.id, ctx.author.id, "Warn", reason)
        
        embed = discord.Embed(description=f"**{member.mention} was warned**", color=discord.Color.gold())
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Mod: {ctx.author}")
        await ctx.send(embed=embed)
        
        try:
            await member.send(f"⚠️ You were warned in **{ctx.guild.name}**: {reason}")
        except:
            pass
        
        await self.log_mod_action(ctx.guild, embed)

    @commands.hybrid_command(description="View user infraction history.")
    @commands.has_permissions(manage_messages=True)
    async def history(self, ctx, member: discord.Member):
        async with self.bot.db.execute("SELECT type, reason, mod_id, timestamp FROM infractions WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 10", (ctx.guild.id, member.id)) as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send(f"{member.mention} has no infractions.")
            return

        embed = discord.Embed(title=f"Infractions for {member}", color=discord.Color.dark_grey())
        for type, reason, mod_id, timestamp in rows:
            mod = ctx.guild.get_member(mod_id)
            mod_name = mod.name if mod else f"ID: {mod_id}"
            date = timestamp.split('T')[0]
            embed.add_field(name=f"{type} - {date}", value=f"**Reason:** {reason}\n**Mod:** {mod_name}", inline=False)
        
        await ctx.send(embed=embed)

    @commands.hybrid_group(name="role", description="Manage roles.")
    @commands.has_permissions(manage_roles=True)
    async def role_cmd(self, ctx):
        await ctx.send("Use `/role all add` or `/role all remove`.")

    @role_cmd.group(name="all", description="Bulk role management.")
    async def role_all(self, ctx):
        pass

    @role_all.command(name="add", description="Add a role to all humans.")
    async def role_all_add(self, ctx, role: discord.Role):
        msg = await ctx.send(f"Adding {role.mention} to all members... This may take a while.")
        count = 0
        for member in ctx.guild.members:
            if not member.bot and role not in member.roles:
                try:
                    await member.add_roles(role)
                    count += 1
                    await asyncio.sleep(0.1) # Rate limit prevention
                except:
                    pass
        await msg.edit(content=f"✅ Added {role.mention} to {count} members.")

    @role_all.command(name="remove", description="Remove a role from all humans.")
    async def role_all_remove(self, ctx, role: discord.Role):
        msg = await ctx.send(f"Removing {role.mention} from all members... This may take a while.")
        count = 0
        for member in ctx.guild.members:
            if not member.bot and role in member.roles:
                try:
                    await member.remove_roles(role)
                    count += 1
                    await asyncio.sleep(0.1)
                except:
                    pass
        await msg.edit(content=f"✅ Removed {role.mention} from {count} members.")

    # --- Sticky Roles ---
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        # Save roles
        role_ids = [str(r.id) for r in member.roles if r.name != "@everyone"]
        if role_ids:
            await self.bot.db.execute("INSERT OR REPLACE INTO sticky_roles (guild_id, user_id, role_ids) VALUES (?, ?, ?)", 
                                      (member.guild.id, member.id, ",".join(role_ids)))
            await self.bot.db.commit()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Restore roles
        async with self.bot.db.execute("SELECT role_ids FROM sticky_roles WHERE guild_id = ? AND user_id = ?", (member.guild.id, member.id)) as cursor:
            row = await cursor.fetchone()
        
        if row:
            role_ids = row[0].split(",")
            roles_to_add = []
            for r_id in role_ids:
                role = member.guild.get_role(int(r_id))
                if role: roles_to_add.append(role)
            
            if roles_to_add:
                try:
                    await member.add_roles(*roles_to_add)
                except:
                    pass

async def setup(bot):
    await bot.add_cog(Moderation(bot))
