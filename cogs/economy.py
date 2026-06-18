import discord
from discord.ext import commands, tasks
import random
import time
import datetime

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_tracking = {}
        self.last_xp_time = {} # {user_id: timestamp}
        self.bank_interest_task.start()

    def cog_unload(self):
        self.bank_interest_task.cancel()

    @tasks.loop(hours=24)
    async def bank_interest_task(self):
        # 1% daily interest for bank balances over 0
        await self.bot.db.execute("UPDATE users SET bank = CAST(bank * 1.01 AS INTEGER) WHERE bank > 0")
        await self.bot.db.commit()

    @bank_interest_task.before_loop
    async def before_bank_interest_task(self):
        await self.bot.wait_until_ready()
    async def log_transaction(self, user_id, type, amount, description):
        timestamp = datetime.datetime.now().isoformat()
        await self.bot.db.execute("INSERT INTO transaction_logs (user_id, type, amount, description, timestamp) VALUES (?, ?, ?, ?, ?)", 
                                  (user_id, type, amount, description, timestamp))
        await self.bot.db.commit()

    @commands.hybrid_command(name="currencylog", aliases=["cl"], description="View your currency transaction history.")
    async def currencylog(self, ctx, page: int = 1):
        if page < 1: page = 1
        per_page = 10
        offset = (page - 1) * per_page

        async with self.bot.db.execute("SELECT COUNT(*) FROM transaction_logs WHERE user_id = ?", (ctx.author.id,)) as cursor:
            total_logs = (await cursor.fetchone())[0]
        
        if total_logs == 0:
            await ctx.send("No transaction history found.")
            return

        total_pages = (total_logs + per_page - 1) // per_page
        if page > total_pages:
            await ctx.send(f"Page {page} does not exist. Total pages: {total_pages}")
            return

        async with self.bot.db.execute("SELECT type, amount, description, timestamp FROM transaction_logs WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (ctx.author.id, per_page, offset)) as cursor:
            logs = await cursor.fetchall()
        
        embed = discord.Embed(title=f"📜 Currency Log: {ctx.author.display_name}", color=discord.Color.blue())
        
        desc = ""
        for type, amount, description, timestamp in logs:
            amount_str = f"+${amount}" if amount >= 0 else f"-${abs(amount)}"
            emoji = "🟢" if amount >= 0 else "🔴"
            dt = datetime.datetime.fromisoformat(timestamp)
            date_str = f"<t:{int(dt.timestamp())}:f>"
            
            desc += f"{emoji} **{type.title()}** ({amount_str})\n{description} • {date_str}\n\n"
        
        embed.description = desc
        embed.set_footer(text=f"Page {page}/{total_pages} | Total: {total_logs}")
        await ctx.send(embed=embed)

    async def log_transaction(self, user_id, type, amount, description):
        timestamp = datetime.datetime.now().isoformat()
        await self.bot.db.execute("INSERT INTO transaction_logs (user_id, type, amount, description, timestamp) VALUES (?, ?, ?, ?, ?)", 
                                  (user_id, type, amount, description, timestamp))
        await self.bot.db.commit()

    @commands.hybrid_command(name="currencylog", aliases=["cl"], description="View your currency transaction history.")
    async def currencylog(self, ctx, page: int = 1):
        if page < 1: page = 1
        per_page = 10
        offset = (page - 1) * per_page

        async with self.bot.db.execute("SELECT COUNT(*) FROM transaction_logs WHERE user_id = ?", (ctx.author.id,)) as cursor:
            total_logs = (await cursor.fetchone())[0]
        
        if total_logs == 0:
            await ctx.send("No transaction history found.")
            return

        total_pages = (total_logs + per_page - 1) // per_page
        if page > total_pages:
            await ctx.send(f"Page {page} does not exist. Total pages: {total_pages}")
            return

        async with self.bot.db.execute("SELECT type, amount, description, timestamp FROM transaction_logs WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (ctx.author.id, per_page, offset)) as cursor:
            logs = await cursor.fetchall()
        
        embed = discord.Embed(title=f"📜 Currency Log: {ctx.author.display_name}", color=discord.Color.blue())
        
        desc = ""
        for type, amount, description, timestamp in logs:
            amount_str = f"+${amount}" if amount >= 0 else f"-${abs(amount)}"
            emoji = "🟢" if amount >= 0 else "🔴"
            dt = datetime.datetime.fromisoformat(timestamp)
            date_str = f"<t:{int(dt.timestamp())}:f>"
            
            desc += f"{emoji} **{type.title()}** ({amount_str})\n{description} • {date_str}\n\n"
        
        embed.description = desc
        embed.set_footer(text=f"Page {page}/{total_pages} | Total: {total_logs}")
        await ctx.send(embed=embed)
    @commands.hybrid_command(description="Check your coin and ticket balance.")
    async def balance(self, ctx):
        print(f"Balance command invoked by {ctx.author} ({ctx.author.id})")
        await ctx.defer()
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
        today = datetime.date.today().isoformat()
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        
        async with self.bot.db.execute("SELECT balance, level, last_daily, daily_streak FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                # New user
                level, last_daily, streak = 1, None, 1
                base_amount = 500
                bonus = 50 # Level 1
                streak_bonus = 0
                total_amount = base_amount + bonus
                await self.bot.db.execute("INSERT INTO users (user_id, balance, level, last_daily, daily_streak) VALUES (?, ?, ?, ?, ?)", 
                                          (ctx.author.id, total_amount, level, today, 1))
            else:
                balance, level, last_daily, streak = row
                
                # Check streak
                if last_daily == yesterday:
                    streak += 1
                elif last_daily == today:
                    await ctx.send("You already claimed your daily reward today!")
                    return
                else:
                    streak = 1
                
                # Cap streak at 7 for visual purposes, but maybe keep counting for fun? 
                # Let's cap bonus at 7 days
                effective_streak = min(streak, 7)
                
                # Check for Mining Rig (Passive Income)
                rig_bonus = 0
                async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = 'Mining Rig'", (ctx.author.id,)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0] > 0:
                        rig_bonus = 200 * row[0] # $200 per rig

                base_amount = 500
                level_bonus = level * 50
                streak_bonus = effective_streak * 50
                total_amount = base_amount + level_bonus + streak_bonus + rig_bonus
                
                await self.bot.db.execute("UPDATE users SET balance = balance + ?, last_daily = ?, daily_streak = ? WHERE user_id = ?", 
                                          (total_amount, today, streak, ctx.author.id))
                await self.log_transaction(ctx.author.id, "daily", total_amount, f"Daily reward (Streak: {streak})")
        
        await self.bot.db.commit()
        
        embed = discord.Embed(title="💰 Daily Reward", color=discord.Color.gold())
        embed.add_field(name="Base", value="$500", inline=True)
        embed.add_field(name="Level Bonus", value=f"${level_bonus}", inline=True)
        embed.add_field(name="Streak Bonus", value=f"${streak_bonus} (Day {streak} 🔥)", inline=True)
        if rig_bonus > 0:
            embed.add_field(name="Mining Rig", value=f"${rig_bonus} 🖥️", inline=True)
        embed.add_field(name="Total", value=f"**${total_amount}**", inline=False)
        
        await ctx.send(embed=embed)

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
        await self.log_transaction(member.id, "admin_give", amount, "Admin gave coins")
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

    @commands.hybrid_command(description="Pay coins to another user.")
    async def pay(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            await ctx.send("Amount must be greater than zero.")
            return
        if member == ctx.author or member.bot:
            await ctx.send("You cannot pay this user.")
            return

        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < amount:
                await ctx.send("Insufficient funds.")
                return

        # Deduct from author
        await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, ctx.author.id))
        # Add to member
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await self.bot.db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (member.id, amount))
            else:
                await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, member.id))
        
        await self.bot.db.commit()
        await self.log_transaction(ctx.author.id, "pay", -amount, f"Paid to {member.display_name}")
        await self.log_transaction(member.id, "pay", amount, f"Received from {ctx.author.display_name}")
        await ctx.send(f"💸 You paid **${amount}** to {member.mention}.")

    # --- Banking ---
    @commands.hybrid_command(description="Deposit coins into your bank.")
    async def deposit(self, ctx, amount: str):
        await ctx.defer()
        async with self.bot.db.execute("SELECT balance, bank FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await ctx.send("You have no account.")
                return
            balance, bank = row
        
        if amount.lower() == "all":
            deposit_amount = balance
        else:
            try:
                deposit_amount = int(amount)
            except ValueError:
                await ctx.send("Invalid amount.")
                return

        if deposit_amount <= 0:
            await ctx.send("Amount must be positive.")
            return
        
        if deposit_amount > balance:
            await ctx.send("Insufficient funds.")
            return

        await self.bot.db.execute("UPDATE users SET balance = balance - ?, bank = bank + ? WHERE user_id = ?", (deposit_amount, deposit_amount, ctx.author.id))
        await self.bot.db.commit()
        await ctx.send(f"🏦 Deposited **${deposit_amount}** into your bank.")

    @commands.hybrid_command(description="Withdraw coins from your bank.")
    async def withdraw(self, ctx, amount: str):
        await ctx.defer()
        async with self.bot.db.execute("SELECT balance, bank FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await ctx.send("You have no account.")
                return
            balance, bank = row
        
        if amount.lower() == "all":
            withdraw_amount = bank
        else:
            try:
                withdraw_amount = int(amount)
            except ValueError:
                await ctx.send("Invalid amount.")
                return

        if withdraw_amount <= 0:
            await ctx.send("Amount must be positive.")
            return
        
        if withdraw_amount > bank:
            await ctx.send("Insufficient funds in bank.")
            return

        await self.bot.db.execute("UPDATE users SET balance = balance + ?, bank = bank - ? WHERE user_id = ?", (withdraw_amount, withdraw_amount, ctx.author.id))
        await self.bot.db.commit()
        await ctx.send(f"💸 Withdrew **${withdraw_amount}** from your bank.")

    # --- Income & Crime ---
    @commands.hybrid_command(description="Work to earn some coins (1h cooldown).")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def work(self, ctx):
        earnings = random.randint(50, 200)
        await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (earnings, ctx.author.id))
        await self.bot.db.commit()
        await self.log_transaction(ctx.author.id, "work", earnings, "Worked a shift")
        await ctx.send(f"🔨 You worked hard and earned **${earnings}**!")

    @commands.hybrid_command(description="Beg for some coins (5m cooldown).")
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def beg(self, ctx):
        if random.random() < 0.7: # 70% success
            earnings = random.randint(10, 50)
            await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (earnings, ctx.author.id))
            await self.bot.db.commit()
            await self.log_transaction(ctx.author.id, "beg", earnings, "Begged successfully")
            await ctx.send(f"🥺 Someone felt bad and gave you **${earnings}**!")
        else:
            await ctx.send("🛑 Everyone ignored you. Try again later.")

    @commands.hybrid_command(description="Search for coins (15m cooldown).")
    @commands.cooldown(1, 900, commands.BucketType.user)
    async def search(self, ctx):
        locations = ["in the couch", "on the street", "in a trash can", "under a rock", "in someone's pocket"]
        if random.random() < 0.8: # 80% success
            earnings = random.randint(20, 100)
            loc = random.choice(locations)
            await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (earnings, ctx.author.id))
            await self.bot.db.commit()
            await self.log_transaction(ctx.author.id, "search", earnings, f"Found coins {loc}")
            await ctx.send(f"🔍 You looked {loc} and found **${earnings}**!")
        else:
            await ctx.send("🔍 You searched but found nothing but dust.")

    @commands.hybrid_command(description="Commit a crime (High risk/reward) (2h cooldown).")
    @commands.cooldown(1, 7200, commands.BucketType.user)
    async def crime(self, ctx):
        if random.random() < 0.6: # 60% success
            earnings = random.randint(300, 800)
            await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (earnings, ctx.author.id))
            await self.bot.db.commit()
            await self.log_transaction(ctx.author.id, "crime", earnings, "Crime success")
            await ctx.send(f"🕵️ You successfully committed a crime and stole **${earnings}**!")
        else:
            fine = random.randint(100, 300)
            await self.bot.db.execute("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?", (fine, ctx.author.id))
            await self.bot.db.commit()
            await self.log_transaction(ctx.author.id, "crime", -fine, "Crime caught (fine)")
            await ctx.send(f"🚓 You got caught! You paid a fine of **${fine}**.")

    @commands.hybrid_command(description="Rob another user (Chance to fail).")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def rob(self, ctx, target: discord.Member):
        if target.bot or target == ctx.author:
            await ctx.send("You can't rob them.")
            return

        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()
            target_bal = row[0] if row else 0

        if target_bal < 100:
            await ctx.send("They don't have enough coins to rob.")
            return

        # Check for Safe
        async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = 'Safe'", (target.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] > 0:
                # Safe protects 50% of balance or increases fail chance?
                # Let's make it increase fail chance drastically (80% fail)
                if random.random() < 0.8:
                    fine = random.randint(200, 1000)
                    await self.bot.db.execute("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?", (fine, ctx.author.id))
                    await self.bot.db.commit()
                    await self.log_transaction(ctx.author.id, "rob", -fine, "Robbery failed (Safe Alarm)")
                    await ctx.send(f"🔒 **Safe Protected!** You triggered the alarm and paid a **${fine}** fine.")
                    return

        if random.random() < 0.4: # 40% success
            steal_amount = random.randint(int(target_bal * 0.1), int(target_bal * 0.5))
            await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (steal_amount, target.id))
            await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (steal_amount, ctx.author.id))
            await self.bot.db.commit()
            await self.log_transaction(target.id, "rob", -steal_amount, f"Robbed by {ctx.author.display_name}")
            await self.log_transaction(ctx.author.id, "rob", steal_amount, f"Robbed {target.display_name}")
            await ctx.send(f"😈 You robbed {target.mention} and stole **${steal_amount}**!")
        else:
            fine = random.randint(100, 500)
            await self.bot.db.execute("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?", (fine, ctx.author.id))
            await self.bot.db.commit()
            await self.log_transaction(ctx.author.id, "rob", -fine, f"Robbery failed - Target: {target.display_name}")
            await ctx.send(f"🛡️ You failed to rob {target.mention} and paid a fine of **${fine}**.")

    # --- Social ---
    @commands.hybrid_command(description="Give a reputation point to a user (24h cooldown).")
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def rep(self, ctx, target: discord.Member):
        if target == ctx.author:
            await ctx.send("You can't rep yourself.")
            return
        
        await self.bot.db.execute("UPDATE users SET reputation = reputation + 1 WHERE user_id = ?", (target.id,))
        await self.bot.db.commit()
        await ctx.send(f"🌟 You gave +1 reputation to {target.mention}!")
    @commands.hybrid_command(description="View the Richest Leaderboard.")
    async def richest(self, ctx, page: int = 1):
        if page < 1: page = 1
        per_page = 10
        offset = (page - 1) * per_page
        
        async with self.bot.db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
            
        total_pages = (total_users + per_page - 1) // per_page
        if not total_pages: total_pages = 1
        
        if page > total_pages:
            await ctx.send(f"Page {page} does not exist. Total pages: {total_pages}")
            return

        async with self.bot.db.execute("SELECT user_id, balance, bank FROM users ORDER BY (balance + bank) DESC LIMIT ? OFFSET ?", (per_page, offset)) as cursor:
            rows = await cursor.fetchall()
        
        embed = discord.Embed(title="💰 Richest Leaderboard", color=discord.Color.green())
        for i, (user_id, bal, bank) in enumerate(rows, 1):
            rank = offset + i
            user = ctx.guild.get_member(user_id)
            name = user.display_name if user else f"User {user_id}"
            net_worth = bal + bank
            embed.add_field(name=f"#{rank} {name}", value=f"**Net Worth:** ${net_worth}\n(Wallet: ${bal} | Bank: ${bank})", inline=False)
        
        embed.set_footer(text=f"Page {page}/{total_pages} | Use !richest <page>")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
