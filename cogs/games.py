import discord
from discord.ext import commands
import random
import asyncio

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToe = self.view
        state = view.board[self.y][self.x]
        if state in (view.X, view.O):
            return

        if view.current_player == view.X:
            self.style = discord.ButtonStyle.danger
            self.label = 'X'
            self.disabled = True
            view.board[self.y][self.x] = view.X
            view.current_player = view.O
            content = f"It is now {view.o_user.mention}'s turn"
        else:
            self.style = discord.ButtonStyle.success
            self.label = 'O'
            self.disabled = True
            view.board[self.y][self.x] = view.O
            view.current_player = view.X
            content = f"It is now {view.x_user.mention}'s turn"

        winner = view.check_winner()
        if winner is not None:
            if winner == view.X:
                content = f"{view.x_user.mention} won!"
            elif winner == view.O:
                content = f"{view.o_user.mention} won!"
            else:
                content = "It's a tie!"

            for child in view.children:
                child.disabled = True

            view.stop()

        await interaction.response.edit_message(content=content, view=view)

class TicTacToe(discord.ui.View):
    X = -1
    O = 1
    Tie = 2

    def __init__(self, x_user, o_user):
        super().__init__()
        self.x_user = x_user
        self.o_user = o_user
        self.current_player = x_user
        self.board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]

        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_winner(self):
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] != 0:
                return self.board[i][0]
            if self.board[0][i] == self.board[1][i] == self.board[2][i] != 0:
                return self.board[0][i]

        if self.board[0][0] == self.board[1][1] == self.board[2][2] != 0:
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != 0:
            return self.board[0][2]

        if all(i != 0 for row in self.board for i in row):
            return self.Tie

        return None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.current_player:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return False
        return True

class Connect4Button(discord.ui.Button):
    def __init__(self, column):
        super().__init__(style=discord.ButtonStyle.primary, label=f"{column+1}", row=0)
        self.column = column

    async def callback(self, interaction: discord.Interaction):
        view: Connect4 = self.view
        
        # Drop logic
        row_idx = -1
        for r in range(5, -1, -1):
            if view.board[r][self.column] == 0:
                row_idx = r
                break
        
        if row_idx == -1:
            return await interaction.response.send_message("Column is full!", ephemeral=True)

        view.board[row_idx][self.column] = view.turn
        
        # Check Win
        if view.check_win(view.turn):
            winner = view.p1 if view.turn == 1 else view.p2
            view.game_over = True
            await interaction.response.edit_message(content=f"🎉 {winner.mention} wins!", embed=view.render_board(), view=None)
            view.stop()
            return
            
        # Check Draw
        if all(view.board[0][c] != 0 for c in range(7)):
            view.game_over = True
            await interaction.response.edit_message(content="🤝 It's a draw!", embed=view.render_board(), view=None)
            view.stop()
            return

        # Switch Turn
        view.turn = 2 if view.turn == 1 else 1
        current_player = view.p1 if view.turn == 1 else view.p2
        await interaction.response.edit_message(content=f"🔴 {view.p1.mention} vs 🟡 {view.p2.mention}\nCurrent Turn: {current_player.mention}", embed=view.render_board(), view=view)

class Connect4(discord.ui.View):
    def __init__(self, p1, p2):
        super().__init__(timeout=300)
        self.p1 = p1
        self.p2 = p2
        self.turn = 1 # 1=Red, 2=Yellow
        self.board = [[0]*7 for _ in range(6)]
        self.game_over = False
        
        for i in range(7):
            self.add_item(Connect4Button(i))

    def render_board(self):
        desc = ""
        for row in self.board:
            for cell in row:
                if cell == 0: desc += "⚫"
                elif cell == 1: desc += "🔴"
                elif cell == 2: desc += "🟡"
            desc += "\n"
        desc += "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣"
        return discord.Embed(title="Connect 4", description=desc, color=discord.Color.blue())

    def check_win(self, player):
        # Horizontal
        for c in range(4):
            for r in range(6):
                if self.board[r][c] == player and self.board[r][c+1] == player and self.board[r][c+2] == player and self.board[r][c+3] == player:
                    return True
        # Vertical
        for c in range(7):
            for r in range(3):
                if self.board[r][c] == player and self.board[r+1][c] == player and self.board[r+2][c] == player and self.board[r+3][c] == player:
                    return True
        # Diagonal /
        for c in range(4):
            for r in range(3, 6):
                if self.board[r][c] == player and self.board[r-1][c+1] == player and self.board[r-2][c+2] == player and self.board[r-3][c+3] == player:
                    return True
        # Diagonal \
        for c in range(4):
            for r in range(3):
                if self.board[r][c] == player and self.board[r+1][c+1] == player and self.board[r+2][c+2] == player and self.board[r+3][c+3] == player:
                    return True
        return False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        current_player = self.p1 if self.turn == 1 else self.p2
        if interaction.user != current_player:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return False
        return True

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="8ball", description="Ask the Magic 8 Ball a question.")
    async def magic8ball(self, ctx, *, question: str):
        responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes definitely.",
            "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
            "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
            "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.",
            "Outlook not so good.", "Very doubtful."
        ]
        embed = discord.Embed(title="🎱 Magic 8 Ball", color=discord.Color.dark_theme())
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=random.choice(responses), inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Play Tic-Tac-Toe with another user.")
    async def tictactoe(self, ctx, opponent: discord.Member):
        if opponent.bot or opponent == ctx.author:
            await ctx.send("You cannot play against bots or yourself.")
            return

        await ctx.send(f"Tic-Tac-Toe: {ctx.author.mention} (X) vs {opponent.mention} (O)", view=TicTacToe(ctx.author, opponent))

    @commands.hybrid_command(description="Play Connect 4 with another user.")
    async def connect4(self, ctx, opponent: discord.Member):
        if opponent.bot or opponent == ctx.author:
            await ctx.send("You cannot play against bots or yourself.")
            return

        game = Connect4(ctx.author, opponent)
        await ctx.send(f"🔴 {ctx.author.mention} vs 🟡 {opponent.mention}\nCurrent Turn: {ctx.author.mention}", embed=game.render_board(), view=game)

async def setup(bot):
    await bot.add_cog(Games(bot))
