import discord
from discord.ext import commands

class VoiceMaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_channels = set() # Store channel IDs in memory (safe because they delete anyway)

    @commands.hybrid_command(description="Setup VoiceMaster (Admin only).")
    @commands.has_permissions(administrator=True)
    async def setup_voicemaster(self, ctx):
        category = await ctx.guild.create_category("Temp Voice Channels")
        vc = await category.create_voice_channel("➕ Join to Create")
        
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS voicemaster (
                guild_id INTEGER PRIMARY KEY,
                category_id INTEGER,
                generator_vc_id INTEGER
            )
        """)
        
        await self.bot.db.execute("""
            INSERT OR REPLACE INTO voicemaster (guild_id, category_id, generator_vc_id)
            VALUES (?, ?, ?)
        """, (ctx.guild.id, category.id, vc.id))
        await self.bot.db.commit()
        
        await ctx.send(f"✅ VoiceMaster setup! Users can join {vc.mention} to get their own private voice channel.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Handle joining the generator channel
        if after.channel:
            async with self.bot.db.execute("SELECT category_id, generator_vc_id FROM voicemaster WHERE guild_id = ?", (member.guild.id,)) as cursor:
                row = await cursor.fetchone()
                
            if row and after.channel.id == row[1]:
                category = member.guild.get_channel(row[0])
                if category:
                    try:
                        # Create private channel
                        new_channel = await category.create_voice_channel(f"🔊 {member.display_name}'s Channel")
                        await member.move_to(new_channel)
                        self.temp_channels.add(new_channel.id)
                    except Exception as e:
                        print(f"Failed to create temp VC: {e}")

        # Handle leaving temp channels
        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="Temp channel empty")
                    self.temp_channels.remove(before.channel.id)
                except: pass

async def setup(bot):
    await bot.add_cog(VoiceMaster(bot))
