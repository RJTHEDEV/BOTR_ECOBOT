import discord
from discord.ext import commands

class OptionsMath(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(invoke_without_command=True, description="Options trading calculators.")
    async def options(self, ctx):
        await ctx.send("Use `/options straddle`, `/options strangle`, or `/options call`.")

    @options.command(name="straddle", description="Calculate breakevens for a Long Straddle.")
    async def straddle(self, ctx, strike: float, call_premium: float, put_premium: float):
        total_cost = call_premium + put_premium
        upper_be = strike + total_cost
        lower_be = strike - total_cost
        
        embed = discord.Embed(title="📊 Long Straddle Calculator", color=discord.Color.blue())
        embed.description = "A straddle involves buying a call and a put at the same strike price."
        embed.add_field(name="Strike Price", value=f"${strike:.2f}", inline=True)
        embed.add_field(name="Total Debit", value=f"${total_cost:.2f} ($cost * 100)", inline=True)
        embed.add_field(name="Max Risk", value=f"${total_cost:.2f}", inline=True)
        
        embed.add_field(name="Lower Breakeven", value=f"${lower_be:.2f}", inline=True)
        embed.add_field(name="Upper Breakeven", value=f"${upper_be:.2f}", inline=True)
        embed.add_field(name="Strategy", value="Needs high volatility to break even.", inline=False)
        
        await ctx.send(embed=embed)

    @options.command(name="call", description="Calculate breakeven for a Long Call.")
    async def call(self, ctx, strike: float, premium: float):
        breakeven = strike + premium
        
        embed = discord.Embed(title="📈 Long Call Calculator", color=discord.Color.green())
        embed.add_field(name="Strike Price", value=f"${strike:.2f}", inline=True)
        embed.add_field(name="Debit (Risk)", value=f"${premium:.2f}", inline=True)
        embed.add_field(name="Breakeven", value=f"${breakeven:.2f}", inline=False)
        embed.add_field(name="Strategy", value="Bullish. Profit is theoretically unlimited above breakeven.", inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(OptionsMath(bot))
