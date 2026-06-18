import discord
from discord.ext import commands
import datetime
import random

PET_TYPES = {
    "dog": {"price": 5000, "emoji": "🐶", "buff_desc": "+5% Extra Coins from Working/Begging", "favorite_food": "bone"},
    "cat": {"price": 5000, "emoji": "🐱", "buff_desc": "+5% Robbery Success Chance", "favorite_food": "fish"},
    "dragon": {"price": 25000, "emoji": "🐉", "buff_desc": "+10% Extra Coins across all Economy commands", "favorite_food": "steak"},
    "monkey": {"price": 10000, "emoji": "🐵", "buff_desc": "+5% Extra XP from Chatting", "favorite_food": "banana"},
    "penguin": {"price": 8000, "emoji": "🐧", "buff_desc": "-5% Cooldown on Daily Command", "favorite_food": "fish"},
    "tiger": {"price": 20000, "emoji": "🐯", "buff_desc": "+10% Win Rate in Arena/Crime", "favorite_food": "steak"},
    "parrot": {"price": 7500, "emoji": "🦜", "buff_desc": "Occasionally finds random items for you", "favorite_food": "seeds"}
}

FOOD_TYPES = {
    "bone": {"emoji": "🦴", "cost": 100, "base_hunger": 20},
    "fish": {"emoji": "🐟", "cost": 150, "base_hunger": 25},
    "steak": {"emoji": "🥩", "cost": 500, "base_hunger": 50},
    "banana": {"emoji": "🍌", "cost": 100, "base_hunger": 20},
    "seeds": {"emoji": "🌻", "cost": 50, "base_hunger": 15},
    "premium kibble": {"emoji": "🥫", "cost": 1000, "base_hunger": 100} # Loved by all
}

class Pets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def pet_type_autocomplete(self, interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
        choices = [discord.app_commands.Choice(name=f"{data['emoji']} {p.title()} (${data['price']:,})", value=p) 
                   for p, data in PET_TYPES.items() if current.lower() in p.lower()]
        return choices[:25]
        
    async def food_autocomplete(self, interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
        choices = [discord.app_commands.Choice(name=f"{data['emoji']} {f.title()} (${data['cost']:,})", value=f) 
                   for f, data in FOOD_TYPES.items() if current.lower() in f.lower()]
        return choices[:25]

    @commands.hybrid_group(invoke_without_command=True, description="Manage your virtual pet.")
    async def pet(self, ctx):
        await ctx.send("Use `/pet shop`, `/pet buy`, `/pet info`, or `/pet feed`.")

    @pet.command(name="shop", description="View the pet shop.")
    async def shop(self, ctx):
        embed = discord.Embed(title="🐾 Pet Shop", description="Buy a pet to earn passive economy buffs!", color=discord.Color.green())
        for p_type, data in PET_TYPES.items():
            embed.add_field(name=f"{data['emoji']} {p_type.title()}", value=f"**Price:** ${data['price']:,}\n**Buff:** {data['buff_desc']}\n**Loves:** {data['favorite_food'].title()}", inline=False)
        await ctx.send(embed=embed)

    @pet.command(name="buy", description="Buy a pet from the shop.")
    @discord.app_commands.autocomplete(pet_type=pet_type_autocomplete)
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
                await ctx.send(f"You don't have enough coins. You need **${price:,}**.")
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
        embed.add_field(name="Active Buff", value=buff if hunger > 20 else "⚠️ Too hungry to buff! Feed them!", inline=False)
        embed.set_footer(text=f"Loves to eat: {PET_TYPES[p_type]['favorite_food'].title()}")
        
        await ctx.send(embed=embed)

    @pet.command(name="feed", description="Feed your pet specific food to restore its hunger.")
    @discord.app_commands.autocomplete(food_name=food_autocomplete)
    async def feed(self, ctx, food_name: str):
        food_name = food_name.lower()
        if food_name not in FOOD_TYPES:
            await ctx.send("Invalid food type. Check the autocomplete menu!")
            return

        async with self.bot.db.execute("SELECT pet_type, last_fed FROM pets WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await ctx.send("You don't own a pet.")
                return
                
        p_type, last_fed = row
        food = FOOD_TYPES[food_name]
        
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            bal_row = await cursor.fetchone()
            if not bal_row or bal_row[0] < food["cost"]:
                await ctx.send(f"You don't have enough coins to buy {food['emoji']} {food_name.title()} (${food['cost']:,}).")
                return
                
        await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (food["cost"], ctx.author.id))
        
        # Calculate current hunger
        last_fed_dt = datetime.datetime.fromisoformat(last_fed)
        hours_since_fed = (datetime.datetime.now() - last_fed_dt).total_seconds() / 3600
        current_hunger = max(0, 100 - int(hours_since_fed * 5))
        
        if current_hunger >= 100:
            await self.bot.db.rollback()
            await ctx.send("Your pet is already full! They refuse to eat anymore right now.")
            return

        restoration = food["base_hunger"]
        is_favorite = False
        if PET_TYPES[p_type]["favorite_food"] == food_name or food_name == "premium kibble":
            restoration *= 2
            is_favorite = True
            
        new_hunger = min(100, current_hunger + restoration)
        
        # Reverse-engineer the new last_fed time
        new_hours_since_fed = (100 - new_hunger) / 5.0
        new_last_fed_dt = datetime.datetime.now() - datetime.timedelta(hours=new_hours_since_fed)
        
        await self.bot.db.execute("UPDATE pets SET last_fed = ? WHERE user_id = ?", (new_last_fed_dt.isoformat(), ctx.author.id))
        await self.bot.db.commit()
        
        embed = discord.Embed(title=f"{food['emoji']} Feeding Time!", color=discord.Color.green())
        embed.description = f"You bought a **{food_name.title()}** for **${food['cost']:,}** and fed it to your pet!"
        
        if is_favorite:
            embed.description += "\n\n💖 **It's their favorite food!** The food restored DOUBLE hunger!"
            
        embed.add_field(name="Fullness", value=f"**{int(current_hunger)}%** ➔ **{int(new_hunger)}%**")
        await ctx.send(embed=embed)

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
            elif p_type == "parrot" and random.random() < 0.2:
                bonus = random.randint(5, 30) * level
                
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
                    await ctx.send(f"{PET_TYPES[p_type]['emoji']} Your pet found an extra **${bonus:,}** for you!", delete_after=5)
                except: pass

async def setup(bot):
    await bot.add_cog(Pets(bot))
