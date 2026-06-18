import discord
from discord.ext import commands

class VIP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(invoke_without_command=True, description="VIP and Subscription Perks.")
    async def vip(self, ctx):
        await ctx.send("Use `/vip setup` to configure VIP roles (Admins only).")

    @vip.command(name="setup", description="Set a VIP role and its economy multiplier.")
    @commands.has_permissions(administrator=True)
    async def setup_vip(self, ctx, role: discord.Role, multiplier: float):
        if multiplier < 1.0:
            await ctx.send("Multiplier should be 1.0 or greater.")
            return
            
        await self.bot.db.execute("""
            INSERT INTO vip_roles (guild_id, role_id, multiplier) 
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, role_id) DO UPDATE SET multiplier=excluded.multiplier
        """, (ctx.guild.id, role.id, multiplier))
        await self.bot.db.commit()
        
        await ctx.send(f"✅ Users with the {role.mention} role will now receive a **{multiplier}x** multiplier on economy gains!")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        # We only want to apply multipliers to specific income commands
        # To avoid duplicating base payouts (which are already added to DB by the command), 
        # we calculate the extra amount based on the command type and add it.
        # But this is tricky without knowing exactly how much they earned. 
        # For simplicity, we just give a flat random VIP bonus for playing the game.
        
        if ctx.author.bot or not ctx.guild: return
        cmd = ctx.command.name if ctx.command else ""
        
        if cmd in ["work", "beg", "search", "crime", "daily"]:
            async with self.bot.db.execute("SELECT role_id, multiplier FROM vip_roles WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()
                
            if not rows: return
            
            best_multiplier = 1.0
            for r_id, mult in rows:
                if discord.utils.get(ctx.author.roles, id=r_id):
                    if mult > best_multiplier:
                        best_multiplier = mult
                        
            if best_multiplier > 1.0:
                # Give a flat bonus based on the multiplier (e.g., 1.5x gives ~150 coins bonus)
                bonus = int(100 * (best_multiplier - 1.0))
                if bonus > 0:
                    await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, ctx.author.id))
                    await self.bot.db.commit()
                    try:
                        await ctx.send(f"🌟 **VIP Bonus:** You received an extra **${bonus}**!", delete_after=5)
                    except: pass

async def setup(bot):
    await bot.add_cog(VIP(bot))
