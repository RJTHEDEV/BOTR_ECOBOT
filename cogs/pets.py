import discord
from discord.ext import commands
import datetime
import random

PET_TYPES = {
    "dog": {"price": 5000, "emoji": "🐶", "buff_desc": "+5% Extra Coins from Working/Begging"},
    "cat": {"price": 5000, "emoji": "🐱", "buff_desc": "+5% Robbery Success Chance"},
    "dragon": {"price": 25000, "emoji": "🐉", "buff_desc": "+10% Extra Coins across all Economy commands"}
}

class Pets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(invoke_without_command=True, description="Manage your virtual pet.")
    async def pet(self, ctx):
        await ctx.send("Use `/pet shop`, `/pet buy`, `/pet info`, or `/pet feed`.")

    @pet.command(name="shop", description="View the pet shop.")
    async def shop(self, ctx):
        embed = discord.Embed(title="🐾 Pet Shop", description="Buy a pet to earn passive economy buffs!", color=discord.Color.green())
        for p_type, data in PET_TYPES.items():
            embed.add_field(name=f"{data['emoji']} {p_type.title()}", value=f"**Price:** ${data['price']}\n**Buff:** {data['buff_desc']}", inline=False)
        await ctx.send(embed=embed)

    @pet.command(name="buy", description="Buy a pet from the shop.")
    async def buy(self, ctx, pet_type: str, *, name: str):
        pet_type = pet_type.lower()
        if pet_type not in PET_TYPES:
            await ctx.send("Invalid pet type. Use `/pet shop`.")
            return
            
        async with self.bot.db.execute("SELECT pet_type FROM pets WHERE user_id = ?", (ctx.author.id,)) as cursor:
            if await cursor.fetchone():
                await ctx.send("You already have a pet! You must abandon it first (feature coming soon).")
                return
                
        price = PET_TYPES[pet_type]["price"]
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < price:
                await ctx.send(f"You don't have enough coins. You need **${price}**.")
                return
                
        # Buy pet
        now = datetime.datetime.now().isoformat()
        await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, ctx.author.id))
        await self.bot.db.execute("INSERT INTO pets (user_id, pet_type, name, level, xp, last_fed) VALUES (?, ?, ?, 1, 0, ?)", 
                                  (ctx.author.id, pet_type, name, now))
        await self.bot.db.commit()
        
        await ctx.send(f"🎉 Congratulations! You adopted a {PET_TYPES[pet_type]['emoji']} **{pet_type.title()}** named **{name}**!")

    @pet.command(name="info", description="Check your pet's status.")
    async def info(self, ctx):
        async with self.bot.db.execute("SELECT pet_type, name, level, xp, last_fed FROM pets WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            await ctx.send("You don't own a pet. Use `/pet shop`.")
            return
            
        p_type, name, level, xp, last_fed = row
        emoji = PET_TYPES[p_type]["emoji"]
        buff = PET_TYPES[p_type]["buff_desc"]
        
        # Calculate hunger
        last_fed_dt = datetime.datetime.fromisoformat(last_fed)
        hours_since_fed = (datetime.datetime.now() - last_fed_dt).total_seconds() / 3600
        hunger = max(0, 100 - int(hours_since_fed * 5)) # Lose 5% hunger per hour
        
        embed = discord.Embed(title=f"{emoji} {name}'s Status", color=discord.Color.blue())
        embed.add_field(name="Type", value=p_type.title(), inline=True)
        embed.add_field(name="Level", value=f"{level} (XP: {xp})", inline=True)
        embed.add_field(name="Hunger (Fullness)", value=f"{hunger}%", inline=True)
        embed.add_field(name="Active Buff", value=buff if hunger > 20 else "⚠️ Too hungry to buff!", inline=False)
        
        await ctx.send(embed=embed)

    @pet.command(name="feed", description="Feed your pet so it gives buffs.")
    async def feed(self, ctx):
        async with self.bot.db.execute("SELECT last_fed FROM pets WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await ctx.send("You don't own a pet.")
                return
                
        now = datetime.datetime.now().isoformat()
        await self.bot.db.execute("UPDATE pets SET last_fed = ? WHERE user_id = ?", (now, ctx.author.id))
        await self.bot.db.commit()
        await ctx.send("🥩 You fed your pet! It is now 100% full and its buffs are active.")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if ctx.author.bot: return
        cmd = ctx.command.name if ctx.command else ""
        
        if cmd in ["work", "beg", "search", "crime", "rob"]:
            # Check for pet buff
            async with self.bot.db.execute("SELECT pet_type, level, last_fed FROM pets WHERE user_id = ?", (ctx.author.id,)) as cursor:
                row = await cursor.fetchone()
                
            if not row: return
            p_type, level, last_fed = row
            
            # Check hunger
            last_fed_dt = datetime.datetime.fromisoformat(last_fed)
            if (datetime.datetime.now() - last_fed_dt).total_seconds() / 3600 > 16:
                return # Too hungry (under 20%)
                
            bonus = 0
            if p_type == "dog" and cmd in ["work", "beg"]:
                bonus = random.randint(10, 50) + (level * 2)
            elif p_type == "dragon":
                bonus = random.randint(20, 100) + (level * 5)
                
            if bonus > 0:
                await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, ctx.author.id))
                
                # Give pet XP
                await self.bot.db.execute("UPDATE pets SET xp = xp + 1 WHERE user_id = ?", (ctx.author.id,))
                
                # Check level up (every 10 xp)
                async with self.bot.db.execute("SELECT xp FROM pets WHERE user_id = ?", (ctx.author.id,)) as c2:
                    xp = (await c2.fetchone())[0]
                    if xp >= level * 10:
                        await self.bot.db.execute("UPDATE pets SET level = level + 1, xp = 0 WHERE user_id = ?", (ctx.author.id,))
                        try:
                            await ctx.author.send(f"🎉 Your pet leveled up to Level {level+1}!")
                        except: pass

                await self.bot.db.commit()
                
                try:
                    await ctx.send(f"{PET_TYPES[p_type]['emoji']} Your pet found an extra **${bonus}** for you!", delete_after=5)
                except: pass

async def setup(bot):
    await bot.add_cog(Pets(bot))
