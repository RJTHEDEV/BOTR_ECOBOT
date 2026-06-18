import discord
from discord.ext import commands, tasks
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

class XP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_tracking = {}
        self.last_xp_time = {}

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
        xp_needed = 75 * (current_level ** 2)
        
        if new_xp >= xp_needed:
            new_level = current_level + 1
            await self.bot.db.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, user.id))
            await self.bot.db.commit()
            
            # Announce Level Up
            reward_coins = new_level * 500
            reward_tickets = 1 if new_level % 5 == 0 else 0
            
            await self.bot.db.execute("UPDATE users SET balance = balance + ?, tickets = tickets + ? WHERE user_id = ?", (reward_coins, reward_tickets, user.id))
            await self.bot.db.commit()
            
            try:
                ticket_msg = f" and 🎟️ **{reward_tickets} Ticket(s)**" if reward_tickets > 0 else ""
                base_msg = random.choice(LEVEL_UP_MESSAGES).format(user=user.mention, level=new_level)
                msg = f"{base_msg}\n\nYou've been awarded **${reward_coins}**{ticket_msg}!"
                
                embed = discord.Embed(title="🆙 Level Up!", description=msg, color=discord.Color.blue())
                await user.send(embed=embed)
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
        
        # Check if any tracked streamer is currently live in this guild
        async with self.bot.db.execute("SELECT 1 FROM streamers WHERE guild_id = ? AND is_live = 1 LIMIT 1", (message.guild.id,)) as cursor:
            is_live_stream = await cursor.fetchone() is not None

        multiplier = 2 if is_live_stream else 1
        
        # XP Cooldown (60s)
        now = time.time()
        last_time = self.last_xp_time.get(message.author.id, 0)
        
        if now - last_time >= 60:
            xp_amount = random.randint(10, 20) * multiplier
            await self.add_xp(message.author, xp_amount)
            self.last_xp_time[message.author.id] = now

        # Random Coin Drop (Engage to Earn)
        if random.random() < 0.05: # 5% chance
            reward = random.randint(1, 5) * multiplier
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
                    # Check if any tracked streamer is currently live in this guild
                    multiplier = 1
                    if member.guild:
                        async with self.bot.db.execute("SELECT 1 FROM streamers WHERE guild_id = ? AND is_live = 1 LIMIT 1", (member.guild.id,)) as cursor:
                            is_live_stream = await cursor.fetchone() is not None
                        if is_live_stream: multiplier = 2

                    xp_reward = minutes * 1 * multiplier
                    await self.add_xp(member, xp_reward)
                    
                    coin_reward = minutes * 2 * multiplier
                    async with self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (coin_reward, member.id)) as cursor:
                         if cursor.rowcount == 0:
                             await self.bot.db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (member.id, coin_reward))
                    await self.bot.db.commit()

async def setup(bot):
    await bot.add_cog(XP(bot))
