import discord
from discord.ext import commands, tasks
import aiohttp
import os
import datetime
import json

class Streamers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitch_token = None
        self.twitch_token_expires = 0
        self.streamer_check_loop.start()

    def cog_unload(self):
        self.streamer_check_loop.cancel()

    async def get_twitch_token(self):
        client_id = os.getenv('TWITCH_CLIENT_ID')
        client_secret = os.getenv('TWITCH_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            return None

        if self.twitch_token and datetime.datetime.now().timestamp() < self.twitch_token_expires:
            return self.twitch_token

        async with aiohttp.ClientSession() as session:
            async with session.post(f'https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.twitch_token = data['access_token']
                    self.twitch_token_expires = datetime.datetime.now().timestamp() + data['expires_in'] - 60
                    return self.twitch_token
                else:
                    print(f"Failed to get Twitch token: {resp.status}")
                    return None

    async def check_twitch(self, session, username):
        token = await self.get_twitch_token()
        client_id = os.getenv('TWITCH_CLIENT_ID')
        
        if not token or not client_id: return False, None, None, None, None, None

        headers = {
            'Client-ID': client_id,
            'Authorization': f'Bearer {token}'
        }
        
        try:
            # 1. Get Stream Info
            async with session.get(f'https://api.twitch.tv/helix/streams?user_login={username}', headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['data']:
                        stream = data['data'][0]
                        title = stream['title']
                        thumbnail = stream['thumbnail_url'].replace('{width}x{height}', '1280x720')
                        game_name = stream['game_name']
                        viewer_count = stream['viewer_count']
                        user_id = stream['user_id']
                        
                        # 2. Get User Info (Avatar)
                        avatar_url = None
                        async with session.get(f'https://api.twitch.tv/helix/users?id={user_id}', headers=headers) as user_resp:
                            if user_resp.status == 200:
                                user_data = await user_resp.json()
                                if user_data['data']:
                                    avatar_url = user_data['data'][0]['profile_image_url']
                        
                        return True, title, thumbnail, game_name, viewer_count, avatar_url
        except Exception as e:
            print(f"Twitch check error for {username}: {e}")
        
        return False, None, None, None, None, None

    async def check_youtube(self, session, username):
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key: return False, None, None, None, None, None

        try:
            # 1. Resolve Channel ID
            channel_id = username
            if username.startswith('@'):
                 async with session.get(f'https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q={username}&key={api_key}') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data['items']:
                            channel_id = data['items'][0]['id']['channelId']

            # 2. Get Live Video
            async with session.get(f'https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channel_id}&eventType=live&type=video&key={api_key}') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['items']:
                        video = data['items'][0]
                        title = video['snippet']['title']
                        thumbnail = video['snippet']['thumbnails']['high']['url']
                        video_id = video['id']['videoId']
                        
                        # 3. Get Viewer Count (requires videos endpoint)
                        viewer_count = 0
                        async with session.get(f'https://www.googleapis.com/youtube/v3/videos?part=liveStreamingDetails&id={video_id}&key={api_key}') as v_resp:
                            if v_resp.status == 200:
                                v_data = await v_resp.json()
                                if v_data['items']:
                                    viewer_count = v_data['items'][0]['liveStreamingDetails'].get('concurrentViewers', 0)

                        # 4. Get Channel Avatar
                        avatar_url = None
                        async with session.get(f'https://www.googleapis.com/youtube/v3/channels?part=snippet&id={channel_id}&key={api_key}') as c_resp:
                             if c_resp.status == 200:
                                c_data = await c_resp.json()
                                if c_data['items']:
                                    avatar_url = c_data['items'][0]['snippet']['thumbnails']['default']['url']

                        return True, title, thumbnail, "YouTube Live", viewer_count, avatar_url
        except Exception as e:
             print(f"YouTube check error for {username}: {e}")

        return False, None, None, None, None, None

    async def check_kick(self, session, username):
        try:
            async with session.get(f'https://kick.com/api/v1/channels/{username}') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('livestream'):
                        title = data['livestream']['session_title']
                        thumbnail = data['livestream']['thumbnail']['url']
                        game_name = data['livestream']['categories'][0]['name'] if data['livestream']['categories'] else "Kick Stream"
                        viewer_count = data['livestream']['viewer_count']
                        avatar_url = data['user']['profile_pic']
                        
                        return True, title, thumbnail, game_name, viewer_count, avatar_url
        except:
            pass
        return False, None, None, None, None, None

    async def check_tiktok(self, session, username):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            async with session.get(f'https://www.tiktok.com/@{username}/live', headers=headers) as resp:
                text = await resp.text()
                if '"status":2' in text or '"roomStatus":2' in text:
                    return True, "Live on TikTok", None, "TikTok Live", 0, None
        except:
            pass
        return False, None, None, None, None, None

    @tasks.loop(minutes=5)
    async def streamer_check_loop(self):
        async with self.bot.db.execute("SELECT guild_id, channel_id, platform, username, last_live FROM streamers") as cursor:
            rows = await cursor.fetchall()

        if not rows: return

        async with aiohttp.ClientSession() as session:
            for guild_id, channel_id, platform, username, last_live in rows:
                is_live = False
                stream_title = "Live Stream"
                thumbnail_url = None
                game_name = "Just Chatting"
                viewer_count = 0
                avatar_url = None

                if platform == 'twitch':
                    is_live, title, thumb, game, viewers, avatar = await self.check_twitch(session, username)
                elif platform == 'youtube':
                    is_live, title, thumb, game, viewers, avatar = await self.check_youtube(session, username)
                elif platform == 'kick':
                    is_live, title, thumb, game, viewers, avatar = await self.check_kick(session, username)
                elif platform == 'tiktok':
                    is_live, title, thumb, game, viewers, avatar = await self.check_tiktok(session, username)

                if is_live:
                    if title: stream_title = title
                    if thumb: thumbnail_url = thumb
                    if game: game_name = game
                    if viewers: viewer_count = viewers
                    if avatar: avatar_url = avatar

                    # Logic to send alert only once per stream
                    now = datetime.datetime.now().timestamp()
                    
                    if (now - last_live) > 3600: # 1 hour cooldown
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            stream_url = f"https://www.{platform}.com/{username}"
                            if platform == "kick": stream_url = f"https://kick.com/{username}" # Fix kick url
                            
                            embed = discord.Embed(description=f"**{stream_title}**", color=discord.Color.purple())
                            embed.set_author(name=f"{username} is LIVE on {platform.capitalize()}!", icon_url=avatar_url or f"https://cdn.iconscout.com/icon/free/png-256/free-{platform}-logo-icon-download-in-svg-png-gif-file-formats--social-media-company-brand-pack-logos-icons-2674087.png?f=webp")
                            
                            embed.add_field(name="Game", value=game_name, inline=True)
                            embed.add_field(name="Viewers", value=str(viewer_count), inline=True)
                            
                            if thumbnail_url:
                                embed.set_image(url=thumbnail_url)
                            
                            embed.set_footer(text=f"{platform.capitalize()} • {datetime.datetime.now().strftime('%I:%M %p')}")

                            # Button View
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(label="Watch Stream", style=discord.ButtonStyle.link, url=stream_url))
                            
                            await channel.send(content=f"@everyone {username} is live!", embed=embed, view=view)
                        
                        # Update last_live
                        await self.bot.db.execute("UPDATE streamers SET last_live = ? WHERE guild_id = ? AND platform = ? AND username = ?", 
                                                  (now, guild_id, platform, username))
                        await self.bot.db.commit()

    @streamer_check_loop.before_loop
    async def before_streamer_check(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_group(name="streamer", description="Manage streamer alerts.")
    async def streamer(self, ctx):
        pass

    @streamer.command(name="add", description="Add a streamer to track.")
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, platform: str, username: str, channel: discord.TextChannel = None):
        """
        Add a streamer to track.
        Platforms: twitch, youtube, kick, tiktok
        """
        platform = platform.lower()
        if platform not in ["twitch", "youtube", "kick", "tiktok"]:
            await ctx.send("❌ Invalid platform. Supported: `twitch`, `youtube`, `kick`, `tiktok`.")
            return

        target_channel = channel or ctx.channel

        async with self.bot.db.execute("SELECT * FROM streamers WHERE guild_id = ? AND platform = ? AND username = ?", (ctx.guild.id, platform, username)) as cursor:
            if await cursor.fetchone():
                await ctx.send(f"⚠️ **{username}** is already being tracked on **{platform}** in this server.")
                return

        await self.bot.db.execute("INSERT INTO streamers (guild_id, channel_id, platform, username, last_live) VALUES (?, ?, ?, ?, ?)", 
                                  (ctx.guild.id, target_channel.id, platform, username, 0))
        await self.bot.db.commit()
        
        await ctx.send(f"✅ Added **{username}** ({platform}) to alerts in {target_channel.mention}.")

    @streamer.command(name="remove", description="Remove a streamer from alerts.")
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx, platform: str, username: str):
        platform = platform.lower()
        async with self.bot.db.execute("DELETE FROM streamers WHERE guild_id = ? AND platform = ? AND username = ?", (ctx.guild.id, platform, username)) as cursor:
            if cursor.rowcount == 0:
                await ctx.send(f"❌ Could not find **{username}** on **{platform}**.")
            else:
                await self.bot.db.commit()
                await ctx.send(f"🗑️ Removed **{username}** ({platform}) from alerts.")

    @streamer.command(name="list", description="List all tracked streamers.")
    async def list(self, ctx):
        async with self.bot.db.execute("SELECT platform, username, channel_id FROM streamers WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await ctx.send("No streamers are being tracked.")
            return

        embed = discord.Embed(title="📺 Tracked Streamers", color=discord.Color.purple())
        
        # Group by platform
        platforms = {}
        for platform, username, channel_id in rows:
            if platform not in platforms: platforms[platform] = []
            channel = ctx.guild.get_channel(channel_id)
            channel_mention = channel.mention if channel else "#deleted-channel"
            platforms[platform].append(f"**{username}** -> {channel_mention}")

        for platform, streamers in platforms.items():
            embed.add_field(name=platform.capitalize(), value="\n".join(streamers), inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Streamers(bot))
