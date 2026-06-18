import discord
from discord.ext import commands, tasks
import random
import time
import datetime


class Crafting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
    await bot.add_cog(Crafting(bot))
