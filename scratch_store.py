class ItemBuySelect(discord.ui.Select):
    def __init__(self, bot, category_items, view_instance):
        self.bot = bot
        self.view_instance = view_instance
        options = []
        for name, price, description, currency in category_items:
            cost_str = f"${price:,}" if currency == 'coins' else f"??? {price}"
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
        super().__init__(style=discord.ButtonStyle.success, label="Checkout", emoji="??", row=2)
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
            await interaction.response.send_message(f"? You don't have enough coins! You need ****, but you only have ****.", ephemeral=True)
            return
        if user_tickets < total_tickets:
            await interaction.response.send_message(f"? You don't have enough tickets! You need **??? {total_tickets}**, but you only have **??? {user_tickets}**.", ephemeral=True)
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
        receipt = "\n".join([f"• {q}x {n}" for n, q in self.view_instance.cart.items()])
        cost_str = ""
        if total_coins > 0: cost_str += f"**** "
        if total_tickets > 0: cost_str += f"**??? {total_tickets} tickets**"
        
        self.view_instance.cart.clear()
        
        embed = discord.Embed(title="?? Checkout Complete!", description=f"You successfully purchased:\n{receipt}\n\n**Total Paid:** {cost_str}", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=self.view_instance)
        
class ClearCartButton(discord.ui.Button):
    def __init__(self, view_instance):
        super().__init__(style=discord.ButtonStyle.danger, label="Clear Cart", emoji="???", row=2)
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
            options.append(discord.SelectOption(label=cat, value=cat, emoji="??"))
        
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
            embed = discord.Embed(title="?? Community Shop", description="Select a category below to browse items.", color=discord.Color.gold())
            await interaction.response.edit_message(embed=embed, view=self)
            return
            
        async with self.bot.db.execute("SELECT name, price, description, currency FROM store WHERE category = ?", (self.current_category,)) as cursor:
            items = await cursor.fetchall()

        embed = discord.Embed(title=f"?? {self.current_category} Shop", description="Select an item from the dropdown to add it to your cart!", color=discord.Color.gold())
        for name, price, description, currency in items:
            cost_str = f"****" if currency == "coins" else f"**??? {price}**"
            embed.add_field(name=f"{name} - {cost_str}", value=description, inline=False)
            
        # Cart Field
        if self.cart:
            cart_str = "\n".join([f"• {q}x {n}" for n, q in self.cart.items()])
            embed.add_field(name="?? Your Cart", value=cart_str, inline=False)
        else:
            embed.add_field(name="?? Your Cart", value="*Cart is empty*", inline=False)

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
