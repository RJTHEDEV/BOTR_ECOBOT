import discord
from discord.ext import commands
import yfinance as yf

class PaperTrading(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_price(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                return hist['Close'].iloc[-1]
        except:
            pass
        return None

    @commands.hybrid_command(description="Buy stocks (simulated).")
    async def tbuy(self, ctx, ticker: str, shares: int):
        if shares <= 0:
            await ctx.send("Shares must be positive.")
            return
            
        ticker = ticker.upper()
        price = await self.get_price(ticker)
        
        if not price:
            await ctx.send(f"Could not get price for {ticker}.")
            return
            
        total_cost = price * shares
        
        # Check balance
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row or row[0] < total_cost:
            await ctx.send(f"Insufficient funds. Cost: ${total_cost:.2f}, Balance: ${row[0] if row else 0}")
            return
            
        # Deduct balance
        await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, ctx.author.id))
        await self.bot.get_cog("Economy").log_transaction(ctx.author.id, "paper_trading", -total_cost, f"Bought {shares} {ticker} @ ${price:.2f}")
        
        # Update portfolio
        async with self.bot.db.execute("SELECT avg_price, shares FROM portfolio WHERE user_id = ? AND ticker = ?", (ctx.author.id, ticker)) as cursor:
            row = await cursor.fetchone()
            
        if row:
            current_avg, current_shares = row
            new_shares = current_shares + shares
            new_avg = ((current_avg * current_shares) + total_cost) / new_shares
            await self.bot.db.execute("UPDATE portfolio SET avg_price = ?, shares = ? WHERE user_id = ? AND ticker = ?", (new_avg, new_shares, ctx.author.id, ticker))
        else:
            await self.bot.db.execute("INSERT INTO portfolio (user_id, ticker, avg_price, shares) VALUES (?, ?, ?, ?)", (ctx.author.id, ticker, price, shares))
            
        await self.bot.db.commit()
        await ctx.send(f"Bought {shares} shares of {ticker} at ${price:.2f} (Total: ${total_cost:.2f}).")

    @commands.hybrid_command(description="Sell stocks (simulated).")
    async def tsell(self, ctx, ticker: str, shares: int):
        if shares <= 0:
            await ctx.send("Shares must be positive.")
            return
            
        ticker = ticker.upper()
        
        # Check ownership
        async with self.bot.db.execute("SELECT avg_price, shares FROM portfolio WHERE user_id = ? AND ticker = ?", (ctx.author.id, ticker)) as cursor:
            row = await cursor.fetchone()
            
        if not row or row[1] < shares:
            await ctx.send(f"You don't have enough shares. Owned: {row[1] if row else 0}")
            return
            
        price = await self.get_price(ticker)
        if not price:
            await ctx.send(f"Could not get price for {ticker}.")
            return
            
        total_value = price * shares
        avg_price, current_shares = row
        
        # Update portfolio
        new_shares = current_shares - shares
        if new_shares == 0:
            await self.bot.db.execute("DELETE FROM portfolio WHERE user_id = ? AND ticker = ?", (ctx.author.id, ticker))
        else:
            await self.bot.db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND ticker = ?", (new_shares, ctx.author.id, ticker))
            
        # Add balance
        await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_value, ctx.author.id))
        await self.bot.get_cog("Economy").log_transaction(ctx.author.id, "paper_trading", total_value, f"Sold {shares} {ticker} @ ${price:.2f}")
        await self.bot.db.commit()
        
        # Calculate P/L
        cost_basis = avg_price * shares
        pl = total_value - cost_basis
        pl_pct = (pl / cost_basis) * 100
        
        color = "🟢" if pl >= 0 else "🔴"
        await ctx.send(f"Sold {shares} shares of {ticker} at ${price:.2f} (Total: ${total_value:.2f}).\nP/L: {color} ${pl:.2f} ({pl_pct:.2f}%)")

    @commands.hybrid_command(name="tportfolio", aliases=["tp"], description="View your paper trading portfolio.")
    async def tportfolio(self, ctx):
        async with self.bot.db.execute("SELECT ticker, avg_price, shares FROM portfolio WHERE user_id = ?", (ctx.author.id,)) as cursor:
            rows = await cursor.fetchall()
            
        if not rows:
            await ctx.send("Your portfolio is empty.")
            return
            
        embed = discord.Embed(title=f"{ctx.author.name}'s Portfolio", color=discord.Color.blue())
        
        total_value = 0
        total_cost = 0
        
        description = ""
        for ticker, avg_price, shares in rows:
            current_price = await self.get_price(ticker)
            if current_price:
                value = current_price * shares
                cost = avg_price * shares
                pl = value - cost
                pl_pct = (pl / cost) * 100 if cost > 0 else 0
                
                total_value += value
                total_cost += cost
                
                icon = "🟢" if pl >= 0 else "🔴"
                description += f"**{ticker}**: {shares} shares @ ${avg_price:.2f} -> ${current_price:.2f}\n"
                description += f"{icon} P/L: ${pl:.2f} ({pl_pct:.2f}%)\n\n"
            else:
                description += f"**{ticker}**: {shares} shares (Price Error)\n\n"
        
        total_pl = total_value - total_cost
        total_pl_pct = (total_pl / total_cost) * 100 if total_cost > 0 else 0
        total_icon = "🟢" if total_pl >= 0 else "🔴"
        
        embed.description = description
        embed.add_field(name="Total Value", value=f"${total_value:.2f}", inline=True)
        embed.add_field(name="Total P/L", value=f"{total_icon} ${total_pl:.2f} ({total_pl_pct:.2f}%)", inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(PaperTrading(bot))
