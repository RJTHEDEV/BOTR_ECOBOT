import discord
from discord.ext import commands, tasks
import aiohttp
import os
import datetime
import json

import random

class Streamers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitch_token = None
        self.twitch_token_expires = 0
        self.streamer_check_loop.start()
        
        self.live_messages = [
            "{username} just went LIVE! Get in here!",
            "It's showtime! {username} is live on {platform}!",
            "Stop what you're doing, {username} is streaming!",
            "{username} is live! Returns of the King/Queen!",
            "Popcorn ready? {username} is live!",
            "Alert! {username} has started streaming!",
            "Don't miss out! {username} is live now!"
        ]
        
        self.offline_messages = [
            "{username} has gone offline. Catch you next time!",
            "Stream over! {username} is offline now.",
            "That's a wrap for {username}. See ya!",
            "{username} signed off. Hope you enjoyed the stream!",
            "Offline now. Check back later for more {username}!",
            "{username} has ended the stream. GG!",
            "Show's over folks! {username} is offline."
        ]

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

    async def send_notification(self, channel, platform, username, stream_info, is_going_live):
        stream_url = f"https://www.{platform}.com/{username}"
        if platform == "kick": stream_url = f"https://kick.com/{username}"
        elif platform == "youtube": stream_url = f"https://youtube.com/{username}"
        
        if is_going_live:
            title = stream_info.get('title', 'Live Stream')
            thumbnail_url = stream_info.get('thumbnail')
            game_name = stream_info.get('game', 'Just Chatting')
            viewer_count = stream_info.get('viewers', 0)
            avatar_url = stream_info.get('avatar')

            msg_content = random.choice(self.live_messages).format(username=username, platform=platform.capitalize())
            
            embed = discord.Embed(description=f"**{title}**", color=discord.Color.purple())
            embed.set_author(name=f"{username} is LIVE on {platform.capitalize()}!", icon_url=avatar_url or f"https://cdn.iconscout.com/icon/free/png-256/free-{platform}-logo-icon-download-in-svg-png-gif-file-formats--social-media-company-brand-pack-logos-icons-2674087.png?f=webp")
            
            embed.add_field(name="Game", value=game_name, inline=True)
            embed.add_field(name="Viewers", value=str(viewer_count), inline=True)
            
            if thumbnail_url:
                embed.set_image(url=thumbnail_url)
            
            embed.set_footer(text=f"{platform.capitalize()} • {datetime.datetime.now().strftime('%I:%M %p')}")

            # Button View
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Watch Stream", style=discord.ButtonStyle.link, url=stream_url))
            
            # Fetch subs
            async with self.bot.db.execute("SELECT user_id FROM streamer_subs WHERE streamer_name = ? AND platform = ?", (username.lower(), platform.lower())) as cursor:
                subs = await cursor.fetchall()
            
            mentions = " ".join([f"<@{sub[0]}>" for sub in subs])
            msg_prefix = f"{mentions}\n" if mentions else ""
            await channel.send(content=f"{msg_prefix}{msg_content}", embed=embed, view=view)
        
        else: # Going Offline
            msg_content = random.choice(self.offline_messages).format(username=username)
            
            embed = discord.Embed(description=f"Thanks to everyone who tuned in!", color=discord.Color.dark_grey())
            embed.set_author(name=f"{username} is now Offline", icon_url=f"https://cdn.iconscout.com/icon/free/png-256/free-{platform}-logo-icon-download-in-svg-png-gif-file-formats--social-media-company-brand-pack-logos-icons-2674087.png?f=webp")
            embed.set_footer(text=f"{platform.capitalize()} • {datetime.datetime.now().strftime('%I:%M %p')}")

            await channel.send(content=f"{msg_content}", embed=embed)

    @tasks.loop(minutes=5)
    async def streamer_check_loop(self):
        async with self.bot.db.execute("SELECT guild_id, channel_id, platform, username, last_live, is_live FROM streamers") as cursor:
            rows = await cursor.fetchall()

        if not rows: return

        async with aiohttp.ClientSession() as session:
            for guild_id, channel_id, platform, username, last_live, is_live_db in rows:
                is_live_now = False
                stream_title = "Live Stream"
                thumbnail_url = None
                game_name = "Just Chatting"
                viewer_count = 0
                avatar_url = None

                if platform == 'twitch':
                    is_live_now, title, thumb, game, viewers, avatar = await self.check_twitch(session, username)
                elif platform == 'youtube':
                    is_live_now, title, thumb, game, viewers, avatar = await self.check_youtube(session, username)
                elif platform == 'kick':
                    is_live_now, title, thumb, game, viewers, avatar = await self.check_kick(session, username)
                elif platform == 'tiktok':
                    is_live_now, title, thumb, game, viewers, avatar = await self.check_tiktok(session, username)

                channel = self.bot.get_channel(channel_id)
                if not channel: continue

                # Status Change Logic
                now = datetime.datetime.now().timestamp()

                # Case 1: Went LIVE (Offline -> Live)
                if is_live_now and not is_live_db:
                    stream_info = {
                        'title': title,
                        'thumbnail': thumb,
                        'game': game,
                        'viewers': viewers,
                        'avatar': avatar
                    }
                    await self.send_notification(channel, platform, username, stream_info, True)
                    
                    # Update DB
                    await self.bot.db.execute("UPDATE streamers SET is_live = 1, last_live = ? WHERE guild_id = ? AND platform = ? AND username = ?", 
                                              (now, guild_id, platform, username))
                    await self.bot.db.commit()

                # Case 2: Went OFFLINE (Live -> Offline)
                elif not is_live_now and is_live_db:
                    await self.send_notification(channel, platform, username, {}, False)
                    
                    # Update DB
                    await self.bot.db.execute("UPDATE streamers SET is_live = 0 WHERE guild_id = ? AND platform = ? AND username = ?", 
                                              (guild_id, platform, username))
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

    @streamer.command(name="test", description="Test streamer notifications (Admin only).")
    @commands.has_permissions(administrator=True)
    async def test(self, ctx, platform: str, username: str, action: str = "live"):
        """
        Test streamer notifications.
        Usage: !streamer test <platform> <username> [live/offline]
        """
        platform = platform.lower()
        action = action.lower()
        
        if platform not in ["twitch", "youtube", "kick", "tiktok"]:
            await ctx.send("❌ Invalid platform. Supported: `twitch`, `youtube`, `kick`, `tiktok`.")
            return
            
        if action == "live":
            stream_info = {
                'title': "Test Stream Title",
                'thumbnail': "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png", # Placeholder
                'game': "Testing",
                'viewers': 1337,
                'avatar': None
            }
            await self.send_notification(ctx.channel, platform, username, stream_info, True)
            await ctx.send(f"✅ Sent **Go Live** test for {username} on {platform}.", delete_after=5)
            
        elif action == "offline":
            await self.send_notification(ctx.channel, platform, username, {}, False)
            await ctx.send(f"✅ Sent **Go Offline** test for {username} on {platform}.", delete_after=5)
        else:
            await ctx.send("❌ Invalid action. Use `live` or `offline`.")

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        # Auto Live Role
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

    @commands.hybrid_command(description="Set the auto-live role.")
    @commands.has_permissions(administrator=True)
    async def set_live_role(self, ctx, role: discord.Role):
        await self.bot.db.execute("INSERT OR REPLACE INTO live_roles (guild_id, role_id) VALUES (?, ?)", (ctx.guild.id, role.id))
        await self.bot.db.commit()
        await ctx.send(f"✅ Auto-Live role set to {role.mention}")

    @commands.hybrid_group(invoke_without_command=True, description="Creator profiles.")
    async def creator(self, ctx):
        await ctx.send("Use `/creator profile <user>` or `/creator setup`.")

    @creator.command(description="Set up your creator profile.")
    async def setup(self, ctx, bio: str = None, twitch: str = None, youtube: str = None, twitter: str = None, kick: str = None, tiktok: str = None):
        await self.bot.db.execute("""
            INSERT OR REPLACE INTO creator_profiles (user_id, bio, twitch, youtube, twitter, kick, tiktok)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ctx.author.id, bio, twitch, youtube, twitter, kick, tiktok))
        await self.bot.db.commit()
        await ctx.send("✅ Creator profile updated!")

    @creator.command(description="View a creator profile.")
    async def profile(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        async with self.bot.db.execute("SELECT bio, twitch, youtube, twitter, kick, tiktok FROM creator_profiles WHERE user_id = ?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await ctx.send(f"{user.display_name} has not set up a creator profile.")
                return

        bio, twitch, youtube, twitter, kick, tiktok = row
        embed = discord.Embed(title=f"🎬 {user.display_name}'s Creator Profile", color=discord.Color.purple())
        embed.set_thumbnail(url=user.display_avatar.url)
        if bio: embed.description = bio
        
        links = []
        if twitch: links.append(f"[Twitch]({twitch})")
        if youtube: links.append(f"[YouTube]({youtube})")
        if twitter: links.append(f"[Twitter]({twitter})")
        if kick: links.append(f"[Kick]({kick})")
        if tiktok: links.append(f"[TikTok]({tiktok})")
        
        if links:
            embed.add_field(name="Socials", value=" | ".join(links))
        
        await ctx.send(embed=embed)

    @commands.hybrid_group(invoke_without_command=True, description="Manage streamer notifications.")
    async def notify(self, ctx):
        await ctx.send("Use `/notify subscribe <platform> <username>` or `/notify unsubscribe <platform> <username>`.")

    @notify.command(description="Subscribe to a streamer's go-live alerts.")
    async def subscribe(self, ctx, platform: str, username: str):
        await self.bot.db.execute("INSERT OR IGNORE INTO streamer_subs (user_id, streamer_name, platform) VALUES (?, ?, ?)", (ctx.author.id, username.lower(), platform.lower()))
        await self.bot.db.commit()
        await ctx.send(f"✅ Subscribed to {username} on {platform}!")

    @notify.command(description="Unsubscribe from a streamer's go-live alerts.")
    async def unsubscribe(self, ctx, platform: str, username: str):
        await self.bot.db.execute("DELETE FROM streamer_subs WHERE user_id = ? AND streamer_name = ? AND platform = ?", (ctx.author.id, username.lower(), platform.lower()))
        await self.bot.db.commit()
        await ctx.send(f"✅ Unsubscribed from {username} on {platform}.")

    @commands.hybrid_group(invoke_without_command=True, description="Share and view stream clips.")
    async def clip(self, ctx):
        pass

    @clip.command(description="Submit a clip.")
    async def submit(self, ctx, streamer_name: str, url: str, *, description: str = ""):
        timestamp = datetime.datetime.now().isoformat()
        await self.bot.db.execute("INSERT INTO clips (guild_id, submitter_id, streamer_name, url, description, timestamp) VALUES (?, ?, ?, ?, ?, ?)", 
                                  (ctx.guild.id, ctx.author.id, streamer_name, url, description, timestamp))
        await self.bot.db.commit()
        await ctx.send(f"✅ Clip submitted for **{streamer_name}**!")

    @clip.command(description="List top clips.")
    async def list(self, ctx):
        async with self.bot.db.execute("SELECT id, streamer_name, url, description, upvotes FROM clips WHERE guild_id = ? ORDER BY upvotes DESC LIMIT 5", (ctx.guild.id,)) as cursor:
            rows = await cursor.fetchall()
            if not rows:
                await ctx.send("No clips submitted yet.")
                return
            
            embed = discord.Embed(title="🎬 Top Stream Clips", color=discord.Color.gold())
            for id, streamer, url, desc, upvotes in rows:
                embed.add_field(name=f"[{id}] {streamer} (👍 {upvotes})", value=f"{desc}\n{url}", inline=False)
            await ctx.send(embed=embed)

    @clip.command(description="Upvote a clip by ID.")
    async def upvote(self, ctx, clip_id: int):
        await self.bot.db.execute("UPDATE clips SET upvotes = upvotes + 1 WHERE id = ? AND guild_id = ?", (clip_id, ctx.guild.id))
        await self.bot.db.commit()
        await ctx.send(f"✅ Upvoted clip #{clip_id}!")

async def setup(bot):
    await bot.add_cog(Streamers(bot))
