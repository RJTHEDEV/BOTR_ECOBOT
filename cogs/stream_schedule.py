import discord
from discord.ext import commands
import datetime

class StreamSchedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(invoke_without_command=True, description="Manage your stream schedule.")
    async def stream_schedule(self, ctx):
        await ctx.send("Use `/stream_schedule next <timestamp>` to set a countdown.")

    @stream_schedule.command(name="next", description="Set a countdown to your next stream. Use Unix Timestamp.")
    @commands.has_permissions(manage_messages=True)
    async def next_stream(self, ctx, unix_timestamp: int, *, title: str = "Next Stream"):
        """
        Set a countdown. You can get unix timestamps from https://www.unixtimestamp.com/
        Example: /schedule next 1700000000 Subathon!
        """
        # Discord uses specific syntax for dynamic countdowns: <t:TIMESTAMP:R>
        
        embed = discord.Embed(title="📅 Stream Schedule Updated!", color=discord.Color.purple())
        embed.add_field(name="Event", value=title, inline=False)
        embed.add_field(name="Countdown", value=f"Going live <t:{unix_timestamp}:R>!", inline=False)
        embed.add_field(name="Local Time", value=f"<t:{unix_timestamp}:F>", inline=False)
        
        await ctx.send(embed=embed)
        
        # If there's an announcement channel configured, send it there
        async with self.bot.db.execute("SELECT welcome_channel_id FROM guild_settings WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                announcement_channel = ctx.guild.get_channel(row[0])
                if announcement_channel and announcement_channel.id != ctx.channel.id:
                    try:
                        await announcement_channel.send(embed=embed)
                    except: pass

async def setup(bot):
    await bot.add_cog(StreamSchedule(bot))
