import discord
from discord.ext import commands, tasks
import random
import time
import datetime
import math

class LeaderboardSelect(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label="Richest (Net Worth)", emoji="💰", value="richest", description="Highest combined wallet and bank balance"),
            discord.SelectOption(label="Ticket Hoarders", emoji="🎟️", value="tickets", description="Most tickets collected"),
            discord.SelectOption(label="Highest Level", emoji="📈", value="level", description="Highest XP and Level"),
            discord.SelectOption(label="Hardest Workers", emoji="🏢", value="work_shifts", description="Most /work shifts completed"),
            discord.SelectOption(label="Most Wanted", emoji="🚔", value="wanted_level", description="Highest Wanted Level from crimes"),
            discord.SelectOption(label="Most Reputable", emoji="🌟", value="reputation", description="Highest community reputation")
        ]
        super().__init__(placeholder="Select a Leaderboard...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.category = self.values[0]
        self.parent_view.page = 1
        await self.parent_view.update_leaderboard(interaction)

class LeaderboardView(discord.ui.View):
    def __init__(self, cog, guild, user):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild = guild
        self.user = user
        self.page = 1
        self.category = "richest"
        
        self.add_item(LeaderboardSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    async def get_data(self):
        per_page = 10
        offset = (self.page - 1) * per_page
        
        query_map = {
            "richest": ("SELECT user_id, balance + bank AS val FROM users ORDER BY val DESC LIMIT ? OFFSET ?", "Net Worth", "${val}"),
            "tickets": ("SELECT user_id, tickets AS val FROM users ORDER BY val DESC LIMIT ? OFFSET ?", "Tickets", "🎟️ {val}"),
            "level": ("SELECT user_id, xp AS val, level FROM users ORDER BY val DESC LIMIT ? OFFSET ?", "Experience", "Level {level} (XP: {val})"),
            "work_shifts": ("SELECT user_id, work_shifts AS val FROM users ORDER BY val DESC LIMIT ? OFFSET ?", "Shifts Completed", "{val} shifts"),
            "wanted_level": ("SELECT user_id, wanted_level AS val FROM users ORDER BY val DESC LIMIT ? OFFSET ?", "Wanted Level", "⭐ {val}"),
            "reputation": ("SELECT user_id, reputation AS val FROM users ORDER BY val DESC LIMIT ? OFFSET ?", "Reputation", "🌟 {val}")
        }
        
        query, stat_name, format_str = query_map[self.category]
        
        async with self.cog.bot.db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
        
        total_pages = max(1, math.ceil(total_users / per_page))
        self.btn_prev.disabled = (self.page <= 1)
        self.btn_next.disabled = (self.page >= total_pages)
        
        async with self.cog.bot.db.execute(query, (per_page, offset)) as cursor:
            rows = await cursor.fetchall()
            
        return rows, total_pages, stat_name, format_str, offset

    async def update_leaderboard(self, interaction: discord.Interaction):
        rows, total_pages, stat_name, format_str, offset = await self.get_data()
        
        titles = {
            "richest": "💰 Richest Citizens",
            "tickets": "🎟️ Ticket Hoarders",
            "level": "📈 Highest Levels",
            "work_shifts": "🏢 Hardest Workers",
            "wanted_level": "🚔 Most Wanted Criminals",
            "reputation": "🌟 Most Reputable"
        }
        
        embed = discord.Embed(title=titles[self.category], color=discord.Color.gold())
        
        if not rows:
            embed.description = "No data available."
        else:
            for i, row in enumerate(rows, 1):
                rank = offset + i
                user_id = row[0]
                val = row[1]
                
                member = self.guild.get_member(user_id)
                name = member.display_name if member else f"Unknown User ({user_id})"
                
                # Emojis for top 3
                prefix = ""
                if rank == 1: prefix = "🥇 "
                elif rank == 2: prefix = "🥈 "
                elif rank == 3: prefix = "🥉 "
                else: prefix = f"#{rank} "
                
                if self.category == "level":
                    val_str = format_str.format(val=val, level=row[2])
                else:
                    val_str = format_str.format(val=val)
                    
                embed.add_field(name=f"{prefix}{name}", value=f"**{stat_name}:** {val_str}", inline=False)
                
        embed.set_footer(text=f"Page {self.page}/{total_pages} | Requested by {self.user.display_name}")
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=1)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        await self.update_leaderboard(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self.update_leaderboard(interaction)

class WorkView(discord.ui.View):
    def __init__(self, cog, user, shifts):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.shifts = shifts

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    def get_multiplier(self):
        if self.shifts < 10: return 1.0 # Intern
        if self.shifts < 50: return 2.0 # Junior
        if self.shifts < 100: return 5.0 # Senior
        return 10.0 # Hedge Fund Manager

    async def process_work(self, interaction, job_name, guaranteed, min_pay, max_pay, fail_chance=0.0):
        for item in self.children:
            item.disabled = True
            
        mult = self.get_multiplier()
        
        if random.random() < fail_chance:
            embed = discord.Embed(title="💼 Work Shift Failed", description=f"You tried to {job_name} but completely messed it up. You got fired for the day and earned nothing.", color=discord.Color.red())
            await interaction.response.edit_message(embed=embed, view=self)
            return

        earnings = int(random.randint(min_pay, max_pay) * mult)
        
        await self.cog.bot.db.execute("UPDATE users SET balance = balance + ?, work_shifts = work_shifts + 1 WHERE user_id = ?", (earnings, self.user.id))
        await self.cog.bot.db.commit()
        await self.cog.log_transaction(self.user.id, "work", earnings, f"Worked: {job_name}")
        
        embed = discord.Embed(title="💼 Work Shift Complete", description=f"You decided to {job_name} and successfully earned **${earnings}**!", color=discord.Color.green())
        
        # Check for promotion
        new_shifts = self.shifts + 1
        if new_shifts == 10:
            embed.add_field(name="🎉 PROMOTION!", value="You have been promoted to **Junior Trader**! Your payouts are doubled!", inline=False)
        elif new_shifts == 50:
            embed.add_field(name="🎉 PROMOTION!", value="You have been promoted to **Senior Trader**! Your payouts are now 5x!", inline=False)
        elif new_shifts == 100:
            embed.add_field(name="🎉 PROMOTION!", value="You have been promoted to **Hedge Fund Manager**! Your payouts are now 10x!", inline=False)
            
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Mow Lawns (Safe)", style=discord.ButtonStyle.green, emoji="🌱")
    async def btn_safe(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_work(interaction, "Mow Lawns", True, 50, 100)

    @discord.ui.button(label="Flip Burgers (Medium)", style=discord.ButtonStyle.blurple, emoji="🍔")
    async def btn_medium(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_work(interaction, "Flip Burgers", False, 100, 250, fail_chance=0.2)

    @discord.ui.button(label="Day Trade (Risky)", style=discord.ButtonStyle.red, emoji="📈")
    async def btn_risky(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_work(interaction, "Day Trade", False, 200, 500, fail_chance=0.5)

class CrimeView(discord.ui.View):
    def __init__(self, cog, user, wanted_level, laptop_count):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.wanted_level = wanted_level
        self.laptop_count = laptop_count

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    async def process_crime(self, interaction, target_name, success_rate, min_pay, max_pay, min_fine, max_fine):
        for item in self.children:
            item.disabled = True
            
        # Apply hacker laptop buff
        actual_success_rate = success_rate + (0.05 * self.laptop_count)
        
        # Wanted level penalty multiplier
        fine_mult = 1.0 + (0.5 * self.wanted_level) # +50% fine per wanted level

        if random.random() < actual_success_rate:
            earnings = random.randint(min_pay, max_pay) + (100 * self.laptop_count)
            await self.cog.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (earnings, self.user.id))
            await self.cog.bot.db.commit()
            await self.cog.log_transaction(self.user.id, "crime", earnings, f"Crime success: {target_name}")
            
            embed = discord.Embed(title="🕵️ Crime Success!", description=f"You successfully pulled off a {target_name} and escaped with **${earnings}**!", color=discord.Color.green())
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            fine = int(random.randint(min_fine, max_fine) * fine_mult)
            new_wanted = min(5, self.wanted_level + 1)
            
            await self.cog.bot.db.execute("UPDATE users SET balance = MAX(0, balance - ?), wanted_level = ? WHERE user_id = ?", (fine, new_wanted, self.user.id))
            await self.cog.bot.db.commit()
            await self.cog.log_transaction(self.user.id, "crime", -fine, f"Crime caught (fine)")
            
            embed = discord.Embed(title="🚓 BUSTED!", description=f"You got caught attempting a {target_name}!\nYou paid a fine of **${fine}**.", color=discord.Color.red())
            embed.add_field(name="Wanted Level Increased", value=f"{'⭐' * new_wanted}\nBuy a Fake ID or Lawyer in the store to clear your name!", inline=False)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Rob Gas Station (Easy)", style=discord.ButtonStyle.green, emoji="🏪")
    async def btn_easy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_crime(interaction, "Gas Station Robbery", 0.8, 100, 300, 50, 150)

    @discord.ui.button(label="Hack WallStreet (Medium)", style=discord.ButtonStyle.blurple, emoji="💻")
    async def btn_medium(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_crime(interaction, "WallStreet Hack", 0.5, 400, 1000, 200, 500)

    @discord.ui.button(label="Bank Heist (Hard)", style=discord.ButtonStyle.red, emoji="🏦")
    async def btn_hard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_work(interaction, "Fast Food Cashier", "🍔", 0.95, 30, 80)


class BegView(discord.ui.View):
    def __init__(self, cog, user):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("You can't beg on someone else's corner!", ephemeral=True)
            return False
        return True

    async def process_beg(self, interaction, target_name, success_chance, min_reward, max_reward, success_msgs, fail_msgs):
        for item in self.children:
            item.disabled = True
            
        embed = discord.Embed(title="🤲 Begging on the Streets", color=discord.Color.gold())
        
        if random.random() < success_chance:
            earnings = random.randint(min_reward, max_reward)
            await self.cog.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (earnings, self.user.id))
            await self.cog.bot.db.commit()
            await self.cog.log_transaction(self.user.id, "beg", earnings, f"Begged {target_name} successfully")
            
            msg = random.choice(success_msgs).format(amount=earnings)
            embed.description = f"**{target_name}** {msg}"
            embed.color = discord.Color.green()
        else:
            msg = random.choice(fail_msgs)
            embed.description = f"**{target_name}** {msg}"
            embed.color = discord.Color.red()
            
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Sweet Old Lady", style=discord.ButtonStyle.success, emoji="👵")
    async def btn_lady(self, interaction: discord.Interaction, button: discord.ui.Button):
        success_msgs = [
            "smiles warmly and hands you **${amount}**. 'Buy yourself something nice, dear.'",
            "pats your head and gives you **${amount}**. 'Stay out of trouble!'",
            "rummages through her purse and finds **${amount}** for you."
        ]
        fail_msgs = [
            "couldn't hear you and kept walking.",
            "thought you were selling girl scout cookies and walked away.",
            "hit you with her purse and yelled 'Stranger danger!'"
        ]
        await self.process_beg(interaction, "The Sweet Old Lady", 0.85, 5, 25, success_msgs, fail_msgs)

    @discord.ui.button(label="Rich Businessman", style=discord.ButtonStyle.primary, emoji="👔")
    async def btn_businessman(self, interaction: discord.Interaction, button: discord.ui.Button):
        success_msgs = [
            "tosses **${amount}** at you without looking up from his phone.",
            "feels a rare moment of pity and writes you a check for **${amount}**.",
            "drops his wallet! You politely return it and he rewards you with **${amount}**!"
        ]
        fail_msgs = [
            "scoffs at you. 'Get a job, hippie!'",
            "calls security to have you removed from the sidewalk.",
            "ignores you completely. Time is money!"
        ]
        await self.process_beg(interaction, "The Rich Businessman", 0.40, 50, 200, success_msgs, fail_msgs)

    @discord.ui.button(label="Passing Celebrity", style=discord.ButtonStyle.danger, emoji="⭐")
    async def btn_celebrity(self, interaction: discord.Interaction, button: discord.ui.Button):
        success_msgs = [
            "takes a selfie with you and tips you **${amount}** for the PR!",
            "makes it rain! You manage to grab **${amount}** from the air.",
            "says 'Don't spend it all in one place!' and hands you **${amount}**."
        ]
        fail_msgs = [
            "hides their face from the paparazzi and runs away.",
            "has their bodyguard shove you into a trash can.",
            "thinks you're an obsessed fan and calls the police."
        ]
        await self.process_beg(interaction, "The Passing Celebrity", 0.20, 150, 500, success_msgs, fail_msgs)

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
                
                # Check for Crafted Items (Passive Income)
                rig_bonus = 0
                server_bonus = 0
                penthouse_bonus = 0
                island_bonus = 0
                ticket_bonus = 0
                
                async with self.bot.db.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ?", (ctx.author.id,)) as cursor:
                    inv = await cursor.fetchall()
                    inventory = {item: qty for item, qty in inv}
                    
                rig_bonus = 200 * inventory.get('Mining Rig', 0)
                server_bonus = 1000 * inventory.get('Server Rack', 0)
                penthouse_bonus = 10000 * inventory.get('Penthouse Suite', 0)
                island_bonus = 100000 * inventory.get('Private Island', 0)
                ticket_bonus = 1 * inventory.get('Insider Bot', 0)

                base_amount = 500
                level_bonus = level * 50
                streak_bonus = effective_streak * 50
                total_amount = base_amount + level_bonus + streak_bonus + rig_bonus + server_bonus + penthouse_bonus + island_bonus
                
                await self.bot.db.execute("UPDATE users SET balance = balance + ?, tickets = tickets + ?, last_daily = ?, daily_streak = ? WHERE user_id = ?", 
                                          (total_amount, ticket_bonus, today, streak, ctx.author.id))
                await self.log_transaction(ctx.author.id, "daily", total_amount, f"Daily reward (Streak: {streak})")
        
        await self.bot.db.commit()
        
        embed = discord.Embed(title="💰 Daily Reward", color=discord.Color.gold())
        embed.add_field(name="Base", value="$500", inline=True)
        embed.add_field(name="Level Bonus", value=f"${level_bonus}", inline=True)
        embed.add_field(name="Streak Bonus", value=f"${streak_bonus} (Day {streak} 🔥)", inline=True)
        
        if rig_bonus > 0:
            embed.add_field(name="Mining Rigs", value=f"${rig_bonus} 🖥️", inline=True)
        if server_bonus > 0:
            embed.add_field(name="Server Racks", value=f"${server_bonus} 🗄️", inline=True)
        if penthouse_bonus > 0:
            embed.add_field(name="Penthouses", value=f"${penthouse_bonus} 🏢", inline=True)
        if island_bonus > 0:
            embed.add_field(name="Private Islands", value=f"${island_bonus} 🏝️", inline=True)
        if ticket_bonus > 0:
            embed.add_field(name="Insider Bots", value=f"🎟️ {ticket_bonus}", inline=True)
            
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
        async with self.bot.db.execute("SELECT work_shifts FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            shifts = row[0] if row else 0
            
        title = "Intern"
        if shifts >= 10: title = "Junior Trader"
        if shifts >= 50: title = "Senior Trader"
        if shifts >= 100: title = "Hedge Fund Manager"
        
        embed = discord.Embed(title=f"🏢 Welcome to Work, {title}!", description="Choose your shift for the next hour. Higher risk jobs pay more, but you might get fired and earn nothing!", color=discord.Color.blue())
        embed.set_footer(text=f"Total Shifts Completed: {shifts}")
        
        view = WorkView(self, ctx.author, shifts)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(description="Beg for some coins on the streets (5m cooldown).")
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def beg(self, ctx):
        embed = discord.Embed(title="🤲 Begging on the Streets", description="You're sitting on the sidewalk with a cup. Who do you want to beg to?", color=discord.Color.gold())
        embed.add_field(name="👵 Sweet Old Lady", value="High chance of success, low reward.", inline=False)
        embed.add_field(name="👔 Rich Businessman", value="Medium chance of success, medium reward.", inline=False)
        embed.add_field(name="⭐ Passing Celebrity", value="Low chance of success, high reward.", inline=False)
        
        view = BegView(self, ctx.author)
        await ctx.send(embed=embed, view=view)

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
        async with self.bot.db.execute("SELECT wanted_level FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            wanted_level = row[0] if row else 0
            
        async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = 'Hacker Laptop'", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            laptop_count = row[0] if row else 0
            
        embed = discord.Embed(title="🕵️ Crime Syndicate", description="Choose your target. The bigger the score, the harder it is to pull off.", color=discord.Color.dark_purple())
        if wanted_level > 0:
            embed.add_field(name="Wanted Level", value=f"{'⭐' * wanted_level}\n*(Fines are increased by {wanted_level * 50}%!)*", inline=False)
        if laptop_count > 0:
            embed.add_field(name="Hacker Laptops", value=f"💻 You have {laptop_count} laptops boosting your success and payout!", inline=False)
            
        view = CrimeView(self, ctx.author, wanted_level, laptop_count)
        await ctx.send(embed=embed, view=view)

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
            has_safe = row and row[0] > 0
            
        if has_safe:
            async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = 'Lockpick Set'", (ctx.author.id,)) as cursor:
                row = await cursor.fetchone()
                has_lockpick = row and row[0] > 0
                
            if has_lockpick:
                await ctx.send("🔓 **Lockpick Used!** You silently bypassed their Safe!")
                await self.bot.db.execute("UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_name = 'Lockpick Set'", (ctx.author.id,))
                await self.bot.db.commit()
            elif random.random() < 0.8: # 80% fail if Safe
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

    @commands.hybrid_command(description="Use a consumable item from your inventory.")
    async def use(self, ctx, item_name: str):
        item_key = item_name.lower()
        
        async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name COLLATE NOCASE = ?", (ctx.author.id, item_name)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] <= 0:
                await ctx.send(f"❌ You don't have any **{item_name.title()}** in your inventory.")
                return

        if item_key in ["fake id", "lawyer"]:
            async with self.bot.db.execute("SELECT wanted_level FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
                user_row = await cursor.fetchone()
                wanted_level = user_row[0] if user_row else 0
                
            if wanted_level == 0:
                await ctx.send("You don't have a Wanted Level to clear!")
                return
                
            # Consume the item
            await self.bot.db.execute("UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_name COLLATE NOCASE = ?", (ctx.author.id, item_name))
            
            # Clear wanted level
            await self.bot.db.execute("UPDATE users SET wanted_level = 0 WHERE user_id = ?", (ctx.author.id,))
            await self.bot.db.commit()
            
            flavor = "Your Fake ID successfully scrubbed you from the police database!" if item_key == "fake id" else "Your Lawyer successfully got all your charges dropped!"
            embed = discord.Embed(title="🚓 Name Cleared!", description=f"You used a **{item_name.title()}**!\n\n{flavor}\n**Wanted Level is now ⭐ 0!**", color=discord.Color.green())
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ **{item_name.title()}** is not a usable item.")

    @commands.hybrid_command(description="Bounty hunt a wanted criminal!")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def bounty(self, ctx, target: discord.Member):
        if target.bot or target == ctx.author:
            return await ctx.send("You can't hunt them.")

        async with self.bot.db.execute("SELECT wanted_level, balance FROM users WHERE user_id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return await ctx.send(f"{target.display_name} doesn't even have a bank account, let alone a bounty.")
            
            wanted_level = row[0]
            target_bal = row[1]
            
        if wanted_level < 3:
            return await ctx.send(f"❌ {target.display_name} only has a **{wanted_level}-Star** wanted level. You can only hunt players with **3 or more stars**.")

        # Hunting logic
        # 3 stars = 60% chance to fail, 4 stars = 50%, 5 stars = 40%
        # The higher the wanted level, the more money you get, but maybe harder?
        # Let's make it fixed 50/50 for now.
        success_chance = 0.50
        
        if random.random() < success_chance:
            # Hunter wins!
            # Take up to 50% of the target's balance + a massive bonus from the state
            bounty_bonus = wanted_level * 2000
            stolen_money = int(target_bal * 0.5)
            total_reward = bounty_bonus + stolen_money
            
            await self.bot.db.execute("UPDATE users SET balance = balance - ?, wanted_level = 0 WHERE user_id = ?", (stolen_money, target.id))
            await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_reward, ctx.author.id))
            await self.bot.db.commit()
            
            await self.log_transaction(ctx.author.id, "bounty", total_reward, f"Hunted {target.display_name}")
            await self.log_transaction(target.id, "bounty", -stolen_money, f"Busted by {ctx.author.display_name}")
            
            embed = discord.Embed(title="🎯 BOUNTY CLAIMED!", description=f"You successfully hunted down the notorious {target.mention}!", color=discord.Color.green())
            embed.add_field(name="Target Arrested", value="Their Wanted Level has been reset to 0.", inline=False)
            embed.add_field(name="Reward Claimed", value=f"State Bounty: **${bounty_bonus}**\nConfiscated Cash: **${stolen_money}**\n\nTotal Payout: **${total_reward}**", inline=False)
            await ctx.send(embed=embed)
        else:
            # Criminal wins!
            # Hunter pays a hospital bill and criminal gets a star
            fine = random.randint(1000, 3000)
            new_wanted = min(5, wanted_level + 1)
            
            await self.bot.db.execute("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?", (fine, ctx.author.id))
            await self.bot.db.execute("UPDATE users SET wanted_level = ? WHERE user_id = ?", (new_wanted, target.id))
            await self.bot.db.commit()
            
            embed = discord.Embed(title="🚑 HUNT FAILED!", description=f"{target.mention} completely outsmarted you and escaped!", color=discord.Color.red())
            embed.add_field(name="Hospital Bill", value=f"You got beat up and paid **${fine}** in medical bills.", inline=False)
            embed.add_field(name="Target Status", value=f"Their Wanted Level increased to **{'⭐' * new_wanted}**", inline=False)
            await ctx.send(embed=embed)

    @commands.hybrid_command(aliases=["top"], description="View the interactive Global Leaderboards.")
    async def leaderboard(self, ctx):
        view = LeaderboardView(self, ctx.guild, ctx.author)
        
        rows, total_pages, stat_name, format_str, offset = await view.get_data()
        
        embed = discord.Embed(title="💰 Richest Citizens", color=discord.Color.gold())
        for i, row in enumerate(rows, 1):
            rank = offset + i
            user_id = row[0]
            val = row[1]
            
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"Unknown User ({user_id})"
            
            prefix = ""
            if rank == 1: prefix = "🥇 "
            elif rank == 2: prefix = "🥈 "
            elif rank == 3: prefix = "🥉 "
            else: prefix = f"#{rank} "
            
            val_str = format_str.format(val=val)
            embed.add_field(name=f"{prefix}{name}", value=f"**{stat_name}:** {val_str}", inline=False)
            
        embed.set_footer(text=f"Page 1/{total_pages} | Requested by {ctx.author.display_name}")
        
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Economy(bot))
