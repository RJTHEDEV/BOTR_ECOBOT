import discord
from discord.ext import commands

class Store(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="store", invoke_without_command=True)
    async def store_group(self, ctx):
        await ctx.send("Use `/store <action>`")


    @store_group.command(description="View items in the shop.")
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

    @store_group.command(description="Buy an item from the shop.")
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

    @store_group.command(description="View your inventory.")
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

    @store_group.command(description="Admin: Add an item to the shop.")
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

    @store_group.command(description="Admin: Auto-populate the store with a full community setup.")
    @commands.has_permissions(administrator=True)
    async def populate(self, ctx):
        items = [
            ('VIP Role', 100000, 'Exclusive access to VIP channels', 'coins', 'Server Roles'),
            ('Whale Role', 500000, 'The ultimate flex role for top traders', 'coins', 'Server Roles'),
            ('Chad Role', 50000, 'Show off your chad status', 'coins', 'Server Roles'),
            ('Shoutout on Stream', 25000, 'The streamer will shout you out live!', 'coins', 'Streamer Perks'),
            ('Soundboard Access', 10000, 'Trigger a sound effect on stream', 'coins', 'Streamer Perks'),
            ('Play with Streamer', 5, 'Join the lobby for the next game', 'tickets', 'Streamer Perks'),
            ('Priority Queue', 2, 'Skip the line for community games', 'tickets', 'Gaming Perks'),
            ('1v1 Challenge', 15000, 'Challenge the admin to a 1v1', 'coins', 'Gaming Perks'),
            ('Custom VC', 75000, 'Get your own private voice channel', 'coins', 'Gaming Perks'),
            ('Trading Floor Pass', 200000, 'Access to the premium trading floor', 'coins', 'Trading & Economy'),
            ('Options Signals', 10, '1 week of premium options alerts', 'tickets', 'Trading & Economy'),
            ('Stock Tip', 50000, 'One exclusive insider stock tip', 'coins', 'Trading & Economy'),
            ('Gold Name Color', 100000, 'Paint your name gold in chat', 'coins', 'Cosmetics & Flex'),
            ('Diamond Badge', 20, 'Exclusive diamond badge next to your name', 'tickets', 'Cosmetics & Flex'),
            ('Custom Command', 50, 'We will program a custom bot command for you', 'tickets', 'Cosmetics & Flex'),
            ('Iron Ore', 1000, 'A hard metal used for crafting heavy items.', 'coins', 'Crafting Materials'),
            ('Wood', 500, 'Basic building material for crafting.', 'coins', 'Crafting Materials'),
            ('Magic Dust', 1, 'Mystical dust required for advanced technology and safes.', 'tickets', 'Crafting Materials')
        ]
        
        added = 0
        for name, price, description, currency, category in items:
            try:
                await self.bot.db.execute("INSERT INTO store (name, price, description, currency, category) VALUES (?, ?, ?, ?, ?)", (name, price, description, currency, category))
                added += 1
            except Exception:
                pass # Skip if already exists (UNIQUE constraint)
                
        await self.bot.db.commit()
        await ctx.send(f"✅ Store populated with {added} new community items!")

    @store_group.command(description="Craft special items using raw materials from the store.")
    async def craft(self, ctx, recipe: str):
        recipes = {
            "mining rig": {"Iron Ore": 10, "Wood": 5},
            "safe": {"Wood": 10, "Magic Dust": 5},
            "hacker laptop": {"Iron Ore": 5, "Wood": 5, "Magic Dust": 10}
        }
        
        recipe_key = recipe.lower()
        if recipe_key not in recipes:
            embed = discord.Embed(title="🛠️ Crafting Recipes", color=discord.Color.orange())
            embed.description = "Buy raw materials in the store (`/store shop`) and craft them into powerful upgrades!\n\nUse `/store craft <recipe>` to build an item."
            embed.add_field(name="🖥️ Mining Rig", value="**Cost:** 10x Iron Ore, 5x Wood\n**Effect:** Generates $200 passive income every time you claim `/daily`.", inline=False)
            embed.add_field(name="🔒 Safe", value="**Cost:** 10x Wood, 5x Magic Dust\n**Effect:** Protects your wallet! 80% chance to block robbers and fine them.", inline=False)
            embed.add_field(name="💻 Hacker Laptop", value="**Cost:** 5x Iron Ore, 5x Wood, 10x Magic Dust\n**Effect:** (Coming Soon) Boosts `/crime` payouts.", inline=False)
            await ctx.send(embed=embed)
            return

        requirements = recipes[recipe_key]
        
        # Check inventory for requirements
        async with self.bot.db.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ?", (ctx.author.id,)) as cursor:
            inv = await cursor.fetchall()
            inventory = {item: qty for item, qty in inv}

        for req_item, req_qty in requirements.items():
            if inventory.get(req_item, 0) < req_qty:
                await ctx.send(f"❌ You don't have enough **{req_item}**. You need {req_qty}, but you only have {inventory.get(req_item, 0)}.")
                return

        # Deduct items
        for req_item, req_qty in requirements.items():
            await self.bot.db.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?", (req_qty, ctx.author.id, req_item))
            
        # Grant crafted item
        crafted_item = recipe_key.title()
        if inventory.get(crafted_item, 0) > 0:
            await self.bot.db.execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_name = ?", (ctx.author.id, crafted_item))
        else:
            await self.bot.db.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, 1)", (ctx.author.id, crafted_item))
            
        await self.bot.db.commit()
        await ctx.send(f"🎉 **CRAFTING SUCCESS!** You constructed a **{crafted_item}**! It is now active in your inventory.")

class ItemBuySelect(discord.ui.Select):
    def __init__(self, bot, category_items):
        self.bot = bot
        options = []
        for name, price, description, currency in category_items:
            cost_str = f"${price:,}" if currency == "coins" else f"🎟️ {price}"
            options.append(discord.SelectOption(label=f"Buy {name}", description=f"{cost_str} - {description}"[:100], value=name))
            
        super().__init__(placeholder="Select an item to purchase...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        item_name = self.values[0]
        async with self.bot.db.execute("SELECT price, currency FROM store WHERE name = ?", (item_name,)) as cursor:
            item = await cursor.fetchone()
            
        if not item:
            await interaction.response.send_message("Item not found.", ephemeral=True)
            return
            
        price, currency = item
        
        # Check balance
        if currency == "coins":
            async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (interaction.user.id,)) as cursor:
                user = await cursor.fetchone()
            balance = user[0] if user else 0
            if balance < price:
                await interaction.response.send_message(f"❌ You don't have enough coins! You need **${price:,}**.", ephemeral=True)
                return
            await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, interaction.user.id))
            await self.bot.get_cog("Economy").log_transaction(interaction.user.id, "shop", -price, f"Bought {item_name}")
        else: # tickets
            async with self.bot.db.execute("SELECT tickets FROM users WHERE user_id = ?", (interaction.user.id,)) as cursor:
                user = await cursor.fetchone()
            tickets = user[0] if user else 0
            if tickets < price:
                await interaction.response.send_message(f"❌ You don't have enough tickets! You need **🎟️ {price}**.", ephemeral=True)
                return
            await self.bot.db.execute("UPDATE users SET tickets = tickets - ? WHERE user_id = ?", (price, interaction.user.id))
            await self.bot.get_cog("Economy").log_transaction(interaction.user.id, "shop (tickets)", -price, f"Bought {item_name}")

        # Add to inventory
        async with self.bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (interaction.user.id, item_name)) as cursor:
            owned = await cursor.fetchone()
        
        if owned:
            await self.bot.db.execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_name = ?", (interaction.user.id, item_name))
        else:
            await self.bot.db.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, 1)", (interaction.user.id, item_name))
        
        await self.bot.db.commit()
        cost_str = f"**${price:,}**" if currency == "coins" else f"**🎟️ {price} tickets**"
        await interaction.response.send_message(f"✅ You successfully purchased **{item_name}** for {cost_str}! It has been added to your `/store inventory`.", ephemeral=True)

class ShopSelect(discord.ui.Select):
    def __init__(self, bot, categories, view_instance):
        self.bot = bot
        self.view_instance = view_instance
        options = []
        for cat in categories:
            options.append(discord.SelectOption(label=cat, value=cat, emoji="🛒"))
        
        super().__init__(placeholder="Select a store category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        
        async with self.bot.db.execute("SELECT name, price, description, currency FROM store WHERE category = ?", (category,)) as cursor:
            items = await cursor.fetchall()
        
        if not items:
            await interaction.response.edit_message(content="Category is empty.", embed=None)
            return

        embed = discord.Embed(title=f"🛒 {category} Shop", description="Select an item from the dropdown below to purchase it instantly!", color=discord.Color.gold())
        for name, price, description, currency in items:
            cost_str = f"${price:,}" if currency == "coins" else f"🎟️ {price}"
            embed.add_field(name=f"{name} - {cost_str}", value=description, inline=False)
        
        # Update view with Buy Select
        self.view_instance.clear_items()
        self.view_instance.add_item(self) # Keep the category selector
        self.view_instance.add_item(ItemBuySelect(self.bot, items)) # Add item buy selector
        
        await interaction.response.edit_message(embed=embed, view=self.view_instance)

class ShopView(discord.ui.View):
    def __init__(self, bot, categories, user):
        super().__init__(timeout=180)
        self.user = user
        self.add_item(ShopSelect(bot, categories, self))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

async def setup(bot):
    await bot.add_cog(Store(bot))
