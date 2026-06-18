import discord
from discord.ext import commands, tasks
import aiohttp
import xml.etree.ElementTree as ET

class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_youtube.start()

    def cog_unload(self):
        self.check_youtube.cancel()

    @commands.hybrid_group(name="notify", description="Setup automated notifications for content creators.")
    @commands.has_permissions(administrator=True)
    async def notify(self, ctx):
        pass

    @notify.command(name="youtube", description="Add a YouTube channel to post notifications for.")
    @commands.has_permissions(administrator=True)
    async def add_youtube(self, ctx, channel_id: str, discord_channel: discord.TextChannel, custom_message: str = "@everyone"):
        """
        Add a YouTube channel.
        To get the channel ID, go to their channel, and it's the ID starting with UC in the URL.
        """
        if not channel_id.startswith("UC"):
            await ctx.send("❌ Please provide a valid YouTube Channel ID (It should start with 'UC').\n*Example:* `UCX6OQ3DkcsbYNE6H8uQQuVA`", ephemeral=True)
            return

        async with self.bot.db.execute("SELECT id FROM youtube_alerts WHERE guild_id = ? AND youtube_channel_id = ?", (ctx.guild.id, channel_id)) as cursor:
            if await cursor.fetchone():
                await ctx.send("❌ This channel is already being monitored in this server!", ephemeral=True)
                return

        # Fetch latest video immediately to set the baseline
        last_video_id = ""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        root = ET.fromstring(text)
                        # Find the first entry
                        ns = {'atom': 'http://www.w3.org/2005/Atom'}
                        entry = root.find('atom:entry', ns)
                        if entry is not None:
                            last_video_id = entry.find('atom:id', ns).text.replace('yt:video:', '')
        except Exception as e:
            print(f"Error fetching initial youtube feed: {e}")

        await self.bot.db.execute(
            "INSERT INTO youtube_alerts (guild_id, channel_id, youtube_channel_id, last_video_id, custom_message) VALUES (?, ?, ?, ?, ?)",
            (ctx.guild.id, discord_channel.id, channel_id, last_video_id, custom_message)
        )
        await self.bot.db.commit()

        embed = discord.Embed(title="✅ YouTube Alerts Added", color=discord.Color.red())
        embed.description = f"Successfully set up notifications for Channel ID `{channel_id}`!\nWhenever they upload, I'll post in {discord_channel.mention}."
        await ctx.send(embed=embed)

    @notify.command(name="remove_youtube", description="Stop monitoring a YouTube channel.")
    @commands.has_permissions(administrator=True)
    async def remove_youtube(self, ctx, channel_id: str):
        await self.bot.db.execute("DELETE FROM youtube_alerts WHERE guild_id = ? AND youtube_channel_id = ?", (ctx.guild.id, channel_id))
        await self.bot.db.commit()
        await ctx.send(f"✅ Removed `{channel_id}` from alerts.")

    @tasks.loop(minutes=5.0)
    async def check_youtube(self):
        # Wait until bot is ready
        await self.bot.wait_until_ready()
        
        try:
            async with self.bot.db.execute("SELECT id, guild_id, channel_id, youtube_channel_id, last_video_id, custom_message FROM youtube_alerts") as cursor:
                alerts = await cursor.fetchall()
                
            if not alerts: return
            
            async with aiohttp.ClientSession() as session:
                for alert in alerts:
                    db_id, guild_id, discord_channel_id, yt_channel_id, db_last_video_id, custom_message = alert
                    
                    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={yt_channel_id}"
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            continue
                        text = await resp.text()
                        
                    root = ET.fromstring(text)
                    ns = {
                        'atom': 'http://www.w3.org/2005/Atom',
                        'media': 'http://search.yahoo.com/mrss/'
                    }
                    
                    # Get author name
                    author = root.find('atom:author/atom:name', ns)
                    author_name = author.text if author is not None else "YouTube Creator"
                    
                    entry = root.find('atom:entry', ns)
                    if entry is None: continue
                        
                    video_id = entry.find('atom:id', ns).text.replace('yt:video:', '')
                    
                    if video_id != db_last_video_id:
                        # NEW VIDEO DETECTED!
                        title = entry.find('atom:title', ns).text
                        link = entry.find('atom:link', ns).attrib['href']
                        
                        media_group = entry.find('media:group', ns)
                        thumbnail_url = ""
                        if media_group is not None:
                            thumbnail = media_group.find('media:thumbnail', ns)
                            if thumbnail is not None:
                                thumbnail_url = thumbnail.attrib['url']
                                
                        # Update DB
                        await self.bot.db.execute("UPDATE youtube_alerts SET last_video_id = ? WHERE id = ?", (video_id, db_id))
                        await self.bot.db.commit()
                        
                        # Post to discord
                        channel = self.bot.get_channel(discord_channel_id)
                        if channel:
                            embed = discord.Embed(title=title, url=link, color=discord.Color.red())
                            embed.set_author(name=author_name, icon_url="https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo_2015.jpg")
                            if thumbnail_url:
                                embed.set_image(url=thumbnail_url)
                                
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(label="Watch Video", style=discord.ButtonStyle.link, url=link))
                            
                            content = f"{custom_message}\n**{author_name}** just posted a new video!"
                            await channel.send(content=content, embed=embed, view=view)
                            
        except Exception as e:
            print(f"Error in youtube alert loop: {e}")

async def setup(bot):
    await bot.add_cog(Notifications(bot))
