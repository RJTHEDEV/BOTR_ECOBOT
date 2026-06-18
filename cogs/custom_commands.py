import discord
from discord.ext import commands

class CustomCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="customcmd", invoke_without_command=True, description="Manage custom commands/auto-responders.")
    @commands.has_permissions(administrator=True)
    async def customcmd(self, ctx):
        await ctx.send("Use `/customcmd add <trigger> <response>`, `/customcmd remove`, or `/customcmd list`.")

    @customcmd.command(name="add", description="Add a new custom command.")
    @commands.has_permissions(administrator=True)
    async def add_cmd(self, ctx, trigger: str, *, response: str):
        trigger = trigger.lower().strip()
        await self.bot.db.execute("INSERT INTO custom_commands (guild_id, trigger, response) VALUES (?, ?, ?)", (ctx.guild.id, trigger, response))
        await self.bot.db.commit()
        await ctx.send(f"✅ Added custom command. When someone says `{trigger}`, I will reply with the response.")

    @customcmd.command(name="remove", description="Remove a custom command.")
    @commands.has_permissions(administrator=True)
    async def remove_cmd(self, ctx, trigger: str):
        trigger = trigger.lower().strip()
        await self.bot.db.execute("DELETE FROM custom_commands WHERE guild_id = ? AND trigger = ?", (ctx.guild.id, trigger))
        await self.bot.db.commit()
        await ctx.send(f"✅ Removed custom command `{trigger}`.")

    @customcmd.command(name="list", description="List all custom commands.")
    @commands.has_permissions(administrator=True)
    async def list_cmds(self, ctx):
        async with self.bot.db.execute("SELECT trigger, response FROM custom_commands WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
            rows = await cursor.fetchall()
            
        if not rows:
            await ctx.send("No custom commands found for this server.")
            return

        embed = discord.Embed(title="📜 Custom Commands", color=discord.Color.blue())
        for trigger, response in rows:
            embed.add_field(name=trigger, value=response[:1024], inline=False)
            
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild: return
        
        # We don't want to conflict with actual commands, but these are exact triggers.
        content = message.content.lower().strip()
        
        async with self.bot.db.execute("SELECT response FROM custom_commands WHERE guild_id = ? AND trigger = ?", (message.guild.id, content)) as cursor:
            row = await cursor.fetchone()
            
        if row:
            try:
                await message.channel.send(row[0])
            except: pass

async def setup(bot):
    await bot.add_cog(CustomCommands(bot))
