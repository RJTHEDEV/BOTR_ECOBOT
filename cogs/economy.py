import discord
from discord.ext import commands
import random
import time

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_tracking = {}

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

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        # Simple engage to earn logic: random chance to get coins/xp
        if random.random() < 0.1: # 10% chance
            reward = random.randint(1, 5)
            async with self.bot.db.execute("SELECT balance, xp FROM users WHERE user_id = ?", (message.author.id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    await self.bot.db.execute("INSERT INTO users (user_id, balance, xp) VALUES (?, ?, ?)", (message.author.id, reward, reward))
                else:
                    await self.bot.db.execute("UPDATE users SET balance = balance + ?, xp = xp + ? WHERE user_id = ?", (reward, reward, message.author.id))
            await self.bot.db.commit()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

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
                    reward = minutes * 2 # 2 coins per minute
                    async with self.bot.db.execute("SELECT balance, xp FROM users WHERE user_id = ?", (member.id,)) as cursor:
                        row = await cursor.fetchone()
                        if not row:
                            await self.bot.db.execute("INSERT INTO users (user_id, balance, xp) VALUES (?, ?, ?)", (member.id, reward, reward))
                        else:
                            await self.bot.db.execute("UPDATE users SET balance = balance + ?, xp = xp + ? WHERE user_id = ?", (reward, reward, member.id))
                    await self.bot.db.commit()
                    # Optional: DM user or log it
                    # await member.send(f"You earned ${reward} for spending {minutes} minutes in voice chat!")

async def setup(bot):
    await bot.add_cog(Economy(bot))
