import discord
from discord.ext import commands, tasks
import datetime

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    @tasks.loop(minutes=1)
    async def check_reminders(self):
        now = datetime.datetime.now().isoformat()
        
        async with self.bot.db.execute("SELECT id, user_id, channel_id, message FROM reminders WHERE remind_time <= ?", (now,)) as cursor:
            due_reminders = await cursor.fetchall()
            
        for rid, uid, cid, msg in due_reminders:
            channel = self.bot.get_channel(cid)
            user = self.bot.get_user(uid)
            if user:
                embed = discord.Embed(title="⏰ Reminder!", description=msg, color=discord.Color.gold())
                try:
                    if channel:
                        await channel.send(content=user.mention, embed=embed)
                    else:
                        await user.send(embed=embed)
                except: pass
            
            # Delete reminder
            await self.bot.db.execute("DELETE FROM reminders WHERE id = ?", (rid,))
        
        if due_reminders:
            await self.bot.db.commit()

    @check_reminders.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="remindme", description="Set a reminder (e.g. 'check stocks').")
    async def remindme(self, ctx, minutes: int, *, message: str):
        if minutes <= 0:
            await ctx.send("Minutes must be greater than 0.")
            return
            
        remind_time = (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).isoformat()
        
        await self.bot.db.execute("INSERT INTO reminders (user_id, channel_id, message, remind_time) VALUES (?, ?, ?, ?)", 
                                  (ctx.author.id, ctx.channel.id, message, remind_time))
        await self.bot.db.commit()
        
        await ctx.send(f"✅ I will remind you about `{message}` in {minutes} minutes.")

async def setup(bot):
    await bot.add_cog(Reminders(bot))
