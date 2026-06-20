import discord
from discord.ext import commands, tasks
import shutil
import os
import datetime

class Maintenance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_task.start()

    def cog_unload(self):
        self.backup_task.cancel()

    @tasks.loop(hours=12)
    async def backup_task(self):
        """Backs up the database every 12 hours."""
        if not os.path.exists("data/backups"):
            os.makedirs("data/backups")
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = f"data/backups/bot_{timestamp}.db"
        
        try:
            # Safely copy the DB
            shutil.copy2("data/bot.db", backup_path)
            print(f"Database backed up to {backup_path}")
            
            # Clean up old backups (keep last 10)
            backups = sorted([f for f in os.listdir("data/backups") if f.endswith(".db")])
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    os.remove(os.path.join("data/backups", old_backup))
                    print(f"Removed old backup: {old_backup}")
        except Exception as e:
            print(f"Failed to backup database: {e}")

    @backup_task.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(description="Manually trigger a database backup.")
    @discord.app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def backup(self, ctx):
        await ctx.defer(ephemeral=True)
        if not os.path.exists("data/backups"):
            os.makedirs("data/backups")
            
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = f"data/backups/bot_manual_{timestamp}.db"
        
        try:
            shutil.copy2("data/bot.db", backup_path)
            await ctx.send(f"✅ Database manually backed up to `{backup_path}`", ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ Failed to backup database: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Maintenance(bot))
