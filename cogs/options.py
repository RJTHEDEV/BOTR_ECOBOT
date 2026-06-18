import discord
from discord.ext import commands
import yfinance as yf
import datetime
import asyncio
import math

def norm_cdf(x):
    """Cumulative distribution function for the standard normal distribution."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def norm_pdf(x):
    """Probability density function for the standard normal distribution."""
    return math.exp(-0.5 * x**2) / math.sqrt(2 * math.pi)

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
                async with self.bot.db.execute("SELECT id, user_id, ticker, option_type, strike_price FROM options WHERE status = 'active' AND expiration_date < ?", (today,)) as cursor:
                    expired = await cursor.fetchall()
                
                for oid, uid, ticker, otype, strike in expired:
                    await self.bot.db.execute("UPDATE options SET status = 'expired' WHERE id = ?", (oid,))
                    user = self.bot.get_user(uid)
                    if user:
                        try: await user.send(f"📉 Your {ticker} {otype.upper()} option (Strike: ${strike}) has expired OTM.")
                        except: pass
                
                await self.bot.db.commit()
            except Exception as e:
                print(f"Options loop error: {e}")
            
            await asyncio.sleep(3600)

    @commands.hybrid_group(name="options", description="Advanced Options Trading & Calculators")
    async def options(self, ctx):
        await ctx.send("Use `/options buy`, `/options list`, or the calculator commands (`/options calc_bs`, `/options calc_greeks`).")

    @options.command(name="buy", description="Buy a Call or Put option with live market data.")
    async def buy(self, ctx, option_type: str, ticker: str, strike_price: float, expiry_days: int):
        option_type = option_type.lower()
        ticker = ticker.upper()
        
        if option_type not in ['call', 'put']:
            await ctx.send("Option type must be 'call' or 'put'.")
            return
        
        if expiry_days <= 0 or expiry_days > 90:
            await ctx.send("Expiry must be between 1 and 90 days.")
            return

        current_price = 0
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
        except:
            await ctx.send(f"❌ Could not fetch market price for **{ticker}**.")
            return

        if current_price == 0:
            await ctx.send("❌ Price error. Ticker may be delisted or invalid.")
            return

        # Simple Premium Calculation (Intrinsic + Time Value)
        intrinsic = max(0, current_price - strike_price) if option_type == 'call' else max(0, strike_price - current_price)
        time_value = (current_price * 0.005 * expiry_days) # 0.5% premium decay per day
        premium_per_share = max(1, intrinsic + time_value) # Min $1 cost
        total_cost = premium_per_share
        
        embed = discord.Embed(title=f"📝 Options Contract: {ticker}", color=discord.Color.blue())
        embed.add_field(name="Type", value=option_type.upper(), inline=True)
        embed.add_field(name="Strike", value=f"${strike_price:,.2f}", inline=True)
        embed.add_field(name="Current Price", value=f"${current_price:,.2f}", inline=True)
        embed.add_field(name="Expiration", value=f"In {expiry_days} days", inline=True)
        embed.add_field(name="Premium Cost", value=f"**${total_cost:,.2f}**", inline=False)
        
        view = ConfirmOptionView(ctx.author, total_cost)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()
        
        if view.value:
            async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
                row = await cursor.fetchone()
                if not row or row[0] < total_cost:
                    await msg.edit(content="❌ Insufficient funds to cover the premium.", view=None)
                    return

            await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, ctx.author.id))
            expiry_date = (datetime.date.today() + datetime.timedelta(days=expiry_days)).isoformat()
            await self.bot.db.execute("INSERT INTO options (user_id, ticker, option_type, strike_price, expiration_date, premium, contracts) VALUES (?, ?, ?, ?, ?, ?, 1)",
                                      (ctx.author.id, ticker, option_type, strike_price, expiry_date, total_cost))
            await self.bot.db.commit()
            await msg.edit(content=f"✅ **Purchased!** You secured a **{ticker} {option_type.upper()}** (Strike: ${strike_price:,.2f}) for **${total_cost:,.2f}**.", view=None)
        else:
            await msg.edit(content="Cancelled.", view=None)

    @options.command(name="list", description="List your active options portfolio.")
    async def list_options(self, ctx):
        async with self.bot.db.execute("SELECT id, ticker, option_type, strike_price, expiration_date, premium FROM options WHERE user_id = ? AND status = 'active'", (ctx.author.id,)) as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("You do not hold any active options contracts.")
            return
        
        embed = discord.Embed(title="📜 Your Options Portfolio", color=discord.Color.gold())
        for oid, ticker, otype, strike, expiry, prem in rows:
            embed.add_field(name=f"[{oid}] {ticker} {otype.upper()}", value=f"Strike: ${strike:,.2f} | Exp: {expiry} | Cost: ${prem:,.2f}", inline=False)
        await ctx.send(embed=embed)

    @options.command(name="exercise", description="Exercise an In-The-Money option for profit.")
    async def exercise(self, ctx, option_id: int):
        async with self.bot.db.execute("SELECT ticker, option_type, strike_price, contracts FROM options WHERE id = ? AND user_id = ? AND status = 'active'", (option_id, ctx.author.id)) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await ctx.send("Option ID not found or already closed.")
            return
        
        ticker, otype, strike, contracts = row
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            current_price = hist['Close'].iloc[-1]
        except:
            await ctx.send("Could not fetch current market price to exercise.")
            return

        profit = 0
        if otype == 'call' and current_price > strike:
            profit = (current_price - strike) * contracts
        elif otype == 'put' and current_price < strike:
            profit = (strike - current_price) * contracts
        
        if profit <= 0:
            await ctx.send(f"❌ This option is Out-Of-The-Money (Current: ${current_price:,.2f}). Exercising would yield $0 profit.")
            return
        
        await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (profit, ctx.author.id))
        await self.bot.db.execute("UPDATE options SET status = 'exercised' WHERE id = ?", (option_id,))
        await self.bot.db.commit()
        await ctx.send(f"✅ **Exercised ITM!** You earned **${profit:,.2f}** from your {ticker} {otype.upper()} contract.")

    # --- ADVANCED CALCULATORS ---

    @options.command(name="calc_bs", description="Black-Scholes Options Pricing Model")
    async def calc_bs(self, ctx, current_price: float, strike_price: float, days_to_expiry: int, volatility: float = 20.0):
        """Calculates theoretical option premium using Black-Scholes formula."""
        if days_to_expiry <= 0:
            await ctx.send("Days to expiry must be positive.")
            return
            
        S = current_price
        K = strike_price
        T = days_to_expiry / 365.0
        r = 0.05 # Assume 5% risk free rate
        sigma = volatility / 100.0
        
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        call_price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
        put_price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
        
        embed = discord.Embed(title="📈 Black-Scholes Pricing Model", color=discord.Color.dark_teal())
        embed.add_field(name="Spot Price", value=f"${S:.2f}", inline=True)
        embed.add_field(name="Strike Price", value=f"${K:.2f}", inline=True)
        embed.add_field(name="Expiry", value=f"{days_to_expiry} days", inline=True)
        embed.add_field(name="Volatility (IV)", value=f"{volatility}%", inline=True)
        embed.add_field(name="Risk-Free Rate", value="5.0%", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        embed.add_field(name="🟢 Theoretical Call Value", value=f"**${call_price:.2f}**", inline=True)
        embed.add_field(name="🔴 Theoretical Put Value", value=f"**${put_price:.2f}**", inline=True)
        
        await ctx.send(embed=embed)

    @options.command(name="calc_greeks", description="Calculate Option Greeks (Delta, Gamma, Theta)")
    async def calc_greeks(self, ctx, current_price: float, strike_price: float, days_to_expiry: int, volatility: float = 20.0):
        if days_to_expiry <= 0:
            await ctx.send("Days to expiry must be positive.")
            return
            
        S = current_price
        K = strike_price
        T = days_to_expiry / 365.0
        r = 0.05
        sigma = volatility / 100.0
        
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        
        # Delta
        call_delta = norm_cdf(d1)
        put_delta = call_delta - 1.0
        
        # Gamma
        gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
        
        # Theta (simplified annual)
        theta_call = -(S * sigma * norm_pdf(d1)) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * norm_cdf(d1 - sigma * math.sqrt(T))
        theta_put = -(S * sigma * norm_pdf(d1)) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm_cdf(-(d1 - sigma * math.sqrt(T)))
        
        embed = discord.Embed(title="🏛️ Options Greeks Calculator", color=discord.Color.dark_purple())
        embed.add_field(name="Parameters", value=f"Spot: ${S} | Strike: ${K} | Vol: {volatility}% | Expiry: {days_to_expiry}d", inline=False)
        
        embed.add_field(name="Call Delta (Δ)", value=f"{call_delta:.4f}", inline=True)
        embed.add_field(name="Put Delta (Δ)", value=f"{put_delta:.4f}", inline=True)
        embed.add_field(name="Gamma (Γ)", value=f"{gamma:.4f}", inline=True)
        
        embed.add_field(name="Call Theta (Θ)", value=f"{theta_call/365:.4f}/day", inline=True)
        embed.add_field(name="Put Theta (Θ)", value=f"{theta_put/365:.4f}/day", inline=True)
        
        await ctx.send(embed=embed)


class ConfirmOptionView(discord.ui.View):
    def __init__(self, author, cost):
        super().__init__(timeout=30)
        self.author = author
        self.value = None
        self.cost = cost

    @discord.ui.button(label="Confirm Purchase", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        self.value = False
        self.stop()

async def setup(bot):
    await bot.add_cog(Options(bot))
