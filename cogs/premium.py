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
            "Support the bot's development and gain exclusive perks by purchasing **Tickets (🎟️)**!\n\n"
            "Tickets can be used to buy premium items in `/store shop`, bypass cooldowns, and craft powerful upgrades.\n\n"
            "**Ticket Packages:**\n"
            "🎟️ **10 Tickets** - $2.99\n"
            "🎟️ **50 Tickets** - $9.99 (Best Value!)\n"
            "🎟️ **200 Tickets** - $29.99 (Whale Tier)\n\n"
            "👑 **Wall Street VIP Subscription** - $5.00/mo\n"
            "Includes 50 Tickets instantly, +1 Ticket every day you `/daily`, and a custom profile badge!\n\n"
            "*(Currently setting up payment gateway. For now, contact an Admin to purchase via PayPal/CashApp!)*"
        )
        embed.set_footer(text="Thank you for supporting JJonWallStreet!")
        
        # Add a placeholder button for the future store link
        view = discord.ui.View()
        store_btn = discord.ui.Button(label="Open Web Store", style=discord.ButtonStyle.link, url="https://discord.com/")
        view.add_item(store_btn)
        
        await ctx.send(embed=embed, view=view)

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
