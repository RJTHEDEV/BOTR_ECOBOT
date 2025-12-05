import discord
from discord.ext import commands
import discord
from discord.ext import commands
import yfinance as yf
import asyncio
import matplotlib.pyplot as plt
import io
import pandas as pd
import mplfinance as mpf
import aiohttp
import datetime

class Market(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    # --- Limit Orders ---
    @commands.hybrid_group(name="limit", description="Manage limit orders.")
    async def limit(self, ctx):
        await ctx.send("Use `/limit buy` or `/limit sell`.")

    @limit.command(description="Set a limit buy order.")
    async def buy(self, ctx, ticker: str, price: float, quantity: int):
        ticker = ticker.upper()
        if price <= 0 or quantity <= 0:
            await ctx.send("Price and quantity must be positive.")
            return

        # Check balance
        total_cost = price * quantity
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < total_cost:
                await ctx.send(f"❌ Insufficient funds. You need **${total_cost:.2f}**.")
                return

        # Reserve funds? 
        # For simplicity, we won't reserve funds now, but check at execution time.
        # OR we deduct now and refund if cancelled. Deducting now is safer.
        await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, ctx.author.id))
        
        created_at = datetime.datetime.now().isoformat()
        await self.bot.db.execute("INSERT INTO limit_orders (user_id, symbol, order_type, target_price, quantity, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                  (ctx.author.id, ticker, 'buy_limit', price, quantity, created_at))
        await self.bot.db.commit()
        
        await ctx.send(f"✅ Limit Buy Order set for **{quantity}x {ticker}** at **${price:.2f}**. Funds reserved.")

    @limit.command(description="Set a limit sell order.")
    async def sell(self, ctx, ticker: str, price: float, quantity: int):
        ticker = ticker.upper()
        if price <= 0 or quantity <= 0:
            await ctx.send("Price and quantity must be positive.")
            return

        # Check shares
        async with self.bot.db.execute("SELECT shares FROM portfolio WHERE user_id = ? AND ticker = ?", (ctx.author.id, ticker)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < quantity:
                await ctx.send(f"❌ You don't have enough shares of {ticker}.")
                return

        # Reserve shares
        await self.bot.db.execute("UPDATE portfolio SET shares = shares - ? WHERE user_id = ? AND ticker = ?", (quantity, ctx.author.id, ticker))
        
        created_at = datetime.datetime.now().isoformat()
        await self.bot.db.execute("INSERT INTO limit_orders (user_id, symbol, order_type, target_price, quantity, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                  (ctx.author.id, ticker, 'sell_limit', price, quantity, created_at))
        await self.bot.db.commit()
        
        await ctx.send(f"✅ Limit Sell Order set for **{quantity}x {ticker}** at **${price:.2f}**. Shares reserved.")

    @commands.hybrid_command(description="View your active orders.")
    async def orders(self, ctx):
        async with self.bot.db.execute("SELECT order_id, symbol, order_type, target_price, quantity FROM limit_orders WHERE user_id = ?", (ctx.author.id,)) as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("No active orders.")
            return
        
        embed = discord.Embed(title="📋 Active Orders", color=discord.Color.blue())
        for oid, symbol, otype, price, qty in rows:
            type_str = "Buy Limit" if otype == 'buy_limit' else "Sell Limit"
            embed.add_field(name=f"ID: {oid} | {symbol}", value=f"{type_str}: {qty} shares @ ${price:.2f}", inline=False)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Cancel an order.")
    async def cancel(self, ctx, order_id: int):
        async with self.bot.db.execute("SELECT user_id, symbol, order_type, target_price, quantity FROM limit_orders WHERE order_id = ?", (order_id,)) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await ctx.send("Order not found.")
            return
        
        if row[0] != ctx.author.id:
            await ctx.send("This is not your order.")
            return
        
        user_id, symbol, otype, price, qty = row
        
        # Refund
        if otype == 'buy_limit':
            refund = price * qty
            await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (refund, user_id))
        else:
            # Return shares
            # Check if portfolio entry exists (it might be empty if they sold all reserved shares, but here we reserved them by deducting)
            # Actually we deducted shares, so we add them back.
            async with self.bot.db.execute("SELECT 1 FROM portfolio WHERE user_id = ? AND ticker = ?", (user_id, symbol)) as cursor:
                if await cursor.fetchone():
                    await self.bot.db.execute("UPDATE portfolio SET shares = shares + ? WHERE user_id = ? AND ticker = ?", (qty, user_id, symbol))
                else:
                    # Should exist if we just deducted, unless we delete rows with 0 shares. 
                    # If we delete rows with 0 shares, we need to re-insert.
                    # For now assuming we keep 0 share rows or insert new.
                    await self.bot.db.execute("INSERT INTO portfolio (user_id, ticker, shares, avg_price, avg_buy_price) VALUES (?, ?, ?, 0, 0)", (user_id, symbol, qty))

        await self.bot.db.execute("DELETE FROM limit_orders WHERE order_id = ?", (order_id,))
        await self.bot.db.commit()
        await ctx.send(f"✅ Order {order_id} cancelled and refunded.")

    # --- Background Task for Limit Orders ---
    async def check_alerts_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                # 1. Check Price Alerts (Existing Logic)
                async with self.bot.db.execute("SELECT id, user_id, ticker, target_price, condition FROM price_alerts WHERE triggered = 0") as cursor:
                    alerts = await cursor.fetchall()
                
                # 2. Check Limit Orders
                async with self.bot.db.execute("SELECT order_id, user_id, symbol, order_type, target_price, quantity FROM limit_orders") as cursor:
                    orders = await cursor.fetchall()

                if not alerts and not orders:
                    await asyncio.sleep(60)
                    continue

                # Collect all tickers
                alert_tickers = [a[2] for a in alerts]
                order_tickers = [o[2] for o in orders]
                all_tickers = list(set(alert_tickers + order_tickers))
                
                prices = {}
                # Fetch prices
                for ticker in all_tickers:
                    try:
                        if ticker.startswith("CRYPTO:"):
                             coin = ticker.split(":")[1]
                             url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd"
                             async with aiohttp.ClientSession() as session:
                                 async with session.get(url) as resp:
                                     data = await resp.json()
                                     if coin in data:
                                         prices[ticker] = data[coin]['usd']
                        else:
                            stock = yf.Ticker(ticker)
                            hist = stock.history(period="1d")
                            if not hist.empty:
                                prices[ticker] = hist['Close'].iloc[-1]
                    except:
                        pass

                # Process Alerts
                for alert_id, user_id, ticker, target, condition in alerts:
                    if ticker not in prices: continue
                    current = prices[ticker]
                    triggered = False
                    if condition == 'above' and current >= target: triggered = True
                    elif condition == 'below' and current <= target: triggered = True
                    
                    if triggered:
                        user = self.bot.get_user(user_id)
                        if user:
                            try: await user.send(f"🚨 **Price Alert!** {ticker} hit **${current:.2f}** (Target: {condition} ${target:.2f})")
                            except: pass
                        await self.bot.db.execute("UPDATE price_alerts SET triggered = 1 WHERE id = ?", (alert_id,))

                # Process Limit Orders
                for oid, user_id, symbol, otype, target, qty in orders:
                    if symbol not in prices: continue
                    current = prices[symbol]
                    executed = False
                    
                    if otype == 'buy_limit' and current <= target:
                        # Execute Buy
                        # Funds already deducted. Just add shares.
                        # Update Avg Buy Price
                        async with self.bot.db.execute("SELECT shares, avg_buy_price FROM portfolio WHERE user_id = ? AND ticker = ?", (user_id, symbol)) as cursor:
                            row = await cursor.fetchone()
                            if row:
                                old_shares, old_avg = row
                                new_shares = old_shares + qty
                                # Weighted average
                                new_avg = ((old_shares * old_avg) + (qty * current)) / new_shares
                                await self.bot.db.execute("UPDATE portfolio SET shares = ?, avg_buy_price = ? WHERE user_id = ? AND ticker = ?", (new_shares, new_avg, user_id, symbol))
                            else:
                                await self.bot.db.execute("INSERT INTO portfolio (user_id, ticker, shares, avg_price, avg_buy_price) VALUES (?, ?, ?, ?, ?)", (user_id, symbol, qty, current, current))
                        
                        executed = True
                        msg = f"✅ **Limit Buy Executed!** Bought {qty}x {symbol} at ${current:.2f} (Target: ${target:.2f})"

                    elif otype == 'sell_limit' and current >= target:
                        # Execute Sell
                        # Shares already deducted. Just add funds.
                        total_val = current * qty
                        await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_val, user_id))
                        executed = True
                        msg = f"✅ **Limit Sell Executed!** Sold {qty}x {symbol} at ${current:.2f} (Target: ${target:.2f}). Earned ${total_val:.2f}"

                    if executed:
                        await self.bot.db.execute("DELETE FROM limit_orders WHERE order_id = ?", (oid,))
                        user = self.bot.get_user(user_id)
                        if user:
                            try: await user.send(msg)
                            except: pass

                await self.bot.db.commit()

            except Exception as e:
                print(f"Loop error: {e}")
            
            await asyncio.sleep(60)

    @commands.hybrid_command(description="View your portfolio performance.")
    async def portfolio(self, ctx):
        async with self.bot.db.execute("SELECT ticker, shares, avg_buy_price FROM portfolio WHERE user_id = ?", (ctx.author.id,)) as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("Your portfolio is empty.")
            return

        embed = discord.Embed(title=f"📈 {ctx.author.name}'s Portfolio", color=discord.Color.blue())
        total_value = 0
        total_gain_loss = 0
        
        description = ""
        
        for ticker, shares, avg_buy in rows:
            if shares <= 0: continue
            
            # Fetch current price
            current_price = 0
            try:
                if ticker.startswith("CRYPTO:"):
                     coin = ticker.split(":")[1]
                     url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd"
                     async with aiohttp.ClientSession() as session:
                         async with session.get(url) as resp:
                             data = await resp.json()
                             if coin in data: current_price = data[coin]['usd']
                else:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="1d")
                    if not hist.empty: current_price = hist['Close'].iloc[-1]
            except:
                pass
            
            if current_price == 0:
                description += f"**{ticker}**: {shares} shares (Price Error)\n"
                continue

            value = current_price * shares
            cost_basis = avg_buy * shares
            gain_loss = value - cost_basis
            pct_change = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0
            
            total_value += value
            total_gain_loss += gain_loss
            
            emoji = "🟢" if gain_loss >= 0 else "🔴"
            description += f"**{ticker}**: {shares} shares @ ${current_price:.2f}\n"
            description += f"Avg Buy: ${avg_buy:.2f} | {emoji} ${gain_loss:+.2f} ({pct_change:+.2f}%)\n\n"

        embed.description = description
        
        total_pct = (total_gain_loss / (total_value - total_gain_loss) * 100) if (total_value - total_gain_loss) > 0 else 0
        embed.add_field(name="Total Value", value=f"${total_value:,.2f}", inline=True)
        embed.add_field(name="Total Gain/Loss", value=f"${total_gain_loss:+,.2f} ({total_pct:+.2f}%)", inline=True)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="View top market movers.")
    async def movers(self, ctx):
        # Using a hardcoded list of popular stocks for now as yfinance movers is unreliable
        popular = ["AAPL", "TSLA", "NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "GME"]
        
        movers_data = []
        msg = await ctx.send("Fetching market movers...")
        
        for ticker in popular:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="1d")
                if not hist.empty:
                    current = hist['Close'].iloc[-1]
                    open_price = hist['Open'].iloc[0]
                    change = current - open_price
                    pct = (change / open_price) * 100
                    movers_data.append((ticker, current, pct))
            except:
                pass
        
        # Sort by absolute pct change
        movers_data.sort(key=lambda x: abs(x[2]), reverse=True)
        
        embed = discord.Embed(title="🚀 Top Market Movers (Watchlist)", color=discord.Color.gold())
        for ticker, price, pct in movers_data[:5]:
            emoji = "🟢" if pct >= 0 else "🔴"
            embed.add_field(name=f"{emoji} {ticker}", value=f"${price:.2f} ({pct:+.2f}%)", inline=False)
            
        await msg.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(Market(bot))

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

    @commands.hybrid_command(description="Get real-time crypto price (CoinGecko).")
    async def crypto(self, ctx, coin: str):
        coin = coin.lower()
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd,eur,gbp&include_24hr_change=true"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await ctx.send("❌ Error fetching data.")
                    return
                
                data = await response.json()
                if coin not in data:
                    await ctx.send(f"❌ Coin `{coin}` not found. Try the full name (e.g., `bitcoin`, `ethereum`).")
                    return
                
                price_usd = data[coin]['usd']
                change_24h = data[coin].get('usd_24h_change', 0)
                
                color = discord.Color.green() if change_24h >= 0 else discord.Color.red()
                arrow = "🔼" if change_24h >= 0 else "🔽"
                
                embed = discord.Embed(title=f"{coin.title()} Price", color=color)
                embed.add_field(name="USD", value=f"${price_usd:,.2f}", inline=True)
                embed.add_field(name="24h Change", value=f"{arrow} {change_24h:.2f}%", inline=True)
                embed.set_footer(text="Source: CoinGecko")
                
                await ctx.send(embed=embed)

    @commands.hybrid_group(name="pricealert", aliases=["pa"], invoke_without_command=True, description="Manage price alerts.")
    async def pricealert(self, ctx):
        await ctx.send("Use `/pricealert set <ticker> <price>`, `/pricealert list`, or `/pricealert remove <id>`.")

    @pricealert.command(description="Set a price alert.")
    async def set(self, ctx, ticker: str, price: float):
        ticker = ticker.upper()
        # Determine condition (above or below current price)
        # We need current price first
        current_price = 0
        is_crypto = False
        
        # Check if crypto (simple heuristic: if ticker is a common name or user specifies)
        # For now, let's assume stocks unless prefixed with CRYPTO:
        # Actually, let's just support stocks for now in alerts to keep it simple, or try both.
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
            else:
                # Try crypto
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ticker.lower()}&vs_currencies=usd") as resp:
                        data = await resp.json()
                        if ticker.lower() in data:
                            current_price = data[ticker.lower()]['usd']
                            is_crypto = True
                            ticker = f"CRYPTO:{ticker.lower()}"
        except:
            pass
        
        if current_price == 0:
            await ctx.send(f"❌ Could not verify current price for {ticker}. Alert not set.")
            return

        condition = 'above' if price > current_price else 'below'
        
        await self.bot.db.execute("INSERT INTO price_alerts (user_id, ticker, target_price, condition) VALUES (?, ?, ?, ?)", 
                                  (ctx.author.id, ticker, price, condition))
        await self.bot.db.commit()
        
        await ctx.send(f"✅ Alert set for **{ticker}** when price goes **{condition} ${price:.2f}** (Current: ${current_price:.2f}).")

    @pricealert.command(name="list", description="List your active alerts.")
    async def list_alerts(self, ctx):
        async with self.bot.db.execute("SELECT id, ticker, target_price, condition FROM price_alerts WHERE user_id = ? AND triggered = 0", (ctx.author.id,)) as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("No active alerts.")
            return
        
        embed = discord.Embed(title="🔔 Your Price Alerts", color=discord.Color.gold())
        for aid, ticker, target, cond in rows:
            embed.add_field(name=f"ID: {aid} | {ticker}", value=f"{cond.title()} ${target:.2f}", inline=False)
        
        await ctx.send(embed=embed)

    @pricealert.command(description="Remove an alert by ID.")
    async def remove(self, ctx, alert_id: int):
        await self.bot.db.execute("DELETE FROM price_alerts WHERE id = ? AND user_id = ?", (alert_id, ctx.author.id))
        await self.bot.db.commit()
        await ctx.send(f"🗑️ Alert {alert_id} removed.")

    @commands.hybrid_command(name="marketnews", aliases=["mnews"], description="Get news and sentiment for a ticker.")
    async def marketnews(self, ctx, ticker: str):
        ticker = ticker.upper()
        msg = await ctx.send(f"📰 Fetching news for {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            news = stock.news
            
            if not news:
                await msg.edit(content=f"No news found for {ticker}.")
                return
            
            embed = discord.Embed(title=f"📰 News for {ticker}", color=discord.Color.blue())
            
            # Simple Sentiment Analysis
            bullish_words = ["surge", "jump", "record", "beat", "buy", "profit", "growth", "high", "soar"]
            bearish_words = ["plunge", "drop", "miss", "fail", "sell", "loss", "decline", "low", "crash"]
            
            for item in news[:3]: # Top 3
                # Handle yfinance structure change (nested in 'content')
                if 'content' in item:
                    item = item['content']

                title = item.get('title', '')
                
                # Try to find link
                link = item.get('link', '')
                if not link:
                    if 'canonicalUrl' in item:
                        link = item['canonicalUrl'].get('url', '')
                    elif 'clickThroughUrl' in item:
                        link = item['clickThroughUrl'].get('url', '')
                
                # publisher = item.get('publisher', 'Unknown')
                
                score = 0
                lower_title = title.lower()
                for w in bullish_words: 
                    if w in lower_title: score += 1
                for w in bearish_words: 
                    if w in lower_title: score -= 1
                
                sentiment = "Neutral 😐"
                if score > 0: sentiment = "Bullish 🟢"
                elif score < 0: sentiment = "Bearish 🔴"
                
                embed.add_field(name=f"{sentiment} {title}", value=f"[Read More]({link})", inline=False)
            
            await msg.edit(content=None, embed=embed)
            
        except Exception as e:
            await msg.edit(content=f"Error fetching news: {e}")

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
