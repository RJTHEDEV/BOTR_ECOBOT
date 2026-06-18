import discord
from discord.ext import commands

class Sportsbook(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(invoke_without_command=True, description="Manage custom bets and predictions.")
    async def bet(self, ctx):
        await ctx.send("Use `/bet create`, `/bet join`, or `/bet resolve`.")

    @bet.command(name="create", description="Create a custom bet (Streamers/Admins).")
    @commands.has_permissions(manage_messages=True)
    async def create(self, ctx, *, question: str):
        embed = discord.Embed(title="🎲 New Prediction Started!", description=f"**{question}**\n\nUse `/bet join {ctx.message.id} yes <amount>` or `no` to play!", color=discord.Color.purple())
        msg = await ctx.send(embed=embed)
        
        # Save to DB
        await self.bot.db.execute("INSERT INTO active_bets (message_id, guild_id, question, status) VALUES (?, ?, ?, 'open')", 
                                  (msg.id, ctx.guild.id, question))
        await self.bot.db.commit()

    @bet.command(name="join", description="Join an active bet with your coins.")
    async def join(self, ctx, bet_id: int, choice: str, amount: int):
        choice = choice.lower()
        if choice not in ["yes", "no"]:
            await ctx.send("Choice must be `yes` or `no`.")
            return
            
        if amount <= 0:
            await ctx.send("Amount must be positive.")
            return

        async with self.bot.db.execute("SELECT status, pool_yes, pool_no FROM active_bets WHERE message_id = ?", (bet_id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            await ctx.send("Bet not found.")
            return
            
        if row[0] != "open":
            await ctx.send("This bet is closed for new entries.")
            return

        # Check balance
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            bal_row = await cursor.fetchone()
            
        if not bal_row or bal_row[0] < amount:
            await ctx.send("Insufficient funds.")
            return

        # Deduct
        await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, ctx.author.id))
        
        # Add to entry
        await self.bot.db.execute("INSERT INTO bet_entries (message_id, user_id, choice, amount) VALUES (?, ?, ?, ?) ON CONFLICT(message_id, user_id) DO UPDATE SET amount = amount + excluded.amount", 
                                  (bet_id, ctx.author.id, choice, amount))
                                  
        # Update pool
        if choice == "yes":
            await self.bot.db.execute("UPDATE active_bets SET pool_yes = pool_yes + ? WHERE message_id = ?", (amount, bet_id))
        else:
            await self.bot.db.execute("UPDATE active_bets SET pool_no = pool_no + ? WHERE message_id = ?", (amount, bet_id))
            
        await self.bot.db.commit()
        await ctx.send(f"✅ You bet **${amount}** on **{choice.upper()}**!")

    @bet.command(name="resolve", description="Resolve a bet and payout winners.")
    @commands.has_permissions(manage_messages=True)
    async def resolve(self, ctx, bet_id: int, winning_choice: str):
        winning_choice = winning_choice.lower()
        if winning_choice not in ["yes", "no", "cancel"]:
            await ctx.send("Winning choice must be `yes`, `no`, or `cancel`.")
            return

        async with self.bot.db.execute("SELECT question, pool_yes, pool_no FROM active_bets WHERE message_id = ? AND status = 'open'", (bet_id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            await ctx.send("Active bet not found.")
            return
            
        question, pool_yes, pool_no = row
        total_pool = pool_yes + pool_no

        if winning_choice == "cancel":
            # Refund
            async with self.bot.db.execute("SELECT user_id, amount FROM bet_entries WHERE message_id = ?", (bet_id,)) as cursor:
                entries = await cursor.fetchall()
            for u_id, amt in entries:
                await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, u_id))
            await ctx.send("Bet cancelled. All coins refunded.")
        else:
            # Payout
            winning_pool = pool_yes if winning_choice == "yes" else pool_no
            if winning_pool == 0:
                await ctx.send("No one bet on the winning side. Coins burned!")
            else:
                multiplier = total_pool / winning_pool
                async with self.bot.db.execute("SELECT user_id, amount FROM bet_entries WHERE message_id = ? AND choice = ?", (bet_id, winning_choice)) as cursor:
                    winners = await cursor.fetchall()
                for u_id, amt in winners:
                    winnings = int(amt * multiplier)
                    await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (winnings, u_id))
                await ctx.send(f"🎉 Bet Resolved! **{winning_choice.upper()}** won. Payout multiplier: **{multiplier:.2f}x**!")

        await self.bot.db.execute("UPDATE active_bets SET status = 'closed' WHERE message_id = ?", (bet_id,))
        await self.bot.db.commit()

async def setup(bot):
    await bot.add_cog(Sportsbook(bot))
