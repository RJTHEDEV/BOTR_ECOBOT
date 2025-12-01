import discord
from discord.ext import commands, tasks
import datetime
import zoneinfo

class Alerts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.market_status_loop.start()

    def cog_unload(self):
        self.market_status_loop.cancel()

    @tasks.loop(minutes=1)
    async def market_status_loop(self):
        # Get current time in ET
        try:
            et_tz = zoneinfo.ZoneInfo("America/New_York")
        except:
            # Fallback if zoneinfo fails (though it shouldn't on modern Python)
            et_tz = datetime.timezone(datetime.timedelta(hours=-5))
            
        now = datetime.datetime.now(et_tz)
        current_time = now.strftime("%H:%M")
        weekday = now.weekday() # 0=Mon, 6=Sun

        # Define Events (Time in ET)
        # Note: Tokyo opens Sunday evening ET, so we handle that.
        events = []

        # New York (Mon-Fri)
        if 0 <= weekday <= 4:
            if current_time == "09:30": events.append(("🇺🇸 New York Stock Exchange", "OPEN", discord.Color.green()))
            elif current_time == "16:00": events.append(("🇺🇸 New York Stock Exchange", "CLOSED", discord.Color.red()))

        # London (Mon-Fri)
        if 0 <= weekday <= 4:
            if current_time == "03:00": events.append(("🇬🇧 London Session", "OPEN", discord.Color.green()))
            elif current_time == "11:30": events.append(("🇬🇧 London Session", "CLOSED", discord.Color.red()))

        # Tokyo (Sun-Thu ET for Mon-Fri JST)
        if 0 <= weekday <= 4 or weekday == 6:
            # Sunday to Thursday ET covers Monday to Friday JST roughly
            if current_time == "19:00": events.append(("🇯🇵 Tokyo Session", "OPEN", discord.Color.green()))
            elif current_time == "02:00": events.append(("🇯🇵 Tokyo Session", "CLOSED", discord.Color.red()))

        if not events:
            return

        # Fetch subscribed channels
        async with self.bot.db.execute("SELECT channel_id FROM log_settings WHERE log_type = 'market_alerts'") as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            return

        for name, status, color in events:
            embed = discord.Embed(title=f"🔔 Market Status: {name}", description=f"The market is now **{status}**.", color=color)
            embed.set_footer(text=f"Time: {now.strftime('%I:%M %p ET')}")
            
            for (channel_id,) in rows:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(embed=embed)
                    except:
                        pass # Ignore permission errors

    @market_status_loop.before_loop
    async def before_market_status_loop(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(description="Admin: Post a trade alert.")
    @commands.has_permissions(administrator=True)
    async def alert(self, ctx, type: str, ticker: str, action: str, price: str, *, notes: str = ""):
        """
        Format: !alert <type> <ticker> <action> <price> [notes]
        Example: !alert OPTION AAPL BUY 150.00 "Looking for a bounce"
        """
        embed = discord.Embed(title=f"🚨 TRADE ALERT: {ticker.upper()} 🚨", color=discord.Color.red())
        embed.add_field(name="Type", value=type.upper(), inline=True)
        embed.add_field(name="Action", value=action.upper(), inline=True)
        embed.add_field(name="Price", value=price, inline=True)
        if notes:
            embed.add_field(name="Notes", value=notes, inline=False)
        
        embed.set_footer(text=f"Alert by {ctx.author.display_name} • {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Alerts(bot))
