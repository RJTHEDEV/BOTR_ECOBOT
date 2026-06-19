import discord
from discord.ext import commands, tasks
import aiohttp
import xml.etree.ElementTree as ET
import json
import re
import os

class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_youtube.start()
        self.check_twitch.start()
        self.check_kick.start()
        self.check_tiktok.start()

    def cog_unload(self):
        self.check_youtube.cancel()
        self.check_twitch.cancel()
        self.check_kick.cancel()
        self.check_tiktok.cancel()

    @commands.hybrid_group(name="alerts", description="Setup automated notifications for content creators.")
    @commands.has_permissions(administrator=True)
    async def notify_group(self, ctx):
        pass

    async def _handle_live_role(self, guild_id, discord_user_id, add=True):
        if not discord_user_id: return
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild: return
            member = guild.get_member(discord_user_id)
            if not member:
                try:
                    member = await guild.fetch_member(discord_user_id)
                except:
                    return
            if not member: return
            
            async with self.bot.db.execute("SELECT role_id FROM live_roles WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if not row: return
                live_role = guild.get_role(row[0])
                if not live_role: return
                
            if add:
                await member.add_roles(live_role, reason="Streamer Alert Live Role")
            else:
                await member.remove_roles(live_role, reason="Streamer Alert Live Role")
        except Exception as e:
            print(f"Failed to handle live role for {discord_user_id}: {e}")

    @notify_group.command(name="list", description="List all active content alerts in this server.")
    @commands.has_permissions(administrator=True)
    async def list_alerts(self, ctx):
        embed = discord.Embed(title="📡 Active Server Alerts", color=discord.Color.blurple())
        
        async def fetch_alerts(table_name, name_col):
            async with self.bot.db.execute(f"SELECT {name_col}, channel_id FROM {table_name} WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                return await cursor.fetchall()

        # YouTube
        yt_alerts = await fetch_alerts('youtube_alerts', 'youtube_channel_id')
        if yt_alerts:
            lines = [f"• `{channel_id}` -> <#{discord_channel}>" for channel_id, discord_channel in yt_alerts]
            embed.add_field(name="YouTube Channels", value="\n".join(lines), inline=False)
            
        # Twitch
        tw_alerts = await fetch_alerts('twitch_alerts', 'twitch_username')
        if tw_alerts:
            lines = [f"• `{username}` -> <#{discord_channel}>" for username, discord_channel in tw_alerts]
            embed.add_field(name="Twitch Streamers", value="\n".join(lines), inline=False)
            
        # Kick
        kick_alerts = await fetch_alerts('kick_alerts', 'kick_username')
        if kick_alerts:
            lines = [f"• `{username}` -> <#{discord_channel}>" for username, discord_channel in kick_alerts]
            embed.add_field(name="Kick Streamers", value="\n".join(lines), inline=False)
            
        # TikTok
        tk_alerts = await fetch_alerts('tiktok_alerts', 'tiktok_username')
        if tk_alerts:
            lines = [f"• `@{username}` -> <#{discord_channel}>" for username, discord_channel in tk_alerts]
            embed.add_field(name="TikTok Creators", value="\n".join(lines), inline=False)
            
        if not len(embed.fields):
            embed.description = "No alerts are currently configured for this server."
            
        await ctx.send(embed=embed)

    @notify_group.command(name="youtube", description="Add a YouTube channel to post notifications for.")
    @commands.has_permissions(administrator=True)
    async def add_youtube(self, ctx, channel_id: str, discord_channel: discord.TextChannel, discord_user: discord.Member = None, custom_message: str = "@everyone"):
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
            "INSERT INTO youtube_alerts (guild_id, channel_id, youtube_channel_id, last_video_id, discord_user_id, custom_message) VALUES (?, ?, ?, ?, ?, ?)",
            (ctx.guild.id, discord_channel.id, channel_id, last_video_id, discord_user.id if discord_user else None, custom_message)
        )
        await self.bot.db.commit()

        embed = discord.Embed(title="✅ YouTube Alerts Added", color=discord.Color.red())
        embed.description = f"Successfully set up notifications for Channel ID `{channel_id}`!\nWhenever they upload, I'll post in {discord_channel.mention}."
        await ctx.send(embed=embed)

    @notify_group.command(name="remove_youtube", description="Stop monitoring a YouTube channel.")
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
            async with self.bot.db.execute("SELECT id, guild_id, channel_id, youtube_channel_id, last_video_id, discord_user_id, custom_message FROM youtube_alerts") as cursor:
                alerts = await cursor.fetchall()
                
            if not alerts: return
            
            async with aiohttp.ClientSession() as session:
                for alert in alerts:
                    db_id, guild_id, discord_channel_id, yt_channel_id, db_last_video_id, discord_user_id, custom_message = alert
                    
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
                        description = ""
                        
                        if media_group is not None:
                            thumbnail = media_group.find('media:thumbnail', ns)
                            if thumbnail is not None:
                                thumbnail_url = thumbnail.attrib['url']
                            
                            desc_elem = media_group.find('media:description', ns)
                            if desc_elem is not None and desc_elem.text:
                                description = desc_elem.text[:200] + "..." if len(desc_elem.text) > 200 else desc_elem.text

                        # Fetch channel avatar using YouTube Data API if available
                        avatar_url = "https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo_2015.jpg"
                        api_key = os.getenv("YOUTUBE_API_KEY")
                        if api_key:
                            try:
                                api_url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet&id={yt_channel_id}&key={api_key}"
                                async with session.get(api_url) as api_resp:
                                    if api_resp.status == 200:
                                        api_data = await api_resp.json()
                                        if api_data.get('items'):
                                            avatar_url = api_data['items'][0]['snippet']['thumbnails']['high']['url']
                            except Exception as e:
                                print(f"Failed to fetch YouTube avatar: {e}")

                        # Update DB
                        await self.bot.db.execute("UPDATE youtube_alerts SET last_video_id = ? WHERE id = ?", (video_id, db_id))
                        await self.bot.db.commit()
                        
                        # Post to discord
                        channel = self.bot.get_channel(discord_channel_id)
                        if channel:
                            embed = discord.Embed(
                                title=title, 
                                description=description,
                                url=link, 
                                color=0xFF0000,
                                timestamp=discord.utils.utcnow()
                            )
                            embed.set_author(name=author_name, icon_url=avatar_url, url=f"https://www.youtube.com/channel/{yt_channel_id}")
                            
                            if thumbnail_url:
                                embed.set_image(url=thumbnail_url)
                                
                            embed.set_footer(text="YouTube", icon_url="https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo_2015.jpg")
                                
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(label="Watch Video", style=discord.ButtonStyle.link, url=link))
                            view.add_item(discord.ui.Button(label="Channel", style=discord.ButtonStyle.link, url=f"https://www.youtube.com/channel/{yt_channel_id}"))
                            
                            if discord_user_id:
                                content = f"{custom_message}\n🎉 <@{discord_user_id}> just posted a new video!"
                            else:
                                content = f"{custom_message}\n🎉 **{author_name}** just posted a new video!"
                            await channel.send(content=content, embed=embed, view=view)
                            
        except Exception as e:
            print(f"Error in youtube alert loop: {e}")

    @notify_group.command(name="twitch", description="Add a Twitch streamer to post notifications for.")
    @commands.has_permissions(administrator=True)
    async def add_twitch(self, ctx, twitch_username: str, discord_channel: discord.TextChannel, discord_user: discord.Member = None, custom_message: str = "@everyone"):
        async with self.bot.db.execute("SELECT id FROM twitch_alerts WHERE guild_id = ? AND twitch_username = ?", (ctx.guild.id, twitch_username.lower())) as cursor:
            if await cursor.fetchone():
                await ctx.send("❌ This Twitch channel is already being monitored in this server!", ephemeral=True)
                return

        await self.bot.db.execute(
            "INSERT INTO twitch_alerts (guild_id, channel_id, twitch_username, is_live, discord_user_id, custom_message) VALUES (?, ?, ?, ?, ?, ?)",
            (ctx.guild.id, discord_channel.id, twitch_username.lower(), 0, discord_user.id if discord_user else None, custom_message)
        )
        await self.bot.db.commit()

        embed = discord.Embed(title="✅ Twitch Alerts Added", color=discord.Color.purple())
        embed.description = f"Successfully set up notifications for `{twitch_username}`!\nWhenever they go live, I'll post in {discord_channel.mention}."
        embed.set_footer(text="Note: Requires TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in .env")
        await ctx.send(embed=embed)

    @notify_group.command(name="remove_twitch", description="Stop monitoring a Twitch streamer.")
    @commands.has_permissions(administrator=True)
    async def remove_twitch(self, ctx, twitch_username: str):
        await self.bot.db.execute("DELETE FROM twitch_alerts WHERE guild_id = ? AND twitch_username = ?", (ctx.guild.id, twitch_username.lower()))
        await self.bot.db.commit()
        await ctx.send(f"✅ Removed `{twitch_username}` from Twitch alerts.")

    @notify_group.command(name="link_user", description="Link a Discord user to an existing alert (so they get pinged and get the Live role).")
    @commands.has_permissions(administrator=True)
    async def link_user(self, ctx, platform: str, streamer_username: str, discord_user: discord.Member):
        platform = platform.lower()
        if platform not in ["twitch", "youtube", "kick", "tiktok"]:
            await ctx.send("❌ Platform must be one of: twitch, youtube, kick, tiktok.", ephemeral=True)
            return
            
        table_map = {
            "twitch": "twitch_alerts",
            "youtube": "youtube_alerts",
            "kick": "kick_alerts",
            "tiktok": "tiktok_alerts"
        }
        
        table = table_map[platform]
        column = "twitch_username" if platform == "twitch" else "youtube_channel_id" if platform == "youtube" else "kick_username" if platform == "kick" else "tiktok_username"
        
        if platform == "youtube":
            await ctx.send("For YouTube, please enter their channel ID instead of their username.", ephemeral=True)
            # Keeping it simple, matching on the identifier
            
        # Check if the alert exists first
        async with self.bot.db.execute(f"SELECT id FROM {table} WHERE guild_id = ? AND {column} = ?", (ctx.guild.id, streamer_username.lower() if platform != 'youtube' else streamer_username)) as cursor:
            if not await cursor.fetchone():
                await ctx.send(f"❌ Could not find a `{platform}` alert for `{streamer_username}`. Make sure you set up the alert first!", ephemeral=True)
                return
                
        # Update it
        await self.bot.db.execute(
            f"UPDATE {table} SET discord_user_id = ? WHERE guild_id = ? AND {column} = ?",
            (discord_user.id, ctx.guild.id, streamer_username.lower() if platform != 'youtube' else streamer_username)
        )
        await self.bot.db.commit()
        await ctx.send(f"✅ Successfully linked {discord_user.mention} to the {platform.capitalize()} alert for `{streamer_username}`!\nThey will now be @-pinged and given the Auto-Live role when going live.")

    @tasks.loop(minutes=3.0)
    async def check_twitch(self):
        import os
        client_id = os.getenv("TWITCH_CLIENT_ID")
        client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        
        if not client_id or not client_secret: return
        
        await self.bot.wait_until_ready()
        
        try:
            async with self.bot.db.execute("SELECT id, guild_id, channel_id, twitch_username, is_live, discord_user_id, custom_message FROM twitch_alerts") as cursor:
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
                    db_id, guild_id, discord_channel_id, twitch_username, db_is_live, discord_user_id, custom_message = alert
                    
                    async with session.get(f"https://api.twitch.tv/helix/streams?user_login={twitch_username}", headers=headers) as resp:
                        if resp.status != 200: continue
                        data = await resp.json()
                        
                    stream_data = data.get("data", [])
                    is_live_now = 1 if len(stream_data) > 0 else 0
                    
                    if is_live_now and not db_is_live:
                        # WENT LIVE
                        await self._handle_live_role(guild_id, discord_user_id, add=True)
                        stream = stream_data[0]
                        title = stream.get("title", "No Title")
                        game = stream.get("game_name", "Just Chatting")
                        thumbnail_url = stream.get("thumbnail_url", "").replace("{width}", "1280").replace("{height}", "720")
                        viewer_count = stream.get("viewer_count", 0)
                        
                        await self.bot.db.execute("UPDATE twitch_alerts SET is_live = 1 WHERE id = ?", (db_id,))
                        await self.bot.db.commit()
                        
                        # Fetch user profile image
                        profile_image_url = "https://pngimg.com/uploads/twitch/twitch_PNG27.png"
                        async with session.get(f"https://api.twitch.tv/helix/users?login={twitch_username}", headers=headers) as u_resp:
                            if u_resp.status == 200:
                                u_data = await u_resp.json()
                                if u_data.get("data"):
                                    profile_image_url = u_data["data"][0].get("profile_image_url", profile_image_url)

                        channel = self.bot.get_channel(discord_channel_id)
                        if channel:
                            url = f"https://twitch.tv/{twitch_username}"
                            embed = discord.Embed(
                                title=title, 
                                url=url, 
                                color=0x9146FF, # Twitch Purple
                                timestamp=discord.utils.utcnow()
                            )
                            embed.set_author(name=f"{twitch_username} is LIVE on Twitch!", icon_url="https://pngimg.com/uploads/twitch/twitch_PNG27.png", url=url)
                            embed.set_thumbnail(url=profile_image_url)
                            embed.add_field(name="🎮 Playing", value=f"**{game}**", inline=True)
                            embed.add_field(name="👥 Viewers", value=f"**{viewer_count}**", inline=True)
                            
                            if thumbnail_url:
                                # Append a random query string so Discord doesn't cache the thumbnail
                                import random
                                embed.set_image(url=f"{thumbnail_url}?r={random.randint(1,10000)}")
                                
                            embed.set_footer(text="Twitch", icon_url="https://pngimg.com/uploads/twitch/twitch_PNG27.png")
                                
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(label="Watch Stream", style=discord.ButtonStyle.link, url=url))
                            
                            if discord_user_id:
                                content = f"{custom_message}\n🔴 <@{discord_user_id}> is live now!"
                            else:
                                content = f"{custom_message}\n🔴 **{twitch_username}** is live now!"
                            await channel.send(content=content, embed=embed, view=view)
                            
                    elif not is_live_now and db_is_live:
                        # WENT OFFLINE
                        await self.bot.db.execute("UPDATE twitch_alerts SET is_live = 0 WHERE id = ?", (db_id,))
                        await self.bot.db.commit()
                        await self._handle_live_role(guild_id, discord_user_id, add=False)
                        
        except Exception as e:
            print(f"Error in twitch alert loop: {e}")

    @notify_group.command(name="kick", description="Add a Kick streamer to post notifications for.")
    @commands.has_permissions(administrator=True)
    async def add_kick(self, ctx, kick_username: str, discord_channel: discord.TextChannel, discord_user: discord.Member = None, custom_message: str = "@everyone"):
        async with self.bot.db.execute("SELECT id FROM kick_alerts WHERE guild_id = ? AND kick_username = ?", (ctx.guild.id, kick_username.lower())) as cursor:
            if await cursor.fetchone():
                await ctx.send("❌ This Kick channel is already being monitored in this server!", ephemeral=True)
                return

        await self.bot.db.execute(
            "INSERT INTO kick_alerts (guild_id, channel_id, kick_username, is_live, discord_user_id, custom_message) VALUES (?, ?, ?, ?, ?, ?)",
            (ctx.guild.id, discord_channel.id, kick_username.lower(), 0, discord_user.id if discord_user else None, custom_message)
        )
        await self.bot.db.commit()

        embed = discord.Embed(title="✅ Kick Alerts Added", color=0x53FC18)
        embed.description = f"Successfully set up notifications for `{kick_username}`!\nWhenever they go live, I'll post in {discord_channel.mention}."
        await ctx.send(embed=embed)

    @notify_group.command(name="remove_kick", description="Stop monitoring a Kick streamer.")
    @commands.has_permissions(administrator=True)
    async def remove_kick(self, ctx, kick_username: str):
        await self.bot.db.execute("DELETE FROM kick_alerts WHERE guild_id = ? AND kick_username = ?", (ctx.guild.id, kick_username.lower()))
        await self.bot.db.commit()
        await ctx.send(f"✅ Removed `{kick_username}` from Kick alerts.")

    @tasks.loop(minutes=3.0)
    async def check_kick(self):
        await self.bot.wait_until_ready()
        try:
            async with self.bot.db.execute("SELECT id, guild_id, channel_id, kick_username, is_live, discord_user_id, custom_message FROM kick_alerts") as cursor:
                alerts = await cursor.fetchall()
                
            if not alerts: return
            
            async with aiohttp.ClientSession() as session:
                for alert in alerts:
                    db_id, guild_id, discord_channel_id, kick_username, db_is_live, discord_user_id, custom_message = alert
                    
                    is_live_now = False
                    try:
                        async with session.get(f'https://kick.com/api/v1/channels/{kick_username}') as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get('livestream'):
                                    is_live_now = True
                                    title = data['livestream']['session_title']
                                    thumbnail_url = data['livestream']['thumbnail']['url']
                                    game = data['livestream']['categories'][0]['name'] if data['livestream']['categories'] else "Kick Stream"
                                    viewer_count = data['livestream']['viewer_count']
                                    avatar_url = data['user']['profile_pic']
                    except Exception as e:
                        print(f"Kick check failed for {kick_username}: {e}")
                        continue
                        
                    if is_live_now and not db_is_live:
                        # WENT LIVE
                        await self._handle_live_role(guild_id, discord_user_id, add=True)
                        await self.bot.db.execute("UPDATE kick_alerts SET is_live = 1 WHERE id = ?", (db_id,))
                        await self.bot.db.commit()
                        
                        channel = self.bot.get_channel(discord_channel_id)
                        if channel:
                            url = f"https://kick.com/{kick_username}"
                            embed = discord.Embed(
                                title=title, 
                                url=url, 
                                color=0x53FC18,
                                timestamp=discord.utils.utcnow()
                            )
                            embed.set_author(name=f"{kick_username} is LIVE on Kick!", icon_url="https://cdn.iconscout.com/icon/free/png-256/free-kick-logo-icon-download-in-svg-png-gif-file-formats--social-media-company-brand-pack-logos-icons-2674087.png", url=url)
                            if avatar_url: embed.set_thumbnail(url=avatar_url)
                            embed.add_field(name="🎮 Playing", value=f"**{game}**", inline=True)
                            embed.add_field(name="👥 Viewers", value=f"**{viewer_count}**", inline=True)
                            if thumbnail_url:
                                import random
                                embed.set_image(url=f"{thumbnail_url}?r={random.randint(1,10000)}")
                                
                            embed.set_footer(text="Kick", icon_url="https://cdn.iconscout.com/icon/free/png-256/free-kick-logo-icon-download-in-svg-png-gif-file-formats--social-media-company-brand-pack-logos-icons-2674087.png")
                                
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(label="Watch Stream", style=discord.ButtonStyle.link, url=url))
                            
                            if discord_user_id:
                                content = f"{custom_message}\n🟢 <@{discord_user_id}> is live now!"
                            else:
                                content = f"{custom_message}\n🟢 **{kick_username}** is live now!"
                            await channel.send(content=content, embed=embed, view=view)
                            
                    elif not is_live_now and db_is_live:
                        await self.bot.db.execute("UPDATE kick_alerts SET is_live = 0 WHERE id = ?", (db_id,))
                        await self.bot.db.commit()
                        await self._handle_live_role(guild_id, discord_user_id, add=False)
        except Exception as e:
            print(f"Error in kick alert loop: {e}")

    @notify_group.command(name="tiktok", description="Add a TikTok streamer to post notifications for.")
    @commands.has_permissions(administrator=True)
    async def add_tiktok(self, ctx, tiktok_username: str, discord_channel: discord.TextChannel, discord_user: discord.Member = None, custom_message: str = "@everyone"):
        tiktok_username = tiktok_username.replace("@", "")
        
        # Initial fetch of latest video id
        last_video_id = ""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://www.tikwm.com/api/user/posts?unique_id={tiktok_username}&count=1') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('data') and data['data'].get('videos'):
                            last_video_id = data['data']['videos'][0]['video_id']
        except Exception as e:
            print(f"Failed to fetch initial TikTok video: {e}")

        async with self.bot.db.execute("SELECT id FROM tiktok_alerts WHERE guild_id = ? AND tiktok_username = ?", (ctx.guild.id, tiktok_username.lower())) as cursor:
            if await cursor.fetchone():
                await ctx.send("❌ This TikTok channel is already being monitored in this server!", ephemeral=True)
                return

        await self.bot.db.execute(
            "INSERT INTO tiktok_alerts (guild_id, channel_id, tiktok_username, is_live, last_video_id, discord_user_id, custom_message) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ctx.guild.id, discord_channel.id, tiktok_username.lower(), 0, last_video_id, discord_user.id if discord_user else None, custom_message)
        )
        await self.bot.db.commit()

        embed = discord.Embed(title="✅ TikTok Alerts Added", color=0x000000)
        embed.description = f"Successfully set up live and upload notifications for `@{tiktok_username}`!\nI'll post in {discord_channel.mention}."
        await ctx.send(embed=embed)

    @notify_group.command(name="remove_tiktok", description="Stop monitoring a TikTok streamer.")
    @commands.has_permissions(administrator=True)
    async def remove_tiktok(self, ctx, tiktok_username: str):
        tiktok_username = tiktok_username.replace("@", "")
        await self.bot.db.execute("DELETE FROM tiktok_alerts WHERE guild_id = ? AND tiktok_username = ?", (ctx.guild.id, tiktok_username.lower()))
        await self.bot.db.commit()
        await ctx.send(f"✅ Removed `@{tiktok_username}` from TikTok alerts.")

    @tasks.loop(minutes=3.0)
    async def check_tiktok(self):
        await self.bot.wait_until_ready()
        try:
            async with self.bot.db.execute("SELECT id, guild_id, channel_id, tiktok_username, is_live, last_video_id, discord_user_id, custom_message FROM tiktok_alerts") as cursor:
                alerts = await cursor.fetchall()
                
            if not alerts: return
            
            async with aiohttp.ClientSession() as session:
                for alert in alerts:
                    db_id, guild_id, discord_channel_id, tiktok_username, db_is_live, db_last_video_id, discord_user_id, custom_message = alert
                    
                    is_live_now = False
                    # 1. Check Live Status
                    try:
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                        async with session.get(f'https://www.tiktok.com/@{tiktok_username}/live', headers=headers) as resp:
                            text = await resp.text()
                            if '"status":2' in text or '"roomStatus":2' in text:
                                is_live_now = True
                    except Exception as e:
                        print(f"TikTok Live check failed for {tiktok_username}: {e}")
                        
                    if is_live_now and not db_is_live:
                        # WENT LIVE
                        await self._handle_live_role(guild_id, discord_user_id, add=True)
                        await self.bot.db.execute("UPDATE tiktok_alerts SET is_live = 1 WHERE id = ?", (db_id,))
                        await self.bot.db.commit()
                        
                        channel = self.bot.get_channel(discord_channel_id)
                        if channel:
                            url = f"https://www.tiktok.com/@{tiktok_username}/live"
                            
                            # Parse SIGI_STATE for rich embed
                            stream_title = f"@{tiktok_username} is Live on TikTok!"
                            cover_url = None
                            avatar_url = None
                            
                            match = re.search(r'<script id="SIGI_STATE".*?>(.*?)</script>', text)
                            if match:
                                try:
                                    data = json.loads(match.group(1))
                                    live_room = data.get("LiveRoom", {}).get("liveRoomUserInfo", {})
                                    user_data = live_room.get("user", {})
                                    room_data = live_room.get("liveRoom", {})
                                    
                                    if room_data.get("title"):
                                        stream_title = room_data.get("title")
                                    if room_data.get("coverUrl"):
                                        cover_url = room_data.get("coverUrl")
                                    if user_data.get("avatarThumb"):
                                        avatar_url = user_data.get("avatarThumb")
                                except Exception:
                                    pass
                            
                            embed = discord.Embed(
                                title=stream_title, 
                                url=url, 
                                color=0x000000,
                                timestamp=discord.utils.utcnow()
                            )
                            embed.set_author(name=f"@{tiktok_username}", icon_url=avatar_url or None, url=url)
                            embed.add_field(name="Status", value="🔴 LIVE", inline=True)
                            
                            if cover_url:
                                embed.set_image(url=cover_url)
                            embed.set_footer(text="TikTok", icon_url="https://cdn.iconscout.com/icon/free/png-256/free-tiktok-logo-icon-download-in-svg-png-gif-file-formats--social-media-company-brand-pack-logos-icons-2674087.png")
                                
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(label="Watch Stream", style=discord.ButtonStyle.link, url=url))
                            
                            if discord_user_id:
                                content = f"{custom_message}\n🔴 <@{discord_user_id}> is live now!"
                            else:
                                content = f"{custom_message}\n**@{tiktok_username}** is live now!"
                            await channel.send(content=content, embed=embed, view=view)
                            
                    elif not is_live_now and db_is_live:
                        await self.bot.db.execute("UPDATE tiktok_alerts SET is_live = 0 WHERE id = ?", (db_id,))
                        await self.bot.db.commit()
                        await self._handle_live_role(guild_id, discord_user_id, add=False)

                    # 2. Check New Videos
                    try:
                        async with session.get(f'https://www.tikwm.com/api/user/posts?unique_id={tiktok_username}&count=1') as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get('data') and data['data'].get('videos'):
                                    video = data['data']['videos'][0]
                                    video_id = video['video_id']
                                    
                                    if video_id != db_last_video_id:
                                        # NEW VIDEO UPLOADED
                                        title = video.get('title', f"New TikTok from @{tiktok_username}")
                                        play_count = video.get('play_count', 0)
                                        cover_url = video.get('cover', '')
                                        
                                        await self.bot.db.execute("UPDATE tiktok_alerts SET last_video_id = ? WHERE id = ?", (video_id, db_id))
                                        await self.bot.db.commit()
                                        
                                        channel = self.bot.get_channel(discord_channel_id)
                                        if channel:
                                            url = f"https://www.tiktok.com/@{tiktok_username}/video/{video_id}"
                                            embed = discord.Embed(
                                                title=title, 
                                                url=url, 
                                                color=0x000000,
                                                timestamp=discord.utils.utcnow()
                                            )
                                            embed.set_author(name=f"@{tiktok_username}", url=f"https://www.tiktok.com/@{tiktok_username}")
                                            if cover_url: embed.set_image(url=cover_url)
                                            embed.set_footer(text="TikTok", icon_url="https://cdn.iconscout.com/icon/free/png-256/free-tiktok-logo-icon-download-in-svg-png-gif-file-formats--social-media-company-brand-pack-logos-icons-2674087.png")
                                                
                                            view = discord.ui.View()
                                            view.add_item(discord.ui.Button(label="Watch Video", style=discord.ButtonStyle.link, url=url))
                                            
                                            if discord_user_id:
                                                content = f"{custom_message}\n🎵 <@{discord_user_id}> just posted a new TikTok!"
                                            else:
                                                content = f"{custom_message}\n🎵 **@{tiktok_username}** just posted a new TikTok!"
                                            await channel.send(content=content, embed=embed, view=view)
                    except Exception as e:
                        print(f"TikTok Video check failed for {tiktok_username}: {e}")

        except Exception as e:
            print(f"Error in tiktok alert loop: {e}")

    # ==========================================
    # AUTO LIVE ROLE SYSTEM
    # ==========================================

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if not after.guild: return
        
        async with self.bot.db.execute("SELECT role_id FROM live_roles WHERE guild_id = ?", (after.guild.id,)) as cursor:
            row = await cursor.fetchone()
            if not row: return
            live_role = after.guild.get_role(row[0])
            if not live_role: return

        was_streaming = any(isinstance(a, discord.Streaming) for a in before.activities) if before else False
        is_streaming = any(isinstance(a, discord.Streaming) for a in after.activities) if after else False

        if is_streaming and not was_streaming:
            try: await after.add_roles(live_role, reason="Auto Live Role")
            except: pass
        elif not is_streaming and was_streaming:
            try: await after.remove_roles(live_role, reason="Auto Live Role")
            except: pass

    @commands.hybrid_command(name="set_live_role", description="Set a role to automatically give to users when they stream on Discord.")
    @commands.has_permissions(administrator=True)
    async def set_live_role(self, ctx, role: discord.Role):
        await self.bot.db.execute(
            "CREATE TABLE IF NOT EXISTS live_roles (guild_id INTEGER PRIMARY KEY, role_id INTEGER)"
        )
        await self.bot.db.execute("INSERT OR REPLACE INTO live_roles (guild_id, role_id) VALUES (?, ?)", (ctx.guild.id, role.id))
        await self.bot.db.commit()
        await ctx.send(f"✅ Auto-Live role successfully set to {role.mention}! When server members stream on Discord, they will get this role.")

async def setup(bot):
    await bot.add_cog(Notifications(bot))
