import discord
from discord.ext import commands

class Store(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="View items in the shop.")
    async def shop(self, ctx):
        # Get distinct categories
        async with self.bot.db.execute("SELECT DISTINCT category FROM store") as cursor:
            rows = await cursor.fetchall()
            categories = [r[0] for r in rows] if rows else ["Items"]
        
        # Default to showing all or first category? Let's show "All" or just prompt to select.
        # Actually, let's show the first category by default or a welcome screen.
        
        view = ShopView(self.bot, categories, ctx.author)
        embed = discord.Embed(title="🛒 Community Shop", description="Select a category below to browse items.", color=discord.Color.gold())
        await ctx.send(embed=embed, view=view)

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
            await self.bot.get_cog("Economy").log_transaction(ctx.author.id, "shop", -price, f"Bought {item_name}")
        else: # tickets
            async with self.bot.db.execute("SELECT tickets FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
                user = await cursor.fetchone()
            tickets = user[0] if user else 0
            if tickets < price:
                await ctx.send("You don't have enough tickets!")
                return
            await self.bot.db.execute("UPDATE users SET tickets = tickets - ? WHERE user_id = ?", (price, ctx.author.id))
            await self.bot.get_cog("Economy").log_transaction(ctx.author.id, "shop (tickets)", -price, f"Bought {item_name}")

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
    async def additem(self, ctx, name: str, price: int, description: str, currency: str = "coins", category: str = "Items"):
        if currency not in ["coins", "tickets"]:
            await ctx.send("Invalid currency. Use 'coins' or 'tickets'.")
            return
        try:
            await self.bot.db.execute("INSERT INTO store (name, price, description, currency, category) VALUES (?, ?, ?, ?, ?)", (name, price, description, currency, category))
            await self.bot.db.commit()
            await ctx.send(f"Added {name} to the {currency} store (Category: {category}).")
        except Exception as e:
            await ctx.send(f"Error adding item: {e}")

class ShopSelect(discord.ui.Select):
    def __init__(self, bot, categories):
        self.bot = bot
        options = []
        for cat in categories:
            options.append(discord.SelectOption(label=cat, value=cat))
        
        super().__init__(placeholder="Select a category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        
        async with self.bot.db.execute("SELECT name, price, description, currency FROM store WHERE category = ?", (category,)) as cursor:
            items = await cursor.fetchall()
        
        if not items:
            await interaction.response.edit_message(content="Category is empty.", embed=None)
            return

        embed = discord.Embed(title=f"🛒 Shop: {category}", color=discord.Color.gold())
        for name, price, description, currency in items:
            cost_str = f"${price}" if currency == "coins" else f"🎟️ {price}"
            embed.add_field(name=f"{name} - {cost_str}", value=description, inline=False)
        
        await interaction.response.edit_message(embed=embed)

class ShopView(discord.ui.View):
    def __init__(self, bot, categories, user):
        super().__init__(timeout=180)
        self.user = user
        self.add_item(ShopSelect(bot, categories))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

async def setup(bot):
    await bot.add_cog(Store(bot))
