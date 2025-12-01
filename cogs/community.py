import discord
from discord.ext import commands
import asyncio
import random
import datetime

class Community(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- News ---
    @commands.hybrid_command(description="Admin: Post a news update.")
    @commands.has_permissions(administrator=True)
    async def news(self, ctx, title: str, *, content: str):
        embed = discord.Embed(title=f"📰 {title}", description=content, color=discord.Color.blue())
        embed.set_footer(text=f"Posted by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Get info on how to claim the Active Developer Badge.")
    async def badge(self, ctx):
        await ctx.send("✅ **Command Executed!**\n\nTo claim your **Active Developer Badge**:\n1. Wait up to 24 hours for Discord to update.\n2. Go to: https://discord.com/developers/active-developer\n3. Select this bot and claim your badge!\n\n*(Running any slash command qualifies you, but this one confirms it works!)*")

    # --- Schedule ---
    @commands.hybrid_group(invoke_without_command=True, description="Manage streaming schedule.")
    async def schedule(self, ctx):
        await ctx.send("Use `!schedule view` or `!schedule add`")

    @schedule.command(description="View upcoming events.")
    async def view(self, ctx):
        async with self.bot.db.execute("SELECT event_name, event_time, description FROM schedule ORDER BY event_time") as cursor:
            events = await cursor.fetchall()
        
        if not events:
            await ctx.send("No upcoming events.")
            return

        embed = discord.Embed(title="📅 Streaming Schedule", color=discord.Color.purple())
        for name, time, desc in events:
            embed.add_field(name=f"{time} - {name}", value=desc, inline=False)
        await ctx.send(embed=embed)

    @schedule.command(description="Admin: Add an event to the schedule.")
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, time: str, name: str, *, description: str):
        await self.bot.db.execute("INSERT INTO schedule (event_name, event_time, description) VALUES (?, ?, ?)", (name, time, description))
        await self.bot.db.commit()
        await ctx.send(f"Added event: {name} at {time}")

    # --- Giveaways ---
    @commands.hybrid_command(description="Admin: Start a giveaway.")
    @commands.has_permissions(administrator=True)
    async def gstart(self, ctx, duration: str, winners: int, *, prize: str):
        # Simple duration parser (e.g., 10s, 1m, 1h)
        unit = duration[-1]
        try:
            val = int(duration[:-1])
        except ValueError:
            await ctx.send("Invalid duration format. Use 10s, 1m, 1h.")
            return

        seconds = 0
        if unit == 's': seconds = val
        elif unit == 'm': seconds = val * 60
        elif unit == 'h': seconds = val * 3600
        else:
            await ctx.send("Invalid unit. Use s, m, or h.")
            return

        embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"Prize: **{prize}**\nReact with 🎉 to enter!\nEnds in: {duration}", color=discord.Color.gold())
        embed.set_footer(text=f"{winners} winner(s)")
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("🎉")

        end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        await self.bot.db.execute("INSERT INTO giveaways (message_id, channel_id, prize, end_time, winners_count) VALUES (?, ?, ?, ?, ?)", 
                                  (msg.id, ctx.channel.id, prize, end_time.isoformat(), winners))
        await self.bot.db.commit()

        await asyncio.sleep(seconds)
        await self.end_giveaway(msg.id)

    async def end_giveaway(self, message_id):
        async with self.bot.db.execute("SELECT channel_id, prize, winners_count, ended FROM giveaways WHERE message_id = ?", (message_id,)) as cursor:
            data = await cursor.fetchone()
        
        if not data or data[3]: return # Already ended or doesn't exist

        channel_id, prize, winners_count, _ = data
        channel = self.bot.get_channel(channel_id)
        try:
            msg = await channel.fetch_message(message_id)
        except:
            return # Message deleted

        users = []
        async for user in msg.reactions[0].users():
            if not user.bot:
                users.append(user)

        if len(users) < winners_count:
            winners = users
        else:
            winners = random.sample(users, winners_count)

        if winners:
            winner_mentions = ", ".join([w.mention for w in winners])
            await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{prize}**!")
        else:
            await channel.send("No one entered the giveaway.")

        await self.bot.db.execute("UPDATE giveaways SET ended = 1 WHERE message_id = ?", (message_id,))
        await self.bot.db.commit()

    @commands.hybrid_command(description="Admin: End a giveaway early.")
    @commands.has_permissions(administrator=True)
    async def gend(self, ctx, message_id: int):
        await self.end_giveaway(message_id)

    @commands.hybrid_command(description="Admin: Reroll a giveaway winner.")
    @commands.has_permissions(administrator=True)
    async def greroll(self, ctx, message_id: int):
        # Simplified reroll logic (just picks one new winner)
        channel = ctx.channel
        try:
            msg = await channel.fetch_message(message_id)
        except:
            await ctx.send("Message not found.")
            return

        users = []
        async for user in msg.reactions[0].users():
            if not user.bot:
                users.append(user)

        if not users:
            await ctx.send("No valid entries.")
            return

        winner = random.choice(users)
        await ctx.send(f"🎉 New winner: {winner.mention}!")

    # --- Raffles ---
    @commands.hybrid_group(invoke_without_command=True, description="Manage raffles.")
    async def raffle(self, ctx):
        await ctx.send("Use `!raffle start`, `!raffle enter`, or `!raffle end`.")

    @raffle.command(description="Admin: Start a raffle.")
    @commands.has_permissions(administrator=True)
    async def start(self, ctx, prize: str, ticket_cost: int, duration: str):
        # Parse duration
        unit = duration[-1]
        try:
            val = int(duration[:-1])
        except ValueError:
            await ctx.send("Invalid duration. Use 10s, 1m, 1h.")
            return

        seconds = 0
        if unit == 's': seconds = val
        elif unit == 'm': seconds = val * 60
        elif unit == 'h': seconds = val * 3600
        else:
            await ctx.send("Invalid unit.")
            return

        embed = discord.Embed(title="🎟️ RAFFLE STARTED 🎟️", description=f"Prize: **{prize}**\nTicket Cost: **{ticket_cost}** 🎟️\nUse `!raffle enter <amount>` to join!", color=discord.Color.magenta())
        embed.set_footer(text=f"Ends in: {duration}")
        msg = await ctx.send(embed=embed)

        await self.bot.db.execute("INSERT INTO raffles (channel_id, message_id, prize, ticket_cost) VALUES (?, ?, ?, ?)", 
                                  (ctx.channel.id, msg.id, prize, ticket_cost))
        await self.bot.db.commit()

        # Auto-end task (simplified: just sleep)
        # In production, use a background task loop to check DB for ended raffles
        await asyncio.sleep(seconds)
        await self.end_raffle(msg.id)

    @raffle.command(description="Enter the current raffle.")
    async def enter(self, ctx, entries: int):
        if entries <= 0:
            await ctx.send("Entries must be positive.")
            return

        # Find active raffle in channel
        async with self.bot.db.execute("SELECT raffle_id, ticket_cost, ended FROM raffles WHERE channel_id = ? AND ended = 0 ORDER BY raffle_id DESC LIMIT 1", (ctx.channel.id,)) as cursor:
            raffle = await cursor.fetchone()
        
        if not raffle:
            await ctx.send("No active raffle in this channel.")
            return

        raffle_id, cost, ended = raffle
        total_cost = cost * entries

        # Check tickets
        async with self.bot.db.execute("SELECT tickets FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            user = await cursor.fetchone()
        
        if not user or user[0] < total_cost:
            await ctx.send(f"Not enough tickets! Cost: {total_cost}, You have: {user[0] if user else 0}")
            return

        # Deduct tickets
        await self.bot.db.execute("UPDATE users SET tickets = tickets - ? WHERE user_id = ?", (total_cost, ctx.author.id))

        # Add entries
        async with self.bot.db.execute("SELECT entries_count FROM raffle_entries WHERE raffle_id = ? AND user_id = ?", (raffle_id, ctx.author.id)) as cursor:
            entry = await cursor.fetchone()
        
        if entry:
            await self.bot.db.execute("UPDATE raffle_entries SET entries_count = entries_count + ? WHERE raffle_id = ? AND user_id = ?", (entries, raffle_id, ctx.author.id))
        else:
            await self.bot.db.execute("INSERT INTO raffle_entries (raffle_id, user_id, entries_count) VALUES (?, ?, ?)", (raffle_id, ctx.author.id, entries))
        
        await self.bot.db.commit()
        await ctx.send(f"Bought {entries} entries for 🎟️ {total_cost}!")

    async def end_raffle(self, message_id):
        async with self.bot.db.execute("SELECT raffle_id, channel_id, prize, ended FROM raffles WHERE message_id = ?", (message_id,)) as cursor:
            raffle = await cursor.fetchone()
        
        if not raffle or raffle[3]: return

        raffle_id, channel_id, prize, _ = raffle
        channel = self.bot.get_channel(channel_id)

        # Get entries (weighted)
        async with self.bot.db.execute("SELECT user_id, entries_count FROM raffle_entries WHERE raffle_id = ?", (raffle_id,)) as cursor:
            entries = await cursor.fetchall()
        
        pool = []
        for user_id, count in entries:
            pool.extend([user_id] * count)

        if pool:
            winner_id = random.choice(pool)
            winner = channel.guild.get_member(winner_id)
            mention = winner.mention if winner else f"User ID {winner_id}"
            await channel.send(f"🎟️ The raffle for **{prize}** has ended!\nWinner: {mention} 🎉")
        else:
            await channel.send(f"🎟️ The raffle for **{prize}** has ended. No entries.")

        await self.bot.db.execute("UPDATE raffles SET ended = 1 WHERE raffle_id = ?", (raffle_id,))
        await self.bot.db.commit()

    @raffle.command(name="end", description="Admin: End a raffle early.")
    @commands.has_permissions(administrator=True)
    async def end_cmd(self, ctx, message_id: int):
        await self.end_raffle(message_id)

async def setup(bot):
    await bot.add_cog(Community(bot))
