import discord
from discord.ext import commands
import datetime

class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="Create a native poll.")
    async def poll(self, ctx, question: str, options: str, duration: str = "24h", allow_multiselect: bool = False):
        """
        Create a native Discord poll.
        Options separated by | (pipe).
        Duration example: 1h, 24h, 3d (max 7 days).
        """
        opts = [o.strip() for o in options.split("|")]
        if len(opts) < 2:
            await ctx.send("You need at least 2 options.")
            return
        if len(opts) > 10:
            await ctx.send("Max 10 options for native polls.")
            return

        # Duration parsing
        duration_delta = datetime.timedelta(hours=24) # Default
        if duration:
            try:
                unit = duration[-1].lower()
                val = int(duration[:-1])
                if unit == 'h': 
                    duration_delta = datetime.timedelta(hours=val)
                elif unit == 'd': 
                    duration_delta = datetime.timedelta(days=val)
                else:
                    await ctx.send("Invalid duration unit. Use 'h' (hours) or 'd' (days). Example: 12h, 3d.")
                    return
                
                # Discord limits: Min 1 hour, Max 7 days (approx 168h)
                if duration_delta < datetime.timedelta(hours=1): 
                    duration_delta = datetime.timedelta(hours=1)
                if duration_delta > datetime.timedelta(days=7): 
                    duration_delta = datetime.timedelta(days=7)
            except ValueError:
                await ctx.send("Invalid duration format. Example: 24h, 2d.")
                return

        try:
            poll = discord.Poll(
                question=question,
                duration=duration_delta,
                multiple=allow_multiselect
            )
            
            for opt in opts:
                poll.add_answer(text=opt)

            await ctx.send(poll=poll)
        except Exception as e:
            await ctx.send(f"Failed to create poll: {e}")

    @commands.hybrid_command(description="End a poll early.")
    @commands.has_permissions(administrator=True)
    async def endpoll(self, ctx, message_id: str):
        try:
            mid = int(message_id)
            msg = await ctx.channel.fetch_message(mid)
            if msg.poll:
                await msg.end_poll()
                await ctx.send("✅ Poll ended successfully.")
            else:
                await ctx.send("❌ That message is not a poll.")
        except discord.NotFound:
            await ctx.send("❌ Message not found.")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to end this poll.")
        except ValueError:
            await ctx.send("❌ Invalid message ID.")
        except Exception as e:
            await ctx.send(f"❌ Error ending poll: {e}")

async def setup(bot):
    await bot.add_cog(Polls(bot))
