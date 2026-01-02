import discord
from discord.ext import commands
import random
import time
import datetime

LEVEL_UP_MESSAGES = [
    "🎉 **Level Up!** Way to go, {user}! You've reached Level {level}!",
    "🚀 **Boom!** {user} just hit Level {level}! Keep soaring!",
    "🌟 **Shining Bright!** {user}, you're now Level {level}!",
    "🔥 **On Fire!** {user} crushed it and reached Level {level}!",
    "💪 **Stronger!** {user} is now Level {level}! Unstoppable!",
    "🎈 **Celebrate!** {user} has ascended to Level {level}!",
    "✨ **Magic Moment!** {user} is officially Level {level}!",
    "👑 **Royalty!** {user} has climbed to Level {level}!",
    "⚡ **Electric!** {user} powered up to Level {level}!",
    "🎸 **Rockstar!** {user} smashed their way to Level {level}!",
    "💎 **Precious!** {user} is now a Level {level} gem!",
    "🌈 **Colorful!** {user} reached Level {level}! Amazing!",
    "🏆 **Champion!** {user} takes the trophy at Level {level}!",
    "🍕 **Party Time!** {user} is Level {level}! Pizza for everyone!",
    "🌊 **Wave Rider!** {user} surfed to Level {level}!",
    "🤖 **Beep Boop!** {user} upgraded to Level {level}!",
    "🍩 **Sweet!** {user} is Level {level}! Delicious victory!",
    "🤠 **Yeehaw!** {user} wrangled Level {level}!",
    "👻 **Spooky Good!** {user} is scarily good at Level {level}!",
    "🐉 **Legendary!** {user} has evolved to Level {level}!",
    "🛸 **Out of this World!** {user} is Level {level}!",
    "🍦 **Cool!** {user} chilled their way to Level {level}!",
    "🎯 **Bullseye!** {user} hit the mark at Level {level}!",
    "🎲 **Jackpot!** {user} rolled a Level {level}!",
    "⚓ **Ahoy!** {user} sailed to Level {level}!",
    "🏰 **King of the Castle!** {user} reached Level {level}!",
    "🌠 **Stralight!** {user} shines at Level {level}!",
    "🌋 **Eruption!** {user} exploded to Level {level}!",
    "🥝 **Juicy!** {user} is fresh at Level {level}!",
    "🍄 **Power Up!** {user} grew to Level {level}!",
    "🚲 **Zoom!** {user} raced to Level {level}!",
    "🥊 **Knockout!** {user} fought to Level {level}!",
    "🎓 **Smart!** {user} graduated to Level {level}!",
    "🦜 **Squawk!** {user} flew to Level {level}!",
    "🧩 **Solved!** {user} pieced together Level {level}!",
    "🌞 **Sunny!** {user} brightened up to Level {level}!",
    "🌙 **Moonlight!** {user} glows at Level {level}!",
    "🍭 **Sugar Rush!** {user} sprinted to Level {level}!",
    "🚗 **Vroom!** {user} drove to Level {level}!",
    "🪐 **Galactic!** {user} orbits Level {level}!",
    "🏔️ **Summit!** {user} climbed to Level {level}!",
    "🕹️ **Game Over? No!** {user} leveled up to {level}!",
    "🎨 **Masterpiece!** {user} painted Level {level}!",
    "🎭 **Encore!** {user} performed perfectly to Level {level}!",
    "🎪 **Showtime!** {user} is the star at Level {level}!",
    "🎡 **High Flyer!** {user} reached new heights at Level {level}!",
    "🎰 **Winner!** {user} hit the Level {level} jackpot!",
    "🧬 **Evolved!** {user} DNA upgraded to Level {level}!",
    "🧪 **Experiment Success!** {user} results: Level {level}!",
    "🔮 **Destiny!** {user} was meant to be Level {level}!"
]

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
        xp_needed = 250 * current_level
        
        if new_xp >= xp_needed:
            new_level = current_level + 1
            await self.bot.db.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, user.id))
            await self.bot.db.commit()
            
            # Announce Level Up
            try:
                msg = random.choice(LEVEL_UP_MESSAGES).format(user=user.mention, level=new_level)
                await user.send(msg)
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

    @commands.hybrid_command(description="View user profile.")
    async def profile(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        await ctx.defer()
        
        async with self.bot.db.execute("SELECT balance, bank, xp, level, reputation FROM users WHERE user_id = ?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await ctx.send("User has no profile.")
                return
            bal, bank, xp, level, rep = row
        
        embed = discord.Embed(title=f"{user.display_name}'s Profile", color=discord.Color.purple())
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="💰 Wallet", value=f"${bal}", inline=True)
        embed.add_field(name="🏦 Bank", value=f"${bank}", inline=True)
        embed.add_field(name="📈 Net Worth", value=f"${bal + bank}", inline=True)
        embed.add_field(name="⭐ Reputation", value=f"{rep}", inline=True)
        embed.add_field(name="📊 Level", value=f"{level} (XP: {xp})", inline=True)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="View the XP Leaderboard.")
    async def leaderboard(self, ctx, page: int = 1):
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

        async with self.bot.db.execute("SELECT user_id, xp, level FROM users ORDER BY xp DESC LIMIT ? OFFSET ?", (per_page, offset)) as cursor:
            rows = await cursor.fetchall()
        
        embed = discord.Embed(title="🏆 XP Leaderboard", color=discord.Color.gold())
        for i, (user_id, xp, level) in enumerate(rows, 1):
            rank = offset + i
            user = ctx.guild.get_member(user_id)
            name = user.display_name if user else f"User {user_id}"
            embed.add_field(name=f"#{rank} {name}", value=f"Level {level} | {xp} XP", inline=False)
        
        embed.set_footer(text=f"Page {page}/{total_pages} | Use !leaderboard <page>")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Compare your stats with another user.")
    async def compare(self, ctx, target: discord.Member):
        if target.bot:
            await ctx.send("Cannot compare with bots.")
            return

        # Fetch Data
        async def get_stats(user_id):
            async with self.bot.db.execute("SELECT balance, bank, xp, level, reputation FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row: return (0, 0, 0, 1, 0)
                return row

        u1_stats = await get_stats(ctx.author.id)
        u2_stats = await get_stats(target.id)

        u1_bal, u1_bank, u1_xp, u1_level, u1_rep = u1_stats
        u2_bal, u2_bank, u2_xp, u2_level, u2_rep = u2_stats

        u1_net = u1_bal + u1_bank
        u2_net = u2_bal + u2_bank

        def cmp(v1, v2):
            if v1 > v2: return "👑", ""
            elif v2 > v1: return "", "👑"
            return "", ""

        c_bal = cmp(u1_bal, u2_bal)
        c_bank = cmp(u1_bank, u2_bank)
        c_net = cmp(u1_net, u2_net)
        c_xp = cmp(u1_xp, u2_xp)
        c_level = cmp(u1_level, u2_level)
        c_rep = cmp(u1_rep, u2_rep)

        embed = discord.Embed(title=f"⚔️ Comparison: {ctx.author.display_name} vs {target.display_name}", color=discord.Color.magenta())
        
        # Table-like format
        embed.add_field(name="Category", value="**Level**\n**XP**\n**Balance**\n**Bank**\n**Net Worth**\n**Reputation**", inline=True)
        embed.add_field(name=ctx.author.display_name, value=f"{c_level[0]} {u1_level}\n{c_xp[0]} {u1_xp}\n{c_bal[0]} ${u1_bal}\n{c_bank[0]} ${u1_bank}\n{c_net[0]} ${u1_net}\n{c_rep[0]} {u1_rep}", inline=True)
        embed.add_field(name=target.display_name, value=f"{c_level[1]} {u2_level}\n{c_xp[1]} {u2_xp}\n{c_bal[1]} ${u2_bal}\n{c_bank[1]} ${u2_bank}\n{c_net[1]} ${u2_net}\n{c_rep[1]} {u2_rep}", inline=True)

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        
        # XP Cooldown (60s)
        now = time.time()
        last_time = self.last_xp_time.get(message.author.id, 0)
        
        if now - last_time >= 60:
            xp_amount = random.randint(10, 20)
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

    # --- Crafting ---
    RECIPES = {
        "Mining Rig": {"GPU": 1, "Motherboard": 1, "Power Supply": 1},
        "Safe": {"Steel": 5, "Lock": 1}
    }

    @commands.hybrid_command(description="Craft an item.")
    async def craft(self, ctx, item_name: str):
        item_name = item_name.title()
        if item_name not in self.RECIPES:
            await ctx.send(f"Unknown recipe. Available: {', '.join(self.RECIPES.keys())}")
            return
        
        recipe = self.RECIPES[item_name]
        
        # Check materials
        for mat, qty in recipe.items():
            async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (ctx.author.id, mat)) as cursor:
                row = await cursor.fetchone()
                if not row or row[0] < qty:
                    await ctx.send(f"❌ Missing materials: You need **{qty}x {mat}**.")
                    return
        
        # Consume materials
        for mat, qty in recipe.items():
            await self.bot.db.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?", (qty, ctx.author.id, mat))
            
        # Add crafted item
        async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (ctx.author.id, item_name)) as cursor:
            row = await cursor.fetchone()
            if row:
                await self.bot.db.execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_name = ?", (ctx.author.id, item_name))
            else:
                await self.bot.db.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, 1)", (ctx.author.id, item_name))
        
        await self.bot.db.commit()
        await ctx.send(f"🛠️ Successfully crafted **{item_name}**!")

    @commands.hybrid_command(description="View crafting recipes.")
    async def recipes(self, ctx):
        embed = discord.Embed(title="📜 Crafting Recipes", color=discord.Color.orange())
        for item, mats in self.RECIPES.items():
            mat_str = ", ".join([f"{qty}x {mat}" for mat, qty in mats.items()])
            embed.add_field(name=item, value=mat_str, inline=False)
        await ctx.send(embed=embed)

    # --- Trading ---
    @commands.hybrid_command(description="Trade an item with another user.")
    async def trade(self, ctx, target: discord.Member, item_name: str, quantity: int, price: int):
        if target.bot or target == ctx.author:
            await ctx.send("Invalid trade target.")
            return
        
        if quantity <= 0 or price < 0:
            await ctx.send("Invalid quantity or price.")
            return

        # Check if user has item
        async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (ctx.author.id, item_name)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < quantity:
                await ctx.send(f"You don't have enough **{item_name}**.")
                return

        # Check if target has enough coins
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < price:
                await ctx.send(f"{target.display_name} doesn't have enough coins.")
                return

        # Create View
        view = TradeView(ctx.author, target, item_name, quantity, price, self.bot)
        embed = discord.Embed(title="🤝 Trade Offer", description=f"{ctx.author.mention} wants to trade:\n\n📦 **{quantity}x {item_name}**\n💰 For: **${price}**\n\n{target.mention}, do you accept?", color=discord.Color.blue())
        await ctx.send(content=target.mention, embed=embed, view=view)

class TradeView(discord.ui.View):
    def __init__(self, seller, buyer, item, quantity, price, bot):
        super().__init__(timeout=60)
        self.seller = seller
        self.buyer = buyer
        self.item = item
        self.quantity = quantity
        self.price = price
        self.bot = bot

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.buyer:
            await interaction.response.send_message("This trade is not for you.", ephemeral=True)
            return
        
        # Re-verify funds and items (in case they changed during the wait)
        async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (self.seller.id, self.item)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < self.quantity:
                await interaction.response.edit_message(content="❌ Trade failed: Seller no longer has the items.", view=None, embed=None)
                return

        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (self.buyer.id,)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < self.price:
                await interaction.response.edit_message(content="❌ Trade failed: Buyer no longer has enough coins.", view=None, embed=None)
                return

        # Execute Trade
        # 1. Remove item from seller
        await self.bot.db.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?", (self.quantity, self.seller.id, self.item))
        # Remove row if 0? Maybe keep for history, but typically remove to save space. Let's keep for now.
        
        # 2. Add item to buyer
        async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (self.buyer.id, self.item)) as cursor:
            row = await cursor.fetchone()
            if row:
                await self.bot.db.execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_name = ?", (self.quantity, self.buyer.id, self.item))
            else:
                await self.bot.db.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?)", (self.buyer.id, self.item, self.quantity))

        # 3. Transfer Coins
        await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (self.price, self.seller.id))
        await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (self.price, self.buyer.id))
        
        await self.bot.db.commit()
        
        await interaction.response.edit_message(content=f"✅ **Trade Successful!**\n{self.seller.mention} gave **{self.quantity}x {self.item}**\n{self.buyer.mention} paid **${self.price}**", view=None, embed=None)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.buyer and interaction.user != self.seller:
            await interaction.response.send_message("You cannot decline this trade.", ephemeral=True)
            return
        
        await interaction.response.edit_message(content="❌ Trade declined.", view=None, embed=None)

async def setup(bot):
    await bot.add_cog(Economy(bot))
