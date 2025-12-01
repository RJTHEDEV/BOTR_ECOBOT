import discord
from discord.ext import commands
import yfinance as yf
import matplotlib.pyplot as plt
import io
import pandas as pd
import mplfinance as mpf
import aiohttp
import datetime

class Market(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(aliases=['price'], description="Get real-time price for a ticker.")
    async def p(self, ctx, ticker: str):
        ticker = ticker.upper()
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # yfinance info can be flaky, try fast_info or history if info fails
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            if not current_price:
                 # Fallback to history
                hist = stock.history(period="1d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                else:
                    await ctx.send(f"Could not find data for {ticker}.")
                    return

            prev_close = info.get('previousClose') or current_price # Avoid div by zero
            change = current_price - prev_close
            pct_change = (change / prev_close) * 100
            
            color = discord.Color.green() if change >= 0 else discord.Color.red()
            arrow = "🔼" if change >= 0 else "🔽"
            
            embed = discord.Embed(title=f"{ticker} Price", color=color)
            embed.add_field(name="Price", value=f"${current_price:.2f}", inline=True)
            embed.add_field(name="Change", value=f"{arrow} {change:.2f} ({pct_change:.2f}%)", inline=True)
            
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error fetching data for {ticker}: {e}")

    @commands.hybrid_command(description="View a candlestick chart.")
    async def chart(self, ctx, ticker: str, timeframe: str = "1mo"):
        """
        View a chart for a ticker.
        Timeframes: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max, ytd
        """
        ticker = ticker.upper()
        valid_timeframes = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max", "ytd"]
        
        if timeframe not in valid_timeframes:
            await ctx.send(f"Invalid timeframe. Use: {', '.join(valid_timeframes)}")
            return

        msg = await ctx.send(f"Generating {timeframe} chart for {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            # Interval selection based on timeframe
            interval = "1d"
            if timeframe in ["1d", "5d"]: interval = "15m"
            elif timeframe in ["1mo", "3mo"]: interval = "1d"
            elif timeframe in ["6mo", "1y"]: interval = "1wk"
            else: interval = "1mo"

            hist = stock.history(period=timeframe, interval=interval)
            
            if hist.empty:
                await msg.edit(content=f"No data found for {ticker}.")
                return

            # Create buffer
            buf = io.BytesIO()
            
            # Plot using mplfinance
            mpf.plot(hist, type='candle', style='charles', 
                     title=f"{ticker} - {timeframe}",
                     ylabel='Price',
                     volume=True,
                     savefig=dict(fname=buf, dpi=100, bbox_inches='tight'))
            
            buf.seek(0)
            
            file = discord.File(buf, filename=f"{ticker}_{timeframe}.png")
            await msg.delete()
            await ctx.send(file=file)
            
        except Exception as e:
            await msg.edit(content=f"Error generating chart: {e}")

    @commands.hybrid_group(invoke_without_command=True, description="Manage your watchlist.")
    async def wl(self, ctx):
        async with self.bot.db.execute("SELECT ticker FROM watchlist WHERE user_id = ?", (ctx.author.id,)) as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("Your watchlist is empty. Use `!wl add <ticker>`.")
            return
            
        tickers = [row[0] for row in rows]
        
        # Fetch data for all tickers (simplified for speed)
        embed = discord.Embed(title=f"{ctx.author.name}'s Watchlist", color=discord.Color.blue())
        
        description = ""
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                # Just get fast price
                hist = stock.history(period="1d")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
                    description += f"**{ticker}**: ${price:.2f}\n"
                else:
                    description += f"**{ticker}**: N/A\n"
            except:
                description += f"**{ticker}**: Error\n"
        
        embed.description = description
        await ctx.send(embed=embed)

    @wl.command(description="Add a ticker to your watchlist.")
    async def add(self, ctx, ticker: str):
        ticker = ticker.upper()
        try:
            await self.bot.db.execute("INSERT INTO watchlist (user_id, ticker) VALUES (?, ?)", (ctx.author.id, ticker))
            await self.bot.db.commit()
            await ctx.send(f"Added {ticker} to watchlist.")
        except:
            await ctx.send(f"{ticker} is already in your watchlist.")

    @wl.command(description="Remove a ticker from your watchlist.")
    async def remove(self, ctx, ticker: str):
        ticker = ticker.upper()
        await self.bot.db.execute("DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (ctx.author.id, ticker))
        await self.bot.db.commit()
        await ctx.send(f"Removed {ticker} from watchlist.")

    @commands.hybrid_command(description="View today's economic calendar (ForexFactory).")
    async def calendar(self, ctx):
        await ctx.defer()
        
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        await ctx.send("❌ Failed to fetch calendar data.")
                        return
                    data = await response.json()
            
            # Filter for today
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            events = []
            
            for event in data:
                # Event date format is usually ISO-like but let's check
                # Sample: "date": "2025-12-01T09:00:00-05:00"
                if event.get('date', '').startswith(today):
                    events.append(event)
            
            if not events:
                await ctx.send(f"No economic events found for today ({today}).")
                return

            # Sort by time
            events.sort(key=lambda x: x.get('date'))

            embed = discord.Embed(title=f"📅 Economic Calendar - {today}", color=discord.Color.blue())
            embed.set_footer(text="Source: ForexFactory")

            for event in events:
                title = event.get('title', 'Unknown Event')
                country = event.get('country', '??')
                impact = event.get('impact', 'Low')
                forecast = event.get('forecast', '-')
                previous = event.get('previous', '-')
                
                # Parse time
                event_date = datetime.datetime.fromisoformat(event.get('date'))
                time_str = event_date.strftime("%H:%M")

                # Impact Emoji
                impact_emoji = "⚪"
                if impact == "High": impact_emoji = "🔴"
                elif impact == "Medium": impact_emoji = "🟠"
                elif impact == "Low": impact_emoji = "🟡"

                embed.add_field(
                    name=f"{impact_emoji} {time_str} {country} - {title}",
                    value=f"**Forecast:** {forecast} | **Prev:** {previous}",
                    inline=False
                )
            
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error fetching calendar: {e}")

async def setup(bot):
    await bot.add_cog(Market(bot))
