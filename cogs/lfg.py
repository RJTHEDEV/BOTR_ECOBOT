import discord
from discord.ext import commands

class LFGView(discord.ui.View):
    def __init__(self, needed):
        super().__init__(timeout=None)
        self.needed = needed
        self.players = []

    @discord.ui.button(label="Join Group", style=discord.ButtonStyle.green, custom_id="lfg_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.players:
            await interaction.response.send_message("You are already in the group!", ephemeral=True)
            return

        self.players.append(interaction.user.id)
        
        embed = interaction.message.embeds[0]
        players_mentions = "\n".join([f"<@{pid}>" for pid in self.players])
        embed.set_field_at(0, name=f"Players ({len(self.players)}/{self.needed})", value=players_mentions or "None yet", inline=False)
        
        if len(self.players) >= self.needed:
            embed.color = discord.Color.green()
            embed.title = "✅ Group Full! " + embed.title.replace("🔍 LFG: ", "")
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
            await interaction.channel.send(f"The group is full! Get ready: {', '.join([f'<@{pid}>' for pid in self.players])}")
        else:
            await interaction.response.edit_message(embed=embed, view=self)


class LFG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="Start a Looking For Group (LFG) request.")
    async def lfg(self, ctx, needed: int, *, game: str):
        if needed < 2:
            await ctx.send("You need at least 2 players for a group.")
            return

        embed = discord.Embed(title=f"🔍 LFG: {game}", description=f"Host: {ctx.author.mention}", color=discord.Color.blue())
        embed.add_field(name=f"Players (1/{needed})", value=ctx.author.mention, inline=False)
        
        view = LFGView(needed)
        view.players.append(ctx.author.id)
        
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(LFG(bot))
