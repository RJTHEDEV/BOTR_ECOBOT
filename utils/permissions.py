import discord
from discord.ext import commands

async def is_bot_admin(ctx):
    # Always allow server owner or user with explicit Administrator permission
    if ctx.author.id == ctx.guild.owner_id or ctx.author.guild_permissions.administrator:
        return True

    # Check database for custom bot admin role
    async with ctx.bot.db.execute("SELECT bot_admin_role_id FROM guild_settings WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
        row = await cursor.fetchone()
        
    if row and row[0]:
        admin_role_id = row[0]
        if discord.utils.get(ctx.author.roles, id=admin_role_id):
            return True

    # If all checks fail, raise standard error which will be caught by our global error handler
    raise commands.MissingPermissions(["Administrator or Custom Bot Admin Role"])

def has_bot_admin():
    """
    Decorator for commands that require the custom Bot Admin role or server Administrator permission.
    """
    return commands.check(is_bot_admin)
