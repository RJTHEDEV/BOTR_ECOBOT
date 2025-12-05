import discord
from discord.ext import commands
import asyncio

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="voice", description="Manage voice channels.")
    async def voice(self, ctx):
        pass

    @voice.command(name="setup", description="Set a voice channel as a 'Join to Create' hub.")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx, channel: discord.VoiceChannel, name_template: str = "{user}'s Channel"):
        """
        Set a voice channel as a hub.
        name_template: Use {user} for the username.
        """
        await self.bot.db.execute("INSERT OR REPLACE INTO voice_hubs (guild_id, channel_id, category_id, name_template) VALUES (?, ?, ?, ?)",
                                  (ctx.guild.id, channel.id, channel.category_id, name_template))
        await self.bot.db.commit()
        await ctx.send(f"✅ Set {channel.mention} as a Voice Hub.\nTemplate: `{name_template}`")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return

        # 1. Check if joined a Hub
        if after.channel:
            async with self.bot.db.execute("SELECT category_id, name_template FROM voice_hubs WHERE channel_id = ?", (after.channel.id,)) as cursor:
                hub = await cursor.fetchone()
            
            if hub:
                category_id, name_template = hub
                category = member.guild.get_channel(category_id)
                
                # Create Name
                channel_name = name_template.replace("{user}", member.display_name)
                
                # Create Channel
                overwrites = {
                    member.guild.default_role: discord.PermissionOverwrite(connect=True),
                    member: discord.PermissionOverwrite(connect=True, manage_channels=True)
                }
                
                try:
                    new_channel = await member.guild.create_voice_channel(name=channel_name, category=category, overwrites=overwrites)
                    
                    # Move Member
                    await member.move_to(new_channel)
                    
                    # Track Temp Channel
                    await self.bot.db.execute("INSERT INTO temp_channels (channel_id, owner_id) VALUES (?, ?)", (new_channel.id, member.id))
                    await self.bot.db.commit()
                except Exception as e:
                    print(f"Error creating voice channel: {e}")

        # 2. Check if left a Temp Channel
        if before.channel:
            # Check if it's a temp channel
            async with self.bot.db.execute("SELECT 1 FROM temp_channels WHERE channel_id = ?", (before.channel.id,)) as cursor:
                is_temp = await cursor.fetchone()
            
            if is_temp:
                # Check if empty
                if len(before.channel.members) == 0:
                    try:
                        await before.channel.delete()
                        await self.bot.db.execute("DELETE FROM temp_channels WHERE channel_id = ?", (before.channel.id,))
                        await self.bot.db.commit()
                    except:
                        pass

async def setup(bot):
    await bot.add_cog(Voice(bot))
