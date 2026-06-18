import discord
from discord.ext import commands, tasks
import aiohttp
import xml.etree.ElementTree as ET

class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_youtube.start()
        self.check_twitch.start()

    def cog_unload(self):
        self.check_youtube.cancel()
        self.check_twitch.cancel()

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

    @notify.command(name="twitch", description="Add a Twitch streamer to post notifications for.")
    @commands.has_permissions(administrator=True)
    async def add_twitch(self, ctx, twitch_username: str, discord_channel: discord.TextChannel, custom_message: str = "@everyone"):
        async with self.bot.db.execute("SELECT id FROM twitch_alerts WHERE guild_id = ? AND twitch_username = ?", (ctx.guild.id, twitch_username.lower())) as cursor:
            if await cursor.fetchone():
                await ctx.send("❌ This Twitch channel is already being monitored in this server!", ephemeral=True)
                return

        await self.bot.db.execute(
            "INSERT INTO twitch_alerts (guild_id, channel_id, twitch_username, is_live, custom_message) VALUES (?, ?, ?, ?, ?)",
            (ctx.guild.id, discord_channel.id, twitch_username.lower(), 0, custom_message)
        )
        await self.bot.db.commit()

        embed = discord.Embed(title="✅ Twitch Alerts Added", color=discord.Color.purple())
        embed.description = f"Successfully set up notifications for `{twitch_username}`!\nWhenever they go live, I'll post in {discord_channel.mention}."
        embed.set_footer(text="Note: Requires TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in .env")
        await ctx.send(embed=embed)

    @notify.command(name="remove_twitch", description="Stop monitoring a Twitch streamer.")
    @commands.has_permissions(administrator=True)
    async def remove_twitch(self, ctx, twitch_username: str):
        await self.bot.db.execute("DELETE FROM twitch_alerts WHERE guild_id = ? AND twitch_username = ?", (ctx.guild.id, twitch_username.lower()))
        await self.bot.db.commit()
        await ctx.send(f"✅ Removed `{twitch_username}` from Twitch alerts.")

    @tasks.loop(minutes=3.0)
    async def check_twitch(self):
        import os
        client_id = os.getenv("TWITCH_CLIENT_ID")
        client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        
        if not client_id or not client_secret: return
        
        await self.bot.wait_until_ready()
        
        try:
            async with self.bot.db.execute("SELECT id, guild_id, channel_id, twitch_username, is_live, custom_message FROM twitch_alerts") as cursor:
                alerts = await cursor.fetchall()
                
            if not alerts: return
            
            async with aiohttp.ClientSession() as session:
                # 1. Get Access Token
                async with session.post(
                    "https://id.twitch.tv/oauth2/token",
                    params={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "grant_type": "client_credentials"
                    }
                ) as resp:
                    if resp.status != 200: return
                    token_data = await resp.json()
                    access_token = token_data.get("access_token")
                    
                if not access_token: return
                
                headers = {
                    "Client-ID": client_id,
                    "Authorization": f"Bearer {access_token}"
                }
                
                # We can batch requests, but for simplicity we'll loop
                for alert in alerts:
                    db_id, guild_id, discord_channel_id, twitch_username, db_is_live, custom_message = alert
                    
                    async with session.get(f"https://api.twitch.tv/helix/streams?user_login={twitch_username}", headers=headers) as resp:
                        if resp.status != 200: continue
                        data = await resp.json()
                        
                    stream_data = data.get("data", [])
                    is_live_now = 1 if len(stream_data) > 0 else 0
                    
                    if is_live_now and not db_is_live:
                        # WENT LIVE!
                        stream = stream_data[0]
                        title = stream.get("title", "No Title")
                        game = stream.get("game_name", "Just Chatting")
                        thumbnail_url = stream.get("thumbnail_url", "").replace("{width}", "1280").replace("{height}", "720")
                        viewer_count = stream.get("viewer_count", 0)
                        
                        await self.bot.db.execute("UPDATE twitch_alerts SET is_live = 1 WHERE id = ?", (db_id,))
                        await self.bot.db.commit()
                        
                        channel = self.bot.get_channel(discord_channel_id)
                        if channel:
                            url = f"https://twitch.tv/{twitch_username}"
                            embed = discord.Embed(title=title, url=url, color=discord.Color.purple())
                            embed.set_author(name=f"{twitch_username} is LIVE on Twitch!", icon_url="https://pngimg.com/uploads/twitch/twitch_PNG27.png")
                            embed.add_field(name="Playing", value=game, inline=True)
                            embed.add_field(name="Viewers", value=str(viewer_count), inline=True)
                            if thumbnail_url:
                                embed.set_image(url=thumbnail_url)
                                
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(label="Watch Stream", style=discord.ButtonStyle.link, url=url))
                            
                            content = f"{custom_message}\n**{twitch_username}** just went live playing **{game}**!"
                            await channel.send(content=content, embed=embed, view=view)
                            
                    elif not is_live_now and db_is_live:
                        # WENT OFFLINE
                        await self.bot.db.execute("UPDATE twitch_alerts SET is_live = 0 WHERE id = ?", (db_id,))
                        await self.bot.db.commit()
                        
        except Exception as e:
            print(f"Error in twitch alert loop: {e}")

async def setup(bot):
    await bot.add_cog(Notifications(bot))
