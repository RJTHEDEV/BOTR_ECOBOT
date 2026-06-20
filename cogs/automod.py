import discord
from discord.ext import commands
import re
import datetime

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_cache = {} # {user_id: [(timestamp, msg_content), ...]}

    @commands.hybrid_group(invoke_without_command=True, description="Configure AutoMod settings.")
    @discord.app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def automod(self, ctx):
        await ctx.send("Use `/automod view`, `/automod blockword`, or `/automod removeword`.")

    @automod.command(name="view", description="View AutoMod configuration.")
    @discord.app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def view_settings(self, ctx):
        async with self.bot.db.execute("SELECT banned_words, anti_spam, anti_caps, punishment FROM automod_settings WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await self.bot.db.execute("INSERT INTO automod_settings (guild_id) VALUES (?)", (ctx.guild.id,))
            await self.bot.db.commit()
            row = (None, 1, 1, 'warn')
            
        banned_words, anti_spam, anti_caps, punishment = row
        words_list = banned_words.split(",") if banned_words else ["None"]

        embed = discord.Embed(title="🛡️ AutoMod Settings", color=discord.Color.red())
        embed.add_field(name="Anti-Spam", value="Enabled" if anti_spam else "Disabled", inline=True)
        embed.add_field(name="Anti-Caps", value="Enabled" if anti_caps else "Disabled", inline=True)
        embed.add_field(name="Punishment", value=punishment.title(), inline=True)
        embed.add_field(name="Banned Words", value=", ".join(words_list)[:1000] if words_list else "None", inline=False)
        
        await ctx.send(embed=embed)

    @automod.command(name="blockword", description="Add a word to the banned words filter.")
    @discord.app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def blockword(self, ctx, word: str):
        word = word.lower().strip()
        async with self.bot.db.execute("SELECT banned_words FROM automod_settings WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
            row = await cursor.fetchone()
            
        words = row[0].split(",") if row and row[0] else []
        if word in words:
            await ctx.send(f"`{word}` is already blocked.")
            return
            
        words.append(word)
        new_words = ",".join(words)
        
        await self.bot.db.execute("""
            INSERT INTO automod_settings (guild_id, banned_words) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET banned_words=excluded.banned_words
        """, (ctx.guild.id, new_words))
        await self.bot.db.commit()
        await ctx.send(f"✅ Added `{word}` to blocked words.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild: return
        
        # Don't automod admins
        if message.author.guild_permissions.administrator: return

        async with self.bot.db.execute("SELECT banned_words, anti_spam, anti_caps, punishment FROM automod_settings WHERE guild_id = ?", (message.guild.id,)) as cursor:
            row = await cursor.fetchone()
        
        if not row: return
        banned_words, anti_spam, anti_caps, punishment = row
        
        content = message.content.lower()
        
        # 1. Banned Words Check
        if banned_words:
            words = banned_words.split(",")
            for word in words:
                if word in content:
                    await message.delete()
                    await self._punish(message.author, message.guild, "Using banned words", punishment)
                    try:
                        await message.channel.send(f"⚠️ {message.author.mention}, your message contained a banned word.", delete_after=5)
                    except: pass
                    return

        # 2. Anti-Caps Check (if > 10 chars and > 70% caps)
        if anti_caps and len(message.content) > 10:
            caps = sum(1 for c in message.content if c.isupper())
            if caps / len(message.content) > 0.7:
                await message.delete()
                try:
                    await message.channel.send(f"⚠️ {message.author.mention}, please don't use excessive caps.", delete_after=5)
                except: pass
                return

    async def _punish(self, member, guild, reason, punishment_type):
        # Delegate punishment to the moderation cog if possible
        mod_cog = self.bot.get_cog("Moderation")
        if mod_cog and punishment_type == "warn":
            await mod_cog.add_infraction(member, member.guild.me, "warn", f"AutoMod: {reason}")
        elif punishment_type == "mute":
            # Just add a timeout
            try:
                duration = datetime.timedelta(minutes=10)
                await member.timeout(duration, reason=f"AutoMod: {reason}")
            except: pass

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
