import discord
from discord.ext import commands
import datetime
import random

QUEST_TYPES = {
    "rob": {"target": 3, "desc": "Rob 3 people", "reward": 500},
    "work": {"target": 5, "desc": "Work 5 times", "reward": 300},
    "gamble": {"target": 10, "desc": "Play 10 gambling games", "reward": 1000},
    "daily": {"target": 1, "desc": "Claim your daily reward", "reward": 100},
    "craft": {"target": 2, "desc": "Craft 2 items", "reward": 800}
}

class Quests(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="quest", description="View your daily quest.")
    async def quest(self, ctx):
        today = datetime.date.today().isoformat()
        
        async with self.bot.db.execute("SELECT quest_type, target, progress, completed, date_assigned FROM quests WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row or row[4] != today:
            # Assign new quest
            q_type = random.choice(list(QUEST_TYPES.keys()))
            q_target = QUEST_TYPES[q_type]["target"]
            
            await self.bot.db.execute("""
                INSERT INTO quests (user_id, quest_type, target, progress, completed, date_assigned)
                VALUES (?, ?, ?, 0, 0, ?)
                ON CONFLICT(user_id) DO UPDATE SET 
                    quest_type=excluded.quest_type, target=excluded.target, progress=0, completed=0, date_assigned=excluded.date_assigned
            """, (ctx.author.id, q_type, q_target, today))
            await self.bot.db.commit()
            
            row = (q_type, q_target, 0, 0, today)
            
        q_type, target, progress, completed, date_assigned = row
        
        desc = QUEST_TYPES.get(q_type, {}).get("desc", "Unknown Quest")
        reward = QUEST_TYPES.get(q_type, {}).get("reward", 0)
        
        embed = discord.Embed(title="📜 Daily Quest", color=discord.Color.green() if completed else discord.Color.blue())
        embed.add_field(name="Mission", value=desc, inline=False)
        embed.add_field(name="Progress", value=f"{progress} / {target}", inline=True)
        embed.add_field(name="Reward", value=f"${reward}", inline=True)
        embed.add_field(name="Status", value="✅ Completed" if completed else "⏳ In Progress", inline=False)
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if ctx.author.bot: return
        
        cmd_name = ctx.command.name if ctx.command else None
        if not cmd_name: return
        
        # Mapping commands to quest types
        q_type = None
        if cmd_name == "rob": q_type = "rob"
        elif cmd_name == "work": q_type = "work"
        elif cmd_name in ["slots", "coinflip", "blackjack"]: q_type = "gamble"
        elif cmd_name == "daily": q_type = "daily"
        elif cmd_name == "craft": q_type = "craft"
        
        if not q_type: return
        
        today = datetime.date.today().isoformat()
        
        async with self.bot.db.execute("SELECT target, progress, completed FROM quests WHERE user_id = ? AND quest_type = ? AND date_assigned = ?", (ctx.author.id, q_type, today)) as cursor:
            row = await cursor.fetchone()
            
        if row:
            target, progress, completed = row
            if not completed:
                progress += 1
                if progress >= target:
                    # Completed
                    reward = QUEST_TYPES[q_type]["reward"]
                    await self.bot.db.execute("UPDATE quests SET progress = ?, completed = 1 WHERE user_id = ?", (progress, ctx.author.id))
                    await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, ctx.author.id))
                    await self.bot.db.commit()
                    
                    try:
                        await ctx.author.send(f"🎉 **Quest Completed!** You finished your daily quest to '{QUEST_TYPES[q_type]['desc']}' and earned **${reward}**!")
                    except: pass
                else:
                    await self.bot.db.execute("UPDATE quests SET progress = ? WHERE user_id = ?", (progress, ctx.author.id))
                    await self.bot.db.commit()

async def setup(bot):
    await bot.add_cog(Quests(bot))
