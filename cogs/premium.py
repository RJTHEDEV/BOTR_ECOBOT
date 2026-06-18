import discord
from discord.ext import commands

class Premium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="premium", invoke_without_command=True, description="Premium options and ticket store.")
    async def premium(self, ctx):
        await self.store(ctx)

    @premium.command(name="store", description="View the premium ticket store.")
    async def store(self, ctx):
        embed = discord.Embed(title="💎 Premium Store: Buy Tickets!", color=discord.Color.gold())
        embed.description = (
            "Support the bot's development and gain exclusive perks by purchasing **Tickets (🎟️)** with Crypto or Fiat!\n\n"
            "Tickets can be used to buy premium items in `/premium perks`, bypass cooldowns, and craft powerful upgrades.\n\n"
            "**Ticket Packages (Crypto/Card):**\n"
            "🎟️ **10 Tickets** - $2.99\n"
            "🎟️ **50 Tickets** - $9.99 (Best Value!)\n"
            "🎟️ **200 Tickets** - $29.99 (Whale Tier)\n\n"
            "👑 **Wall Street VIP Subscription** - $5.00/mo\n"
            "Includes 50 Tickets instantly, +1 Ticket every day you `/daily`, and a custom profile badge!\n\n"
            "*(For Crypto payments, click the store link below. For manual CashApp/PayPal, contact an Admin!)*"
        )
        embed.set_footer(text="Thank you for supporting JJonWallStreet!")
        
        # Add a placeholder button for the future store link
        view = discord.ui.View()
        store_btn = discord.ui.Button(label="Open Web Store (Crypto Supported)", style=discord.ButtonStyle.link, url="https://discord.com/")
        view.add_item(store_btn)
        
        await ctx.send(embed=embed, view=view)

    @premium.command(name="perks", description="Spend your Tickets on Premium Perks!")
    async def perks(self, ctx, perk: str = None):
        if not perk:
            embed = discord.Embed(title="💎 Premium Perks", description="Spend your 🎟️ Tickets here! Use `/premium perks <perk_name>` to buy.", color=discord.Color.purple())
            embed.add_field(name="⚡ Energy Drink", value="**Cost:** 5 Tickets\nInstantly resets your `/work` and `/crime` cooldowns.", inline=False)
            embed.add_field(name="📈 Double XP", value="**Cost:** 10 Tickets\nDoubles all XP gained for the next 2 hours.", inline=False)
            embed.add_field(name="🎰 Casino VIP", value="**Cost:** 50 Tickets\nPermanently grants you the Casino VIP status, giving you better odds on all gambling games.", inline=False)
            embed.add_field(name="💰 Whale Exchange", value="**Cost:** 10 Tickets\nInstantly adds $50,000 to your bank balance.", inline=False)
            await ctx.send(embed=embed)
            return

        perk = perk.lower()
        
        async with self.bot.db.execute("SELECT tickets FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            tickets = row[0] if row else 0

        cost = 0
        if perk == "energy drink":
            cost = 5
        elif perk == "double xp":
            cost = 10
        elif perk == "casino vip":
            cost = 50
        elif perk == "whale exchange":
            cost = 10
        else:
            await ctx.send("Invalid perk. Use `/premium perks` to see the list.")
            return

        if tickets < cost:
            await ctx.send(f"You don't have enough tickets. You need {cost} 🎟️. Buy more with `/premium store`.")
            return

        # Deduct tickets
        await self.bot.db.execute("UPDATE users SET tickets = tickets - ? WHERE user_id = ?", (cost, ctx.author.id))

        # Apply Perk
        if perk == "energy drink":
            await self.bot.db.execute("UPDATE users SET last_work = NULL, last_crime = NULL WHERE user_id = ?", (ctx.author.id,))
            await ctx.send("⚡ You drank an Energy Drink! Your `/work` and `/crime` cooldowns have been reset.")
        
        elif perk == "double xp":
            import datetime
            expiry = (datetime.datetime.now() + datetime.timedelta(hours=2)).isoformat()
            await self.bot.db.execute("UPDATE users SET xp_boost_expiry = ? WHERE user_id = ?", (expiry, ctx.author.id))
            await ctx.send("📈 Double XP activated! Enjoy 2x XP for the next 2 hours.")
            
        elif perk == "casino vip":
            await self.bot.db.execute("UPDATE users SET casino_vip = 1 WHERE user_id = ?", (ctx.author.id,))
            await ctx.send("🎰 You are now a Casino VIP! Enjoy better odds at the casino.")
            
        elif perk == "whale exchange":
            await self.bot.db.execute("UPDATE users SET bank = bank + 50000 WHERE user_id = ?", (ctx.author.id,))
            await ctx.send("💰 You exchanged 10 Tickets for $50,000! The funds have been deposited into your bank.")

        await self.bot.db.commit()

    @premium.command(name="grant_tickets", description="Admin: Grant tickets to a user after a manual purchase.")
    @commands.has_permissions(administrator=True)
    async def grant_tickets(self, ctx, user: discord.Member, amount: int, reason: str = "Premium Purchase"):
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.", ephemeral=True)
            return
            
        async with self.bot.db.execute("SELECT tickets FROM users WHERE user_id = ?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await self.bot.db.execute("INSERT INTO users (user_id, balance, bank, tickets) VALUES (?, 0, 0, ?)", (user.id, amount))
            else:
                await self.bot.db.execute("UPDATE users SET tickets = tickets + ? WHERE user_id = ?", (amount, user.id))
                
        await self.bot.db.commit()
        
        embed = discord.Embed(title="🎉 Premium Purchase Successful!", color=discord.Color.green())
        embed.description = f"Successfully granted **{amount} 🎟️ Tickets** to {user.mention}!\n*Reason: {reason}*"
        await ctx.send(embed=embed)
        
        try:
            await user.send(f"Thank you for your purchase! **{amount} 🎟️ Tickets** have been added to your account.")
        except: pass

async def setup(bot):
    await bot.add_cog(Premium(bot))
