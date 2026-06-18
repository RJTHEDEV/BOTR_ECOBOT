import discord
from discord.ext import commands
import random
import asyncio

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, user, game_choice, bet):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.game_choice = game_choice
        self.bet = bet

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄")
    async def btn_play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        balance = await self.cog.get_balance(self.user.id)
        if balance < self.bet:
            await interaction.response.send_message("❌ You don't have enough money to play again.", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        await self.cog.update_balance(self.user.id, -self.bet, f"Casino Bet ({self.game_choice})")
        
        for item in self.children: item.disabled = True
        try: await interaction.message.edit(view=self)
        except: pass
        
        if self.game_choice == "blackjack":
            await self.cog.start_blackjack(interaction.channel, self.user, self.bet)
        elif self.game_choice == "slots":
            await self.cog.start_slots(interaction.channel, self.user, self.bet)
        elif self.game_choice == "highlow":
            await self.cog.start_highlow(interaction.channel, self.user, self.bet)
        elif self.game_choice == "coinflip":
            await self.cog.start_coinflip(interaction.channel, self.user, self.bet)
        elif self.game_choice == "snakeeyes":
            await self.cog.start_snakeeyes(interaction.channel, self.user, self.bet)

class BlackjackView(discord.ui.View):
    def __init__(self, cog, user, bet, deck, player_hand, dealer_hand, msg):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.bet = bet
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.msg = msg

    def calculate_score(self, hand):
        score = sum(hand)
        aces = hand.count(11)
        while score > 21 and aces:
            score -= 10
            aces -= 1
        return score

    def create_embed(self, player_score, dealer_score=None, hide_dealer=True):
        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.dark_red())
        embed.add_field(name="Your Hand", value=f"{self.player_hand} (Score: {player_score})", inline=False)
        if hide_dealer:
            embed.add_field(name="Dealer's Hand", value=f"[{self.dealer_hand[0]}, ?]", inline=False)
        else:
            embed.add_field(name="Dealer's Hand", value=f"{self.dealer_hand} (Score: {dealer_score})", inline=False)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    async def disable_buttons(self, interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.success)
    async def btn_hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_hand.append(self.deck.pop())
        score = self.calculate_score(self.player_hand)
        
        if score > 21:
            await self.disable_buttons(interaction)
            await self.cog.add_to_jackpot(self.bet)
            embed = self.create_embed(score, self.calculate_score(self.dealer_hand), False)
            embed.description = f"💥 **Bust!** You went over 21. You lost **${self.bet}**."
            await self.msg.edit(embed=embed, view=PlayAgainView(self.cog, self.user, "blackjack", self.bet))
        else:
            embed = self.create_embed(score)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.danger)
    async def btn_stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.disable_buttons(interaction)
        
        dealer_score = self.calculate_score(self.dealer_hand)
        while dealer_score < 17:
            self.dealer_hand.append(self.deck.pop())
            dealer_score = self.calculate_score(self.dealer_hand)

        player_score = self.calculate_score(self.player_hand)
        embed = self.create_embed(player_score, dealer_score, False)

        if dealer_score > 21:
            winnings = self.bet * 2
            await self.cog.update_balance(self.user.id, winnings, "Blackjack Win")
            embed.description = f"🎉 **Dealer Busts!** You won **${winnings}**!"
        elif player_score > dealer_score:
            winnings = self.bet * 2
            await self.cog.update_balance(self.user.id, winnings, "Blackjack Win")
            embed.description = f"🎉 **You Win!** You beat the dealer and won **${winnings}**!"
        elif player_score == dealer_score:
            await self.cog.update_balance(self.user.id, self.bet, "Blackjack Push")
            embed.description = "🤝 **Push!** It's a tie. Your bet is returned."
        else:
            await self.cog.add_to_jackpot(self.bet)
            embed.description = f"📉 **Dealer Wins.** You lost **${self.bet}**."

        await self.msg.edit(embed=embed, view=PlayAgainView(self.cog, self.user, "blackjack", self.bet))

class HighLowView(discord.ui.View):
    def __init__(self, cog, user, bet, current, msg):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.bet = bet
        self.current = current
        self.msg = msg

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    async def process_guess(self, interaction, guess_higher):
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(view=self)
        
        next_num = random.randint(1, 100)
        
        win = False
        if guess_higher and next_num > self.current: win = True
        elif not guess_higher and next_num < self.current: win = True
            
        embed = discord.Embed(title="📈 High / Low 📉", color=discord.Color.blue())
        if next_num == self.current:
            await self.cog.update_balance(self.user.id, self.bet, "HighLow Push")
            embed.description = f"The new number is **{next_num}**. It's a tie! Bet returned."
        elif win:
            async with self.cog.bot.db.execute("SELECT casino_vip FROM users WHERE user_id = ?", (self.user.id,)) as cursor:
                row = await cursor.fetchone()
                is_vip = bool(row[0]) if row else False
            
            multiplier = 2.0 if is_vip else 1.8
            winnings = int(self.bet * multiplier)
            await self.cog.update_balance(self.user.id, winnings, "HighLow Win")
            vip_text = " *(VIP Multiplier!)*" if is_vip else ""
            embed.description = f"The new number is **{next_num}**. You guessed correctly and won **${winnings}**!{vip_text}"
            embed.color = discord.Color.green()
        else:
            await self.cog.add_to_jackpot(self.bet)
            embed.description = f"The new number is **{next_num}**. You guessed wrong and lost **${self.bet}**."
            embed.color = discord.Color.red()
            
        await self.msg.edit(embed=embed, view=PlayAgainView(self.cog, self.user, "highlow", self.bet))

    @discord.ui.button(label="Higher", style=discord.ButtonStyle.success, emoji="⬆️")
    async def btn_higher(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_guess(interaction, True)

    @discord.ui.button(label="Lower", style=discord.ButtonStyle.danger, emoji="⬇️")
    async def btn_lower(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_guess(interaction, False)

class CoinFlipView(discord.ui.View):
    def __init__(self, cog, user, bet, msg):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.bet = bet
        self.msg = msg

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    async def process_flip(self, interaction, choice):
        await interaction.response.defer()
        for child in self.children:
            child.disabled = True
            
        result = random.choice(["heads", "tails"])
        embed = discord.Embed(title="🪙 Coin Flip", color=discord.Color.blue())
        
        if choice == result:
            async with self.cog.bot.db.execute("SELECT casino_vip FROM users WHERE user_id = ?", (self.user.id,)) as cursor:
                row = await cursor.fetchone()
                is_vip = bool(row[0]) if row else False
                
            multiplier = 2.2 if is_vip else 2.0
            winnings = int(self.bet * multiplier)
            await self.cog.update_balance(self.user.id, winnings, "CoinFlip Win")
            vip_text = " *(VIP Boost!)*" if is_vip else ""
            embed.description = f"The coin landed on **{result.title()}**!\nYou guessed correctly and won **${winnings}**!{vip_text}"
            embed.color = discord.Color.green()
        else:
            await self.cog.add_to_jackpot(self.bet)
            embed.description = f"The coin landed on **{result.title()}**!\nYou guessed wrong and lost **${self.bet}**."
            embed.color = discord.Color.red()
            
        await self.msg.edit(embed=embed, view=PlayAgainView(self.cog, self.user, "coinflip", self.bet))

    @discord.ui.button(label="Heads", style=discord.ButtonStyle.primary)
    async def btn_heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_flip(interaction, "heads")

    @discord.ui.button(label="Tails", style=discord.ButtonStyle.primary)
    async def btn_tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_flip(interaction, "tails")


class CasinoBetModal(discord.ui.Modal):
    def __init__(self, cog, game_choice):
        super().__init__(title=f"Bet Amount for {game_choice.title()}")
        self.cog = cog
        self.game_choice = game_choice
        
        self.bet_input = discord.ui.TextInput(
            label="How much do you want to bet?",
            placeholder="e.g. 100, 500, 1000",
            required=True
        )
        self.add_item(self.bet_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet = int(self.bet_input.value)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number.", ephemeral=True)
            return

        if bet <= 0:
            await interaction.response.send_message("❌ Amount must be greater than zero.", ephemeral=True)
            return

        balance = await self.cog.get_balance(interaction.user.id)
        if balance < bet:
            await interaction.response.send_message("❌ Insufficient funds for this bet.", ephemeral=True)
            return

        await interaction.response.defer()
        
        # Deduct bet for games
        await self.cog.update_balance(interaction.user.id, -bet, f"Casino Bet ({self.game_choice})")
        
        if self.game_choice == "blackjack":
            await self.cog.start_blackjack(interaction.channel, interaction.user, bet)
        elif self.game_choice == "slots":
            await self.cog.start_slots(interaction.channel, interaction.user, bet)
        elif self.game_choice == "highlow":
            await self.cog.start_highlow(interaction.channel, interaction.user, bet)
        elif self.game_choice == "coinflip":
            await self.cog.start_coinflip(interaction.channel, interaction.user, bet)
        elif self.game_choice == "snakeeyes":
            await self.cog.start_snakeeyes(interaction.channel, interaction.user, bet)


class CasinoLobbySelect(discord.ui.Select):
    def __init__(self, cog):
        self.cog = cog
        options = [
            discord.SelectOption(label="Slots", description="Spin to win big multipliers! (Jackpot eligible)", emoji="🎰", value="slots"),
            discord.SelectOption(label="Blackjack", description="Beat the dealer to 21.", emoji="🃏", value="blackjack"),
            discord.SelectOption(label="High / Low", description="Guess if the next number is higher or lower.", emoji="📈", value="highlow"),
            discord.SelectOption(label="Coin Flip", description="50/50 chance to double your bet.", emoji="🪙", value="coinflip"),
            discord.SelectOption(label="Snake Eyes", description="Roll two dice. Pairs win! (Jackpot eligible)", emoji="🎲", value="snakeeyes")
        ]
        super().__init__(placeholder="Select a game to play...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        game = self.values[0]
        modal = CasinoBetModal(self.cog, game)
        await interaction.response.send_modal(modal)

class CasinoLobbyView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.add_item(CasinoLobbySelect(cog))


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
        if amount != 0:
            await self.bot.get_cog("Economy").log_transaction(user_id, "gambling", amount, description)

    async def add_to_jackpot(self, bet_amount):
        # 5% of losses go to the global jackpot
        contribution = int(bet_amount * 0.05)
        if contribution > 0:
            await self.bot.db.execute("UPDATE casino_jackpot SET amount = amount + ? WHERE id = 1", (contribution,))
            await self.bot.db.commit()

    @commands.hybrid_group(name="casino", invoke_without_command=True, description="Open the Casino Lobby.")
    async def casino_group(self, ctx):
        await self.lobby(ctx)

    @casino_group.command(description="Open the main Casino Lobby.")
    async def lobby(self, ctx):
        async with self.bot.db.execute("SELECT amount FROM casino_jackpot WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            jackpot = row[0] if row else 10000

        embed = discord.Embed(title="🎰 Welcome to the Casino Lobby", description="Select a game from the dropdown below to place your bets!", color=discord.Color.gold())
        embed.add_field(name="💰 Mega Jackpot", value=f"**${jackpot:,}**", inline=False)
        embed.set_footer(text="Play Slots or Snake Eyes to win the Mega Jackpot!")
        await ctx.send(embed=embed, view=CasinoLobbyView(self))

    async def start_slots(self, channel, user, bet):
        emojis = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]
        embed = discord.Embed(title="🎰 Slots", description="Spinning...\n\n❓ | ❓ | ❓", color=discord.Color.gold())
        msg = await channel.send(embed=embed)
        
        # Animation
        for i in range(3):
            await asyncio.sleep(0.5)
            e1, e2, e3 = random.choice(emojis), random.choice(emojis), random.choice(emojis)
            embed.description = f"Spinning...\n\n{e1} | {e2} | {e3}"
            await msg.edit(embed=embed)

        a, b, c = random.choice(emojis), random.choice(emojis), random.choice(emojis)
        
        if a == b == c == "7️⃣":
            # MEGA JACKPOT
            async with self.bot.db.execute("SELECT amount FROM casino_jackpot WHERE id = 1") as cursor:
                jp = await cursor.fetchone()[0]
            await self.update_balance(user.id, jp, "Mega Jackpot Win")
            await self.bot.db.execute("UPDATE casino_jackpot SET amount = 10000 WHERE id = 1")
            await self.bot.db.commit()
            embed.description = f"**{a} | {b} | {c}**\n\n🚨 **MEGA JACKPOT!!!** 🚨\nYou won the entire pool of **${jp:,}**!"
            embed.color = discord.Color.green()
        elif a == b == c:
            payout = bet * 10
            await self.update_balance(user.id, payout, "Slots Jackpot")
            embed.description = f"**{a} | {b} | {c}**\n\n🎉 **JACKPOT!** You won **${payout}** (10x)!"
            embed.color = discord.Color.green()
        elif a == b or b == c or a == c:
            payout = bet * 2
            await self.update_balance(user.id, payout, "Slots Win")
            embed.description = f"**{a} | {b} | {c}**\n\nNice! Two of a kind. You won **${payout}**!"
            embed.color = discord.Color.green()
        else:
            await self.add_to_jackpot(bet)
            embed.description = f"**{a} | {b} | {c}**\n\nBetter luck next time. You lost **${bet}**."
            embed.color = discord.Color.red()
            
        await msg.edit(embed=embed, view=PlayAgainView(self, user, "slots", bet))

    async def start_blackjack(self, channel, user, bet):
        deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
        random.shuffle(deck)

        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]

        def calc_score(hand):
            s = sum(hand)
            a = hand.count(11)
            while s > 21 and a:
                s -= 10
                a -= 1
            return s
            
        p_score = calc_score(player_hand)
        
        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.dark_red())
        embed.add_field(name="Your Hand", value=f"{player_hand} (Score: {p_score})", inline=False)
        embed.add_field(name="Dealer's Hand", value=f"[{dealer_hand[0]}, ?]", inline=False)
        
        msg = await channel.send(f"<@{user.id}>", embed=embed)
        
        if p_score == 21:
            winnings = int(bet * 2.5)
            await self.update_balance(user.id, winnings, "Blackjack 21")
            embed.description = f"🎉 **Blackjack!** You won **${winnings}**!"
            await msg.edit(embed=embed, view=PlayAgainView(self, user, "blackjack", bet))
            return
            
        view = BlackjackView(self, user, bet, deck, player_hand, dealer_hand, msg)
        await msg.edit(view=view)

    async def start_highlow(self, channel, user, bet):
        current = random.randint(1, 100)
        embed = discord.Embed(title="📈 High / Low 📉", description=f"The current number is **{current}**.\nWill the next number be Higher or Lower?", color=discord.Color.blue())
        msg = await channel.send(f"<@{user.id}>", embed=embed)
        view = HighLowView(self, user, bet, current, msg)
        await msg.edit(view=view)

    async def start_coinflip(self, channel, user, bet):
        embed = discord.Embed(title="🪙 Coin Flip", description="Choose Heads or Tails!", color=discord.Color.gold())
        msg = await channel.send(f"<@{user.id}>", embed=embed)
        view = CoinFlipView(self, user, bet, msg)
        await msg.edit(view=view)

    async def start_snakeeyes(self, channel, user, bet):
        embed = discord.Embed(title="🎲 Snake Eyes", description="Rolling the dice...", color=discord.Color.purple())
        msg = await channel.send(f"<@{user.id}>", embed=embed)
        
        await asyncio.sleep(1.5)
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        
        if d1 == 1 and d2 == 1:
            async with self.bot.db.execute("SELECT amount FROM casino_jackpot WHERE id = 1") as cursor:
                jp = await cursor.fetchone()[0]
            await self.update_balance(user.id, jp, "Mega Jackpot Win")
            await self.bot.db.execute("UPDATE casino_jackpot SET amount = 10000 WHERE id = 1")
            await self.bot.db.commit()
            embed.description = f"You rolled **{d1}** and **{d2}**!\n\n🚨 **SNAKE EYES MEGA JACKPOT!!!** 🚨\nYou won the entire pool of **${jp:,}**!"
            embed.color = discord.Color.green()
        elif d1 == d2:
            winnings = bet * 5
            await self.update_balance(user.id, winnings, "SnakeEyes Pair")
            embed.description = f"You rolled **{d1}** and **{d2}**!\n\n🎉 **PAIR!** You won **${winnings}** (5x)!"
            embed.color = discord.Color.green()
        else:
            await self.add_to_jackpot(bet)
            embed.description = f"You rolled **{d1}** and **{d2}**.\n\n😢 No pair. You lost **${bet}**."
            embed.color = discord.Color.red()
            
        await msg.edit(embed=embed, view=PlayAgainView(self, user, "snakeeyes", bet))

async def setup(bot):
    await bot.add_cog(Gambling(bot))
