import discord
from discord.ext import commands
import random
import asyncio

TRIVIA_QUESTIONS = [
    {"q": "What is the capital of France?", "options": ["Paris", "London", "Berlin", "Madrid"], "answer": 0},
    {"q": "Which crypto is known as 'digital gold'?", "options": ["Ethereum", "Bitcoin", "Dogecoin", "Solana"], "answer": 1},
    {"q": "What is the maximum supply of Bitcoin?", "options": ["10 Million", "21 Million", "50 Million", "Unlimited"], "answer": 1},
    {"q": "In Valorant, who says 'Watch them run!'?", "options": ["Brimstone", "Viper", "Omen", "Reyna"], "answer": 1},
    {"q": "What is the ticker symbol for Apple?", "options": ["APP", "AAPL", "APL", "APPLE"], "answer": 1},
]

class TriviaView(discord.ui.View):
    def __init__(self, question_data, bot):
        super().__init__(timeout=15)
        self.question_data = question_data
        self.bot = bot
        self.answered = set()
        self.scores = {}
        
        for i, option in enumerate(question_data["options"]):
            btn = discord.ui.Button(label=option, style=discord.ButtonStyle.primary, custom_id=f"trivia_{i}")
            btn.callback = self.make_callback(i)
            self.add_item(btn)
            
    def make_callback(self, index):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id in self.answered:
                await interaction.response.send_message("You already answered!", ephemeral=True)
                return
                
            self.answered.add(interaction.user.id)
            if index == self.question_data["answer"]:
                self.scores[interaction.user.id] = 10
                await interaction.response.send_message("✅ Correct!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Incorrect!", ephemeral=True)
        return callback

class Trivia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="Start a quick trivia game!")
    @commands.has_permissions(manage_messages=True)
    async def trivia(self, ctx):
        await ctx.send("🧠 **Trivia Event Starting in 5 seconds!** Get ready!")
        await asyncio.sleep(5)
        
        questions = random.sample(TRIVIA_QUESTIONS, 3)
        total_scores = {}
        
        for q in questions:
            embed = discord.Embed(title="❓ Trivia Question", description=f"**{q['q']}**\n\nYou have 15 seconds to answer!", color=discord.Color.blue())
            view = TriviaView(q, self.bot)
            msg = await ctx.send(embed=embed, view=view)
            
            await asyncio.sleep(15)
            
            # Disable buttons
            for child in view.children:
                child.disabled = True
            
            correct_answer = q['options'][q['answer']]
            embed.description = f"**{q['q']}**\n\n⏰ Time's up! The correct answer was **{correct_answer}**."
            embed.color = discord.Color.red()
            await msg.edit(embed=embed, view=view)
            
            # Tally scores
            for uid, score in view.scores.items():
                total_scores[uid] = total_scores.get(uid, 0) + score
                
            await asyncio.sleep(3)
            
        # End game
        if not total_scores:
            await ctx.send("The trivia ended, but nobody scored any points!")
            return
            
        sorted_scores = sorted(total_scores.items(), key=lambda x: x[1], reverse=True)
        winner_id, winning_score = sorted_scores[0]
        
        # Payout
        payout = winning_score * 50
        await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (payout, winner_id))
        await self.bot.db.commit()
        
        embed = discord.Embed(title="🏆 Trivia Winner!", description=f"<@{winner_id}> won the trivia with **{winning_score}** points!\nThey have been awarded **${payout}**!", color=discord.Color.gold())
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Trivia(bot))
