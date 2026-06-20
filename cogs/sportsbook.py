import discord
from discord.ext import commands

class BetModal(discord.ui.Modal):
    def __init__(self, bot, choice: str, bet_id: int):
        super().__init__(title=f"Bet on {choice.upper()}")
        self.bot = bot
        self.choice = choice
        self.bet_id = bet_id

        self.amount = discord.ui.TextInput(
            label="Amount to bet",
            placeholder="e.g. 1000",
            required=True
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
        except ValueError:
            await interaction.response.send_message("Invalid amount. Must be a number.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return

        async with self.bot.db.execute("SELECT status, pool_yes, pool_no FROM active_bets WHERE message_id = ?", (self.bet_id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            await interaction.response.send_message("Bet not found or ended.", ephemeral=True)
            return
            
        if row[0] != "open":
            await interaction.response.send_message("This bet is closed for new entries.", ephemeral=True)
            return

        # Check balance
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (interaction.user.id,)) as cursor:
            bal_row = await cursor.fetchone()
            
        if not bal_row or bal_row[0] < amount:
            await interaction.response.send_message("Insufficient funds.", ephemeral=True)
            return

        # Deduct
        await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, interaction.user.id))
        
        # Add to entry
        await self.bot.db.execute("INSERT INTO bet_entries (message_id, user_id, choice, amount) VALUES (?, ?, ?, ?) ON CONFLICT(message_id, user_id) DO UPDATE SET amount = amount + excluded.amount", 
                                  (self.bet_id, interaction.user.id, self.choice, amount))
                                  
        # Update pool
        if self.choice == "yes":
            await self.bot.db.execute("UPDATE active_bets SET pool_yes = pool_yes + ? WHERE message_id = ?", (amount, self.bet_id))
        else:
            await self.bot.db.execute("UPDATE active_bets SET pool_no = pool_no + ? WHERE message_id = ?", (amount, self.bet_id))
            
        await self.bot.db.commit()

        # Re-fetch pools to update embed
        async with self.bot.db.execute("SELECT pool_yes, pool_no FROM active_bets WHERE message_id = ?", (self.bet_id,)) as cursor:
            pools = await cursor.fetchone()
        
        pool_y = pools[0]
        pool_n = pools[1]
        
        embed = interaction.message.embeds[0]
        embed.set_footer(text=f"Pools -> YES: ${pool_y} | NO: ${pool_n}")
        await interaction.message.edit(embed=embed)
        
        await interaction.response.send_message(f"✅ You bet **${amount}** on **{self.choice.upper()}**!", ephemeral=True)

class BetView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Bet YES", style=discord.ButtonStyle.success, custom_id="bet_btn_yes")
    async def bet_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal(self.bot, "yes", interaction.message.id))

    @discord.ui.button(label="Bet NO", style=discord.ButtonStyle.danger, custom_id="bet_btn_no")
    async def bet_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal(self.bot, "no", interaction.message.id))

class Sportsbook(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(BetView(self.bot))

    @commands.hybrid_group(invoke_without_command=True, description="Manage custom bets and predictions.")
    async def bet(self, ctx):
        await ctx.send("Use `/bet create` or `/bet resolve`.")

    @bet.command(name="create", description="Create a custom bet (Streamers/Admins).")
    @discord.app_commands.default_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    async def create(self, ctx, *, question: str):
        embed = discord.Embed(title="🎲 New Prediction Started!", description=f"**{question}**\n\nClick the buttons below to place your bets!", color=discord.Color.purple())
        embed.set_footer(text="Pools -> YES: $0 | NO: $0")
        msg = await ctx.send(embed=embed, view=BetView(self.bot))
        
        # Save to DB
        await self.bot.db.execute("INSERT INTO active_bets (message_id, guild_id, question, status) VALUES (?, ?, ?, 'open')", 
                                  (msg.id, ctx.guild.id, question))
        await self.bot.db.commit()

    async def bet_autocomplete(self, interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
        async with self.bot.db.execute("SELECT message_id, question FROM active_bets WHERE guild_id = ? AND status = 'open'", (interaction.guild.id,)) as cursor:
            bets = await cursor.fetchall()
            
        choices = []
        for b_id, question in bets:
            q_trunc = (question[:85] + '...') if len(question) > 85 else question
            if current.lower() in q_trunc.lower() or current in str(b_id):
                choices.append(discord.app_commands.Choice(name=f"{q_trunc}", value=str(b_id)))
                
        return choices[:25]

    @bet.command(name="resolve", description="Resolve a bet and payout winners.")
    @discord.app_commands.default_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @discord.app_commands.autocomplete(message_id=bet_autocomplete)
    async def resolve(self, ctx, message_id: str, winning_choice: str):
        try:
            bet_id = int(message_id)
        except ValueError:
            await ctx.send("Invalid message ID.")
            return

        winning_choice = winning_choice.lower()
        if winning_choice not in ["yes", "no", "cancel"]:
            await ctx.send("Winning choice must be `yes`, `no`, or `cancel`.")
            return

        async with self.bot.db.execute("SELECT question, pool_yes, pool_no FROM active_bets WHERE message_id = ? AND status = 'open'", (bet_id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            await ctx.send("Active bet not found or already closed.")
            return
            
        question, pool_yes, pool_no = row
        total_pool = pool_yes + pool_no

        if winning_choice == "cancel":
            # Refund
            async with self.bot.db.execute("SELECT user_id, amount FROM bet_entries WHERE message_id = ?", (bet_id,)) as cursor:
                entries = await cursor.fetchall()
            for u_id, amt in entries:
                await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, u_id))
            await ctx.send(f"Prediction cancelled. All coins refunded for bet ID: {bet_id}")
        else:
            # Payout
            winning_pool = pool_yes if winning_choice == "yes" else pool_no
            if winning_pool == 0:
                await ctx.send("No one bet on the winning side. Coins burned!")
            else:
                multiplier = total_pool / winning_pool
                async with self.bot.db.execute("SELECT user_id, amount FROM bet_entries WHERE message_id = ? AND choice = ?", (bet_id, winning_choice)) as cursor:
                    winners = await cursor.fetchall()
                for u_id, amt in winners:
                    winnings = int(amt * multiplier)
                    await self.bot.db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (winnings, u_id))
                await ctx.send(f"🎉 Prediction Resolved! **{winning_choice.upper()}** won. Payout multiplier: **{multiplier:.2f}x**!")

        await self.bot.db.execute("UPDATE active_bets SET status = 'closed' WHERE message_id = ?", (bet_id,))
        await self.bot.db.commit()
        
        # Try to edit the original message to remove buttons and show closed status
        try:
            msg = await ctx.channel.fetch_message(bet_id)
            embed = msg.embeds[0]
            embed.title = "🎲 Prediction Closed!"
            embed.color = discord.Color.red()
            await msg.edit(embed=embed, view=None)
        except:
            pass

async def setup(bot):
    await bot.add_cog(Sportsbook(bot))
