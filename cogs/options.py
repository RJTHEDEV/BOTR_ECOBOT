import discord
from discord.ext import commands, tasks
import yfinance as yf
import datetime
import asyncio

class Options(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_expiry_task = self.bot.loop.create_task(self.check_options_expiry())

    def cog_unload(self):
        self.check_expiry_task.cancel()

    async def check_options_expiry(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                today = datetime.date.today().isoformat()
                # Find active options that expired yesterday or today
                async with self.bot.db.execute("SELECT id, user_id, ticker, option_type, strike_price FROM options WHERE status = 'active' AND expiration_date < ?", (today,)) as cursor:
                    expired = await cursor.fetchall()
                
                for oid, uid, ticker, otype, strike in expired:
                    # Mark as expired
                    await self.bot.db.execute("UPDATE options SET status = 'expired' WHERE id = ?", (oid,))
                    
                    user = self.bot.get_user(uid)
                    if user:
                        try: await user.send(f"📉 Your {ticker} {otype.upper()} option (Strike: ${strike}) has expired.")
                        except: pass
                
                await self.bot.db.commit()

            except Exception as e:
                print(f"Options loop error: {e}")
            
            await asyncio.sleep(3600) # Check every hour

    @commands.hybrid_group(name="option", description="Trade stock options.")
    async def option(self, ctx):
        await ctx.send("Use `/option buy` or `/option list`.")

    @option.command(description="Buy a Call or Put option.")
    async def buy(self, ctx, option_type: str, ticker: str, strike_price: float, expiry_days: int):
        option_type = option_type.lower()
        ticker = ticker.upper()
        
        if option_type not in ['call', 'put']:
            await ctx.send("Option type must be 'call' or 'put'.")
            return
        
        if expiry_days <= 0 or expiry_days > 30:
            await ctx.send("Expiry must be between 1 and 30 days.")
            return

        # Fetch current price
        current_price = 0
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
        except:
            await ctx.send(f"Could not fetch price for {ticker}.")
            return

        if current_price == 0:
            await ctx.send("Price error.")
            return

        # Calculate Premium (Simplified)
        # Premium = Intrinsic Value + Time Value
        # Intrinsic Call = Max(0, Current - Strike)
        # Intrinsic Put = Max(0, Strike - Current)
        # Time Value = (Current * 0.02 * Days) (2% volatility per day approximation)
        
        intrinsic = 0
        if option_type == 'call':
            intrinsic = max(0, current_price - strike_price)
        else:
            intrinsic = max(0, strike_price - current_price)
            
        time_value = (current_price * 0.01 * expiry_days) # 1% per day cost
        premium_per_share = intrinsic + time_value
        
        # Minimum premium
        if premium_per_share < 1: premium_per_share = 1
        
        # 1 Contract = 1 Share (Simplified for this bot economy)
        total_cost = premium_per_share
        
        # Confirm
        embed = discord.Embed(title=f"📝 Confirm Option Buy", description=f"**Type:** {option_type.upper()}\n**Ticker:** {ticker}\n**Strike:** ${strike_price}\n**Current:** ${current_price:.2f}\n**Expiry:** {expiry_days} days\n\n**Premium (Cost):** ${total_cost:.2f}", color=discord.Color.blue())
        view = ConfirmOptionView(ctx.author, total_cost)
        msg = await ctx.send(embed=embed, view=view)
        
        await view.wait()
        
        if view.value is None:
            await msg.edit(content="Timed out.", view=None)
        elif view.value:
            # Check balance
            async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
                row = await cursor.fetchone()
                if not row or row[0] < total_cost:
                    await msg.edit(content="❌ Insufficient funds.", view=None)
                    return

            # Deduct funds
            await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, ctx.author.id))
            
            # Create Option
            expiry_date = (datetime.date.today() + datetime.timedelta(days=expiry_days)).isoformat()
            await self.bot.db.execute("INSERT INTO options (user_id, ticker, option_type, strike_price, expiration_date, premium, contracts) VALUES (?, ?, ?, ?, ?, ?, 1)",
                                      (ctx.author.id, ticker, option_type, strike_price, expiry_date, total_cost))
            await self.bot.db.commit()
            
            await msg.edit(content=f"✅ **Option Purchased!** You bought a {ticker} {option_type.upper()} Strike ${strike_price} for ${total_cost:.2f}.", view=None)
        else:
            await msg.edit(content="Cancelled.", view=None)

    @option.command(name="list", description="List your active options.")
    async def list_options(self, ctx):
        async with self.bot.db.execute("SELECT id, ticker, option_type, strike_price, expiration_date, premium FROM options WHERE user_id = ? AND status = 'active'", (ctx.author.id,)) as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("No active options.")
            return
        
        embed = discord.Embed(title="📜 Active Options", color=discord.Color.gold())
        for oid, ticker, otype, strike, expiry, prem in rows:
            embed.add_field(name=f"ID: {oid} | {ticker} {otype.upper()}", value=f"Strike: ${strike} | Exp: {expiry} | Cost: ${prem:.2f}", inline=False)
        
        await ctx.send(embed=embed)

    @option.command(description="Exercise an option.")
    async def exercise(self, ctx, option_id: int):
        async with self.bot.db.execute("SELECT ticker, option_type, strike_price, contracts FROM options WHERE id = ? AND user_id = ? AND status = 'active'", (option_id, ctx.author.id)) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await ctx.send("Option not found or already closed.")
            return
        
        ticker, otype, strike, contracts = row
        
        # Fetch current price
        current_price = 0
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
        except:
            await ctx.send("Could not fetch current price.")
            return

        profit = 0
        if otype == 'call':
            # Profit = (Current - Strike) * Contracts
            if current_price > strike:
                profit = (current_price - strike) * contracts
        else:
            # Profit = (Strike - Current) * Contracts
            if current_price < strike:
                profit = (strike - current_price) * contracts
        
        if profit <= 0:
            await ctx.send(f"❌ This option is out of the money (Current: ${current_price:.2f}). Exercising would result in $0 profit.")
            return
        
        # Payout
        await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (profit, ctx.author.id))
        await self.bot.db.execute("UPDATE options SET status = 'exercised' WHERE id = ?", (option_id,))
        await self.bot.db.commit()
        
        await ctx.send(f"✅ **Option Exercised!** You earned **${profit:.2f}** from your {ticker} {otype.upper()}.")

class ConfirmOptionView(discord.ui.View):
    def __init__(self, author, cost):
        super().__init__(timeout=30)
        self.author = author
        self.value = None
        self.cost = cost

    @discord.ui.button(label="Confirm Buy", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        self.value = False
        self.stop()

async def setup(bot):
    await bot.add_cog(Options(bot))
