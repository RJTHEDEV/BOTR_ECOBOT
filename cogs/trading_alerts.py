import discord
from discord.ext import commands, tasks
import yfinance as yf

class TradingAlerts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_alerts.start()

    def cog_unload(self):
        self.check_alerts.cancel()

    @commands.hybrid_group(invoke_without_command=True, description="Manage stock price alerts.")
    async def alert(self, ctx):
        await ctx.send("Use `/alert set <ticker> <price> <above/below>` or `/alert list`.")

    @alert.command(name="set", description="Set a price alert for a stock.")
    async def set_alert(self, ctx, ticker: str, price: float, direction: str):
        ticker = ticker.upper()
        direction = direction.lower()
        if direction not in ["above", "below"]:
            await ctx.send("Direction must be `above` or `below`.")
            return

        # Check if valid ticker
        try:
            stock = yf.Ticker(ticker)
            current_price = stock.fast_info['last_price']
        except Exception:
            await ctx.send("Invalid ticker symbol.")
            return

        await self.bot.db.execute("INSERT INTO price_alerts (user_id, ticker, target_price, direction) VALUES (?, ?, ?, ?)", 
                                  (ctx.author.id, ticker, price, direction))
        await self.bot.db.commit()
        await ctx.send(f"✅ Alert set! I will DM you when **{ticker}** goes **{direction}** **${price:,.2f}**. (Current: ${current_price:,.2f})")

    @alert.command(name="list", description="List your active price alerts.")
    async def list_alerts(self, ctx):
        async with self.bot.db.execute("SELECT id, ticker, target_price, direction FROM price_alerts WHERE user_id = ?", (ctx.author.id,)) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await ctx.send("You have no active price alerts.")
            return

        embed = discord.Embed(title="📈 Your Price Alerts", color=discord.Color.blue())
        for a_id, ticker, target, direction in rows:
            embed.add_field(name=f"Alert ID: {a_id}", value=f"**{ticker}** goes **{direction}** **${target:,.2f}**", inline=False)
        await ctx.send(embed=embed)

    @tasks.loop(minutes=5)
    async def check_alerts(self):
        async with self.bot.db.execute("SELECT id, user_id, ticker, target_price, direction FROM price_alerts") as cursor:
            alerts = await cursor.fetchall()

        if not alerts: return

        # Group by ticker to minimize yfinance calls
        tickers = list(set([a[2] for a in alerts]))
        try:
            data = yf.download(tickers, period="1d", progress=False)['Close']
        except Exception as e:
            print(f"Error fetching yfinance data for alerts: {e}")
            return

        for a_id, user_id, ticker, target_price, direction in alerts:
            try:
                # Handle single vs multiple tickers returned by yf
                if len(tickers) == 1:
                    current_price = data.iloc[-1]
                else:
                    current_price = data[ticker].iloc[-1]

                triggered = False
                if direction == "above" and current_price >= target_price:
                    triggered = True
                elif direction == "below" and current_price <= target_price:
                    triggered = True

                if triggered:
                    user = self.bot.get_user(user_id)
                    if user:
                        embed = discord.Embed(title="🚨 PRICE ALERT TRIGGERED 🚨", color=discord.Color.red())
                        embed.add_field(name="Ticker", value=f"**{ticker}**", inline=True)
                        embed.add_field(name="Current Price", value=f"**${current_price:,.2f}**", inline=True)
                        embed.add_field(name="Condition", value=f"Target was {direction} ${target_price:,.2f}", inline=False)
                        try:
                            await user.send(embed=embed)
                        except: pass
                    
                    # Delete triggered alert
                    await self.bot.db.execute("DELETE FROM price_alerts WHERE id = ?", (a_id,))
            except Exception as e:
                pass
        
        await self.bot.db.commit()

    @check_alerts.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(TradingAlerts(bot))
