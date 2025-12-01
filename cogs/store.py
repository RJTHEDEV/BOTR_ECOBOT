import discord
from discord.ext import commands

class Store(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="View items in the shop.")
    async def shop(self, ctx, currency_type: str = "coins"):
        currency_type = currency_type.lower()
        if currency_type not in ["coins", "tickets"]:
            await ctx.send("Invalid currency type. Use 'coins' or 'tickets'.")
            return

        async with self.bot.db.execute("SELECT name, price, description FROM store WHERE currency = ?", (currency_type,)) as cursor:
            items = await cursor.fetchall()
        
        if not items:
            await ctx.send(f"The {currency_type} shop is currently empty.")
            return

        embed = discord.Embed(title=f"Community Shop ({currency_type.capitalize()})", color=discord.Color.gold())
        for name, price, description in items:
            cost_str = f"${price}" if currency_type == "coins" else f"🎟️ {price}"
            embed.add_field(name=f"{name} - {cost_str}", value=description, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Buy an item from the shop.")
    async def buy(self, ctx, *, item_name: str):
        # Check if item exists
        async with self.bot.db.execute("SELECT price, currency FROM store WHERE name = ?", (item_name,)) as cursor:
            item = await cursor.fetchone()
        
        if not item:
            await ctx.send("Item not found.")
            return
        
        price, currency = item

        # Check balance
        if currency == "coins":
            async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
                user = await cursor.fetchone()
            balance = user[0] if user else 0
            if balance < price:
                await ctx.send("You don't have enough money!")
                return
            await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, ctx.author.id))
        else: # tickets
            async with self.bot.db.execute("SELECT tickets FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
                user = await cursor.fetchone()
            tickets = user[0] if user else 0
            if tickets < price:
                await ctx.send("You don't have enough tickets!")
                return
            await self.bot.db.execute("UPDATE users SET tickets = tickets - ? WHERE user_id = ?", (price, ctx.author.id))

        # Add to inventory
        async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (ctx.author.id, item_name)) as cursor:
            owned = await cursor.fetchone()
        
        if owned:
            await self.bot.db.execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_name = ?", (ctx.author.id, item_name))
        else:
            await self.bot.db.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, 1)", (ctx.author.id, item_name))
        
        await self.bot.db.commit()
        cost_str = f"${price}" if currency == "coins" else f"🎟️ {price}"
        await ctx.send(f"You bought {item_name} for {cost_str}!")

    @commands.hybrid_command(description="View your inventory.")
    async def inventory(self, ctx):
        async with self.bot.db.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ?", (ctx.author.id,)) as cursor:
            items = await cursor.fetchall()
        
        if not items:
            await ctx.send("Your inventory is empty.")
            return

        embed = discord.Embed(title=f"{ctx.author.name}'s Inventory", color=discord.Color.blue())
        for name, quantity in items:
            embed.add_field(name=name, value=f"Quantity: {quantity}", inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Admin: Add an item to the shop.")
    @commands.has_permissions(administrator=True)
    async def additem(self, ctx, name: str, price: int, description: str, currency: str = "coins"):
        if currency not in ["coins", "tickets"]:
            await ctx.send("Invalid currency. Use 'coins' or 'tickets'.")
            return
        try:
            await self.bot.db.execute("INSERT INTO store (name, price, description, currency) VALUES (?, ?, ?, ?)", (name, price, description, currency))
            await self.bot.db.commit()
            await ctx.send(f"Added {name} to the {currency} store.")
        except Exception as e:
            await ctx.send(f"Error adding item: {e}")

async def setup(bot):
    await bot.add_cog(Store(bot))
