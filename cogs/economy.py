import discord
from discord.ext import commands
import random
import time

LEVEL_ROLES = {
    1: "Level 1",
    5: "Level 5",
    10: "Level 10",
    20: "Level 20",
    30: "Level 30",
    40: "Level 40",
    50: "Level 50"
}

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_tracking = {}
        self.last_xp_time = {} # {user_id: timestamp}

    async def add_xp(self, user, amount):
        if user.bot: return

        # Booster Multiplier (2x)
        if user.premium_since:
            amount *= 2

        async with self.bot.db.execute("SELECT xp, level FROM users WHERE user_id = ?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                current_xp, current_level = 0, 1
                await self.bot.db.execute("INSERT INTO users (user_id, xp, level, balance) VALUES (?, ?, ?, ?)", (user.id, amount, 1, 0))
            else:
                current_xp, current_level = row
                await self.bot.db.execute("UPDATE users SET xp = xp + ? WHERE user_id = ?", (amount, user.id))
        
        await self.bot.db.commit()
        
        # Level Up Check
        new_xp = current_xp + amount
        # Simple formula: Level = 0.1 * sqrt(XP)  => XP = (Level / 0.1)^2 = (Level * 10)^2 = 100 * Level^2
        # Let's use a linear/exponential curve: XP needed = 100 * Level
        xp_needed = 100 * current_level
        
        if new_xp >= xp_needed:
            new_level = current_level + 1
            await self.bot.db.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, user.id))
            await self.bot.db.commit()
            
            # Announce Level Up
            try:
                await user.send(f"🎉 **Level Up!** You are now Level {new_level}!")
            except:
                pass

            # Assign Role
            if new_level in LEVEL_ROLES:
                role_name = LEVEL_ROLES[new_level]
                role = discord.utils.get(user.guild.roles, name=role_name)
                if role:
                    try:
                        await user.add_roles(role)
                        await user.send(f"🏅 You earned the **{role_name}** role!")
                    except:
                        pass

    @commands.hybrid_command(description="Check your coin and ticket balance.")
    async def balance(self, ctx):
        async with self.bot.db.execute("SELECT balance, xp, level, tickets FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await self.bot.db.execute("INSERT INTO users (user_id) VALUES (?)", (ctx.author.id,))
                await self.bot.db.commit()
                balance, xp, level, tickets = 0, 0, 1, 0
            else:
                balance, xp, level, tickets = row
        
        embed = discord.Embed(title=f"{ctx.author.name}'s Wallet", color=discord.Color.green())
        embed.add_field(name="Balance", value=f"${balance}", inline=True)
        embed.add_field(name="Tickets", value=f"🎟️ {tickets}", inline=True)
        embed.add_field(name="Level", value=f"{level} (XP: {xp})", inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Check your ticket balance.")
    async def tickets(self, ctx):
        async with self.bot.db.execute("SELECT tickets FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            tickets = row[0] if row else 0
        await ctx.send(f"You have 🎟️ {tickets} tickets.")

    @commands.hybrid_command(description="Claim your daily reward.")
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily(self, ctx):
        amount = 100
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await self.bot.db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (ctx.author.id, amount))
            else:
                await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, ctx.author.id))
        await self.bot.db.commit()
        await ctx.send(f"You claimed your daily reward of ${amount}!")

    @commands.hybrid_command(description="Admin: Give coins to a user.")
    @commands.has_permissions(administrator=True)
    async def give(self, ctx, member: discord.Member, amount: int):
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await self.bot.db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (member.id, amount))
            else:
                await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, member.id))
        await self.bot.db.commit()
        await ctx.send(f"Gave ${amount} to {member.mention}.")

    @commands.hybrid_command(description="Admin: Give tickets to a user.")
    @commands.has_permissions(administrator=True)
    async def givetickets(self, ctx, member: discord.Member, amount: int):
        async with self.bot.db.execute("SELECT tickets FROM users WHERE user_id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await self.bot.db.execute("INSERT INTO users (user_id, tickets) VALUES (?, ?)", (member.id, amount))
            else:
                await self.bot.db.execute("UPDATE users SET tickets = tickets + ? WHERE user_id = ?", (amount, member.id))
        await self.bot.db.commit()
        await ctx.send(f"Gave 🎟️ {amount} tickets to {member.mention}.")

    @commands.hybrid_command(description="View the XP Leaderboard.")
    async def leaderboard(self, ctx):
        async with self.bot.db.execute("SELECT user_id, xp, level FROM users ORDER BY xp DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("No data yet.")
            return

        embed = discord.Embed(title="🏆 XP Leaderboard", color=discord.Color.gold())
        for i, (user_id, xp, level) in enumerate(rows, 1):
            user = ctx.guild.get_member(user_id)
            name = user.display_name if user else f"User {user_id}"
            embed.add_field(name=f"#{i} {name}", value=f"Level {level} | {xp} XP", inline=False)
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        
        # XP Cooldown (60s)
        now = time.time()
        last_time = self.last_xp_time.get(message.author.id, 0)
        
        if now - last_time >= 60:
            xp_amount = random.randint(15, 25)
            await self.add_xp(message.author, xp_amount)
            self.last_xp_time[message.author.id] = now

        # Random Coin Drop (Engage to Earn)
        if random.random() < 0.05: # 5% chance
            reward = random.randint(1, 5)
            async with self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, message.author.id)) as cursor:
                if cursor.rowcount == 0:
                     await self.bot.db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (message.author.id, reward))
            await self.bot.db.commit()

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or not reaction.message.guild: return
        # 5 XP for reacting
        await self.add_xp(user, 5)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return

        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            self.voice_tracking[member.id] = time.time()
        
        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            if member.id in self.voice_tracking:
                start_time = self.voice_tracking.pop(member.id)
                duration = time.time() - start_time
                minutes = int(duration / 60)
                
                if minutes > 0:
                    # 10 XP per 10 minutes = 1 XP per minute (simplified)
                    # Let's do 1 XP per minute for smoother tracking
                    xp_reward = minutes * 1 
                    await self.add_xp(member, xp_reward)
                    
                    # Coins: 2 per minute
                    coin_reward = minutes * 2
                    async with self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (coin_reward, member.id)) as cursor:
                         if cursor.rowcount == 0:
                             await self.bot.db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (member.id, coin_reward))
                    await self.bot.db.commit()

async def setup(bot):
    await bot.add_cog(Economy(bot))
