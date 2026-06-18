import discord
from discord.ext import commands

class CopyTrading(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(invoke_without_command=True, description="Manage copy trading subscriptions.")
    async def copytrade(self, ctx):
        await ctx.send("Use `/copytrade subscribe <user>` or `/copytrade unsubscribe <user>`.")

    @copytrade.command(name="subscribe", description="Subscribe to automatically mirror a user's paper trades.")
    async def subscribe(self, ctx, target: discord.Member):
        if target.id == ctx.author.id:
            await ctx.send("You cannot copy trade yourself.")
            return

        await self.bot.db.execute("INSERT OR IGNORE INTO copy_trades (follower_id, target_id) VALUES (?, ?)", 
                                  (ctx.author.id, target.id))
        await self.bot.db.commit()
        await ctx.send(f"📈 You are now copy trading **{target.display_name}**. When they use `/tbuy` or `/tsell`, you will automatically do the same if you have the funds!")

    @copytrade.command(name="unsubscribe", description="Unsubscribe from a user's paper trades.")
    async def unsubscribe(self, ctx, target: discord.Member):
        await self.bot.db.execute("DELETE FROM copy_trades WHERE follower_id = ? AND target_id = ?", 
                                  (ctx.author.id, target.id))
        await self.bot.db.commit()
        await ctx.send(f"🛑 You are no longer copy trading **{target.display_name}**.")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if ctx.author.bot: return
        cmd = ctx.command.name if ctx.command else ""
        
        if cmd in ["tbuy", "tsell"]:
            # Check if anyone is copying this user
            async with self.bot.db.execute("SELECT follower_id FROM copy_trades WHERE target_id = ?", (ctx.author.id,)) as cursor:
                followers = await cursor.fetchall()
                
            if not followers: return
            
            # Extract arguments
            ticker = ctx.kwargs.get("ticker", "")
            shares = ctx.kwargs.get("shares", 0)
            
            if not ticker or shares <= 0: return
            
            # Execute trade for each follower by re-invoking the command programmatically
            # Note: For security/safety, we fetch the PaperTrading cog directly and call its inner logic, 
            # but invoking commands programmatically is tricky.
            # Instead, we just lookup the PaperTrading cog and call the method directly with a fake context.
            paper_cog = self.bot.get_cog("PaperTrading")
            if not paper_cog: return

            for (follower_id,) in followers:
                follower = ctx.guild.get_member(follower_id)
                if not follower: continue
                
                # We need to simulate a context for the follower.
                # A robust way is to just send a message to the channel or DM them, but the logic inside tbuy requires a context.
                # Since ctx is required, let's just create a modified copy of the context.
                import copy
                fake_ctx = copy.copy(ctx)
                fake_ctx.author = follower
                
                try:
                    if cmd == "tbuy":
                        await paper_cog.tbuy(fake_ctx, ticker=ticker, shares=shares)
                    elif cmd == "tsell":
                        await paper_cog.tsell(fake_ctx, ticker=ticker, shares=shares)
                except Exception as e:
                    print(f"Copy trade error for {follower.display_name}: {e}")

async def setup(bot):
    await bot.add_cog(CopyTrading(bot))
