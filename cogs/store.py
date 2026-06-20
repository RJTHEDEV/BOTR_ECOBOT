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
    @discord.app_commands.default_permissions(administrator=True)
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

    @store_group.command(description="Admin: Remove an item from the shop.")
    @discord.app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def removeitem(self, ctx, *, name: str):
        try:
            async with self.bot.db.execute("DELETE FROM store WHERE name = ?", (name,)) as cursor:
                pass
            await self.bot.db.commit()
            await ctx.send(f"Removed **{name}** from the store. Note: it might still be in people's inventories.")
        except Exception as e:
            await ctx.send(f"Error removing item: {e}")

    @store_group.command(description="Admin: Auto-populate the store with a full community setup.")
    @discord.app_commands.default_permissions(administrator=True)
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
            ('Penthouse Suite', 500000, 'Grants $10,000 passive income daily!', 'coins', 'Real Estate'),
            ('Private Island', 5000000, 'Grants $100,000 passive income daily!', 'coins', 'Real Estate'),
            ('Gold Name Color', 100000, 'Paint your name gold in chat', 'coins', 'Cosmetics & Flex'),
            ('Diamond Badge', 20, 'Exclusive diamond badge next to your name', 'tickets', 'Cosmetics & Flex'),
            ('Custom Command', 50, 'We will program a custom bot command for you', 'tickets', 'Cosmetics & Flex'),
            ('Fake ID', 10000, 'Clears your Wanted Level instantly.', 'coins', 'Consumables'),
            ('Lawyer', 5, 'Clears your Wanted Level instantly.', 'tickets', 'Consumables'),
            ('Iron Ore', 1000, 'A hard metal used for crafting heavy items.', 'coins', 'Crafting Materials'),
            ('Wood', 500, 'Basic building material for crafting.', 'coins', 'Crafting Materials'),
            ('Magic Dust', 1, 'Mystical dust required for advanced technology and safes.', 'tickets', 'Crafting Materials'),
            ('Silicon Chip', 5000, 'Advanced electronics for high-tier crafting.', 'coins', 'Crafting Materials'),
            ('Gold Bar', 3, 'Extremely valuable metal used in premium recipes.', 'tickets', 'Crafting Materials'),
            ('Copper Wire', 1500, 'Conductive material for electronics.', 'coins', 'Crafting Materials')
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

    @store_group.command(description="Craft special items using raw materials from the store. Leave blank to view recipes.")
    async def craft(self, ctx, recipe: str = None):
        recipes = {
            "mining rig": {"Iron Ore": 10, "Wood": 5},
            "safe": {"Wood": 10, "Magic Dust": 5},
            "hacker laptop": {"Silicon Chip": 2, "Wood": 5, "Copper Wire": 10},
            "server rack": {"Silicon Chip": 20, "Copper Wire": 50, "Iron Ore": 10},
            "insider bot": {"Silicon Chip": 10, "Gold Bar": 5},
            "lockpick set": {"Iron Ore": 5, "Copper Wire": 2}
        }
        recipe_key = recipe.lower() if recipe else ""
        if recipe_key not in recipes:
            await self.send_recipes_embed(ctx)
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

    @store_group.command(description="View all available crafting recipes.")
    async def recipes(self, ctx):
        await self.send_recipes_embed(ctx)

    async def send_recipes_embed(self, ctx):
        embed = discord.Embed(title="🛠️ Crafting Recipes", color=discord.Color.orange())
        embed.description = "Buy raw materials in the store (`/store shop`) and craft them into powerful upgrades!\n\nUse `/store craft <recipe>` to build an item."
        embed.add_field(name="🖥️ Mining Rig", value="**Cost:** 10x Iron Ore, 5x Wood\n**Effect:** Generates $200 passive income every time you claim `/daily`.", inline=False)
        embed.add_field(name="🔒 Safe", value="**Cost:** 10x Wood, 5x Magic Dust\n**Effect:** Protects your wallet! 80% chance to block robbers and fine them.", inline=False)
        embed.add_field(name="💻 Hacker Laptop", value="**Cost:** 2x Silicon Chip, 5x Wood, 10x Copper Wire\n**Effect:** Increases `/crime` success chance by 5% and payout by $100 per laptop.", inline=False)
        embed.add_field(name="🗄️ Server Rack", value="**Cost:** 20x Silicon Chip, 50x Copper Wire, 10x Iron Ore\n**Effect:** Generates $1,000 passive income every time you claim `/daily`.", inline=False)
        embed.add_field(name="🤖 Insider Bot", value="**Cost:** 10x Silicon Chip, 5x Gold Bar\n**Effect:** Generates 1 Ticket (🎟️) every time you claim `/daily`.", inline=False)
        embed.add_field(name="🔓 Lockpick Set", value="**Cost:** 5x Iron Ore, 2x Copper Wire\n**Effect:** Automatically bypasses a victim's Safe when you `/rob` them. (Consumed on use).", inline=False)
        await ctx.send(embed=embed)
    @store_group.command(name="buy_tickets", description="Purchase VIP Tickets with cryptocurrency (BTC, ETH, SOL).")
    async def buy_tickets(self, ctx):
        embed = discord.Embed(title="🎫 Purchase VIP Tickets", color=discord.Color.gold())
        embed.description = (
            "You can purchase **VIP Tickets (🎟️)** using cryptocurrency to unlock premium items, roles, and exclusive perks!\n\n"
            "**Pricing:**\n"
            "• 🎟️ 5 Tickets = $5.00\n"
            "• 🎟️ 15 Tickets = $12.00 *(Best Value!)*\n"
            "• 🎟️ 50 Tickets = $35.00 *(Whale Status!)*\n\n"
            "**How to Buy:**\n"
            "1. Send the equivalent crypto amount to one of the wallets below.\n"
            "2. Open a support ticket in the server and provide your transaction hash/proof of payment.\n"
            "3. An Admin will credit your account immediately."
        )
        
        embed.add_field(name="🪙 Bitcoin (BTC)", value="`bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh`", inline=False)
        embed.add_field(name="🔷 Ethereum (ETH / ERC-20)", value="`0x71C7656EC7ab88b098defB751B7401B5f6d8976F`", inline=False)
        embed.add_field(name="🟣 Solana (SOL)", value="`HN7cABqLq46Es1jh92dQQisAq662SmxELLLsHHe4YWrH`", inline=False)
        
        embed.set_footer(text="Make sure you send on the correct network! Admins will manually verify your deposit.")
        await ctx.send(embed=embed)

class ItemBuySelect(discord.ui.Select):
    def __init__(self, bot, category_items, view_instance):
        self.bot = bot
        self.view_instance = view_instance
        options = []
        for name, price, description, currency in category_items:
            cost_str = f"`${price:,}`" if currency == 'coins' else f"`🎟️ {price}`"
            # Truncate description to 100 chars
            desc = description[:97] + "..." if len(description) > 100 else description
            options.append(discord.SelectOption(label=f"Add {name}", description=f"{cost_str} - {desc}"[:100], value=name))
            
        super().__init__(placeholder="Select an item to add to your cart...", min_values=1, max_values=1, options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        item_name = self.values[0]
        self.view_instance.cart[item_name] = self.view_instance.cart.get(item_name, 0) + 1
        await self.view_instance.update_embed(interaction)

class CheckoutButton(discord.ui.Button):
    def __init__(self, view_instance):
        super().__init__(style=discord.ButtonStyle.success, label="Checkout", emoji="💳", row=2)
        self.view_instance = view_instance

    async def callback(self, interaction: discord.Interaction):
        if not self.view_instance.cart:
            await interaction.response.send_message("Your cart is empty!", ephemeral=True)
            return

        bot = self.view_instance.bot
        user_id = interaction.user.id
        
        # Calculate totals
        total_coins = 0
        total_tickets = 0
        items_data = {}
        
        for item_name, qty in self.view_instance.cart.items():
            async with bot.db.execute("SELECT price, currency FROM store WHERE name = ?", (item_name,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    price, currency = row
                    items_data[item_name] = {'price': price, 'currency': currency, 'qty': qty}
                    if currency == 'coins':
                        total_coins += price * qty
                    else:
                        total_tickets += price * qty

        # Check balances
        async with bot.db.execute("SELECT balance, tickets FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user_row = await cursor.fetchone()
            user_coins = user_row[0] if user_row else 0
            user_tickets = user_row[1] if user_row else 0

        if user_coins < total_coins:
            await interaction.response.send_message(f"❌ You don't have enough coins! You need **${total_coins:,}**, but you only have **${user_coins:,}**.", ephemeral=True)
            return
        if user_tickets < total_tickets:
            await interaction.response.send_message(f"❌ You don't have enough tickets! You need **🎟️ {total_tickets}**, but you only have **🎟️ {user_tickets}**.", ephemeral=True)
            return

        # Deduct balances
        await bot.db.execute("UPDATE users SET balance = balance - ?, tickets = tickets - ? WHERE user_id = ?", (total_coins, total_tickets, user_id))
        
        # Log transaction
        if total_coins > 0:
            await bot.get_cog("Economy").log_transaction(user_id, "shop_checkout", -total_coins, "Bought multiple items via cart")
        if total_tickets > 0:
            await bot.get_cog("Economy").log_transaction(user_id, "shop_checkout_tickets", -total_tickets, "Bought multiple items via cart")

        # Add to inventory
        for item_name, data in items_data.items():
            qty = data['qty']
            async with bot.db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name)) as cursor:
                owned = await cursor.fetchone()
            
            if owned:
                await bot.db.execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_name = ?", (qty, user_id, item_name))
            else:
                await bot.db.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?)", (user_id, item_name, qty))

        await bot.db.commit()
        
        # Receipt
        receipt = "\n".join([f"• {q}x **{n}**" for n, q in self.view_instance.cart.items()])
        cost_str = ""
        if total_coins > 0: cost_str += f"**${total_coins:,}** "
        if total_tickets > 0: cost_str += f"**🎟️ {total_tickets} tickets**"
        
        self.view_instance.cart.clear()
        
        embed = discord.Embed(title="🧾 Checkout Complete!", description=f"You successfully purchased:\n{receipt}\n\n**Total Paid:** {cost_str}", color=discord.Color.green())
        
        # Clear items on view and add a return to shop button? 
        # Or just edit the message to be a final receipt.
        self.view_instance.clear_items()
        await interaction.response.edit_message(embed=embed, view=self.view_instance)
        
class ClearCartButton(discord.ui.Button):
    def __init__(self, view_instance):
        super().__init__(style=discord.ButtonStyle.danger, label="Clear Cart", emoji="🗑️", row=2)
        self.view_instance = view_instance

    async def callback(self, interaction: discord.Interaction):
        self.view_instance.cart.clear()
        await self.view_instance.update_embed(interaction)

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
        self.view_instance.current_category = category
        await self.view_instance.update_embed(interaction)

class ShopView(discord.ui.View):
    def __init__(self, bot, categories, user):
        super().__init__(timeout=180)
        self.bot = bot
        self.user = user
        self.categories = categories
        self.cart = {} # {item_name: quantity}
        self.current_category = None
        
        self.cat_select = ShopSelect(bot, categories, self)
        self.add_item(self.cat_select)
        self.add_item(CheckoutButton(self))
        self.add_item(ClearCartButton(self))
        
    async def update_embed(self, interaction):
        if not self.current_category:
            embed = discord.Embed(title="🛒 Community Shop", description="Select a category below to browse items.", color=discord.Color.gold())
            await interaction.response.edit_message(embed=embed, view=self)
            return
            
        async with self.bot.db.execute("SELECT name, price, description, currency FROM store WHERE category = ?", (self.current_category,)) as cursor:
            items = await cursor.fetchall()

        embed = discord.Embed(title=f"🛒 {self.current_category} Shop", description="Select an item from the dropdown to add it to your cart!", color=discord.Color.gold())
        for name, price, description, currency in items:
            cost_str = f"**${price:,}**" if currency == "coins" else f"**🎟️ {price}**"
            embed.add_field(name=f"{name} - {cost_str}", value=description, inline=False)
            
        # Cart Field
        if self.cart:
            cart_str = "\n".join([f"• {q}x {n}" for n, q in self.cart.items()])
            
            # Calculate total preview
            total_c = 0
            total_t = 0
            for c_item, qty in self.cart.items():
                async with self.bot.db.execute("SELECT price, currency FROM store WHERE name = ?", (c_item,)) as cursor:
                    r = await cursor.fetchone()
                    if r:
                        if r[1] == 'coins': total_c += r[0] * qty
                        else: total_t += r[0] * qty
                        
            t_str = ""
            if total_c > 0: t_str += f"**${total_c:,}** "
            if total_t > 0: t_str += f"**🎟️ {total_t}**"
            
            embed.add_field(name="🛒 Your Cart", value=f"{cart_str}\n\n**Total:** {t_str}", inline=False)
        else:
            embed.add_field(name="🛒 Your Cart", value="*Cart is empty*", inline=False)

        # Update view
        self.clear_items()
        self.add_item(self.cat_select)
        if items:
            self.add_item(ItemBuySelect(self.bot, items, self))
        self.add_item(CheckoutButton(self))
        self.add_item(ClearCartButton(self))
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("This isn't your shop session!", ephemeral=True)
            return False
        return True

async def setup(bot):
    await bot.add_cog(Store(bot))
