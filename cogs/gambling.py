import discord
from discord.ext import commands
import random
import asyncio

class Gambling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_balance(self, user_id):
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def update_balance(self, user_id, amount, description="Gambling"):
        async with self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id)) as cursor:
            if cursor.rowcount == 0:
                await self.bot.db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, amount))
        await self.bot.db.commit()
        await self.bot.get_cog("Economy").log_transaction(user_id, "gambling", amount, description)

    @commands.hybrid_command(description="Flip a coin to double your bet.")
    async def coinflip(self, ctx, amount: int, choice: str):
        if amount <= 0:
            await ctx.send("Amount must be positive.")
            return

        balance = await self.get_balance(ctx.author.id)
        if balance < amount:
            await ctx.send("Insufficient funds.")
            return

        choice = choice.lower()
        if choice not in ["heads", "tails", "h", "t"]:
            await ctx.send("Choose heads or tails.")
            return
        
        # Normalize choice
        choice = "heads" if choice.startswith("h") else "tails"
        
        result = random.choice(["heads", "tails"])
        
        if choice == result:
            winnings = amount
            await self.update_balance(ctx.author.id, winnings)
            await ctx.send(f"🪙 It's **{result.title()}**! You won **${winnings}**!")
        else:
            loss = -amount
            await self.update_balance(ctx.author.id, loss)
            await ctx.send(f"🪙 It's **{result.title()}**! You lost **${amount}**.")

    @commands.hybrid_command(description="Spin the slots.")
    async def slots(self, ctx, amount: int):
        if amount <= 0:
            await ctx.send("Amount must be positive.")
            return

        balance = await self.get_balance(ctx.author.id)
        if balance < amount:
            await ctx.send("Insufficient funds.")
            return

        # Deduct bet first
        await self.update_balance(ctx.author.id, -amount)

        emojis = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]
        a = random.choice(emojis)
        b = random.choice(emojis)
        c = random.choice(emojis)

        msg = await ctx.send(f"🎰 Spinning...\n{a} | {b} | {c}")
        
        payout = 0
        if a == b == c:
            payout = amount * 5
            result_text = f"JACKPOT! You won **${payout}**!"
        elif a == b or b == c or a == c:
            payout = amount * 2
            result_text = f"Nice! Two of a kind. You won **${payout}**!"
        else:
            result_text = "Better luck next time!"

        if payout > 0:
            await self.update_balance(ctx.author.id, payout)
        
        await msg.edit(content=f"🎰 Result:\n{a} | {b} | {c}\n\n{result_text}")

    @commands.hybrid_command(description="Play Blackjack.")
    async def blackjack(self, ctx, amount: int):
        if amount <= 0:
            await ctx.send("Amount must be positive.")
            return

        balance = await self.get_balance(ctx.author.id)
        if balance < amount:
            await ctx.send("Insufficient funds.")
            return

        # Deduct bet
        await self.update_balance(ctx.author.id, -amount)

        deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
        random.shuffle(deck)

        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]

        def calculate_score(hand):
            score = sum(hand)
            aces = hand.count(11)
            while score > 21 and aces:
                score -= 10
                aces -= 1
            return score

        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.dark_red())
        embed.add_field(name="Your Hand", value=f"{player_hand} (Score: {calculate_score(player_hand)})", inline=False)
        embed.add_field(name="Dealer's Hand", value=f"[{dealer_hand[0]}, ?]", inline=False)
        embed.set_footer(text="Type 'hit' or 'stand'")
        
        msg = await ctx.send(embed=embed)

        # Game Loop
        while True:
            if calculate_score(player_hand) == 21:
                break # Instant 21 (or Blackjack)
            
            try:
                response = await self.bot.wait_for(
                    "message", 
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["hit", "stand"], 
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                await ctx.send("Time's up! You stand.")
                break

            if response.content.lower() == "hit":
                player_hand.append(deck.pop())
                score = calculate_score(player_hand)
                
                embed.set_field_at(0, name="Your Hand", value=f"{player_hand} (Score: {score})", inline=False)
                await msg.edit(embed=embed)

                if score > 21:
                    await ctx.send(f"💥 Bust! You went over 21. You lost **${amount}**.")
                    return
            else:
                break

        # Dealer Turn
        dealer_score = calculate_score(dealer_hand)
        while dealer_score < 17:
            dealer_hand.append(deck.pop())
            dealer_score = calculate_score(dealer_hand)

        player_score = calculate_score(player_hand)

        embed.set_field_at(0, name="Your Hand", value=f"{player_hand} (Score: {player_score})", inline=False)
        embed.set_field_at(1, name="Dealer's Hand", value=f"{dealer_hand} (Score: {dealer_score})", inline=False)
        await msg.edit(embed=embed)

        if player_score > 21:
            await ctx.send(f"💥 Bust! You lost **${amount}**.") # Should be caught above, but safety net
        elif dealer_score > 21:
            winnings = amount * 2
            await self.update_balance(ctx.author.id, winnings)
            await ctx.send(f"🎉 Dealer Bust! You won **${winnings}**!")
        elif player_score > dealer_score:
            winnings = amount * 2
            await self.update_balance(ctx.author.id, winnings)
            await ctx.send(f"🎉 You won **${winnings}**!")
        elif player_score == dealer_score:
            await self.update_balance(ctx.author.id, amount)
            await ctx.send("🤝 Push! Your bet is returned.")
        else:
            await ctx.send(f"📉 Dealer wins. You lost **${amount}**.")

            await ctx.send(f"📉 Dealer wins. You lost **${amount}**.")

    @commands.hybrid_command(description="Guess if the next number (1-100) is higher or lower.")
    async def highlow(self, ctx, amount: int, choice: str):
        if amount <= 0: return await ctx.send("Amount must be positive.")
        
        balance = await self.get_balance(ctx.author.id)
        if balance < amount: return await ctx.send("Insufficient funds.")

        choice = choice.lower()
        if choice not in ["higher", "lower", "high", "low"]:
            return await ctx.send("Choice must be 'higher' or 'lower'.")
        
        # Deduct bet
        await self.update_balance(ctx.author.id, -amount, "HighLow Bet")

        current = random.randint(1, 100)
        await ctx.send(f"Current number is **{current}**. Will the next be higher or lower?")
        await asyncio.sleep(2)

        next_num = random.randint(1, 100)
        
        win = False
        if choice.startswith("h"):
            if next_num > current: win = True
        else:
            if next_num < current: win = True
            
        if next_num == current:
            # Push
            await self.update_balance(ctx.author.id, amount, "HighLow Push")
            await ctx.send(f"The number was **{next_num}**. It's a tie! Bet returned.")
            return

        if win:
            winnings = int(amount * 1.8) # 1.8x multiplier
            await self.update_balance(ctx.author.id, winnings, "HighLow Win")
            await ctx.send(f"The number was **{next_num}**. You won **${winnings}**!")
        else:
            await ctx.send(f"The number was **{next_num}**. You lost **${amount}**.")

    @commands.hybrid_command(description="Roll two dice. Pairs win!")
    async def snakeeyes(self, ctx, amount: int):
        if amount <= 0: return await ctx.send("Amount must be positive.")
        
        balance = await self.get_balance(ctx.author.id)
        if balance < amount: return await ctx.send("Insufficient funds.")

        # Deduct bet
        await self.update_balance(ctx.author.id, -amount, "SnakeEyes Bet")

        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        
        msg = await ctx.send("🎲 Rolling...")
        await asyncio.sleep(1)
        
        await msg.edit(content=f"🎲 You rolled **{d1}** and **{d2}**!")
        
        if d1 == 1 and d2 == 1:
            # Snake Eyes (30x)
            winnings = amount * 30
            await self.update_balance(ctx.author.id, winnings, "SnakeEyes Jackpot")
            await ctx.send(f"🐍 **SNAKE EYES!** You won **${winnings}** (30x)!")
        elif d1 == d2:
            # Pair (5x)
            winnings = amount * 5
            await self.update_balance(ctx.author.id, winnings, "SnakeEyes Pair")
            await ctx.send(f"🎉 **PAIR!** You won **${winnings}** (5x)!")
        else:
            await ctx.send(f"😢 No pair. You lost **${amount}**.")

async def setup(bot):
    await bot.add_cog(Gambling(bot))
