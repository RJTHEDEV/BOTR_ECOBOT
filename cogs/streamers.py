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
        
        if not token or not client_id: return False, None

        headers = {
            'Client-ID': client_id,
            'Authorization': f'Bearer {token}'
        }
        
        try:
            async with session.get(f'https://api.twitch.tv/helix/streams?user_login={username}', headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['data']:
                        stream = data['data'][0]
                        return True, stream['title']
        except Exception as e:
            print(f"Twitch check error for {username}: {e}")
        
        return False, None

    async def check_youtube(self, session, username):
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key: return False, None

        # This is a simplified check. Ideally we'd store Channel ID, not username.
        # Searching by username/custom URL is tricky. We'll assume 'username' is the channel handle or ID for now.
        # If it's a handle (@user), we need to resolve it. 
        # For simplicity in this v1, let's assume the user provides the Channel ID if the username search fails, 
        # or we search for the channel.
        
        try:
            # Search for live video by channelId
            # First, try to find channel ID from username (handle)
            channel_id = username
            if username.startswith('@'):
                 async with session.get(f'https://www.googleapis.com/youtube/v3/search?part=snippet&type=channel&q={username}&key={api_key}') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data['items']:
                            channel_id = data['items'][0]['id']['channelId']

            async with session.get(f'https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channel_id}&eventType=live&type=video&key={api_key}') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['items']:
                        video = data['items'][0]
                        return True, video['snippet']['title']
        except Exception as e:
             print(f"YouTube check error for {username}: {e}")

        return False, None

    async def check_kick(self, session, username):
        # Kick has an undocumented API: https://kick.com/api/v1/channels/{slug}
        # Note: This is protected by Cloudflare and might fail. 
        # A better approach for bots is often just checking the page status or using a headless browser (not available here).
        # We will try the API endpoint first.
        try:
            async with session.get(f'https://kick.com/api/v1/channels/{username}') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('livestream'):
                        return True, data['livestream']['session_title']
        except:
            pass
        return False, None

    async def check_tiktok(self, session, username):
        # TikTok is very hard to scrape without a library. 
        # We can try checking the embed page or a specific unofficial API.
        # For now, we will leave this as a placeholder or try a very basic scrape.
        # Basic scrape: fetch https://www.tiktok.com/@username/live
        # Check for "status": 2 (LIVE) in the HTML data blob.
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            async with session.get(f'https://www.tiktok.com/@{username}/live', headers=headers) as resp:
                text = await resp.text()
                if '"status":2' in text or '"roomStatus":2' in text:
                    return True, "Live on TikTok"
        except:
            pass
        return False, None

    @tasks.loop(minutes=5)
    async def streamer_check_loop(self):
        async with self.bot.db.execute("SELECT guild_id, channel_id, platform, username, last_live FROM streamers") as cursor:
            rows = await cursor.fetchall()

        if not rows: return

        async with aiohttp.ClientSession() as session:
            for guild_id, channel_id, platform, username, last_live in rows:
                is_live = False
                stream_title = "Live Stream"

                if platform == 'twitch':
                    is_live, title = await self.check_twitch(session, username)
                    if title: stream_title = title
                elif platform == 'youtube':
                    is_live, title = await self.check_youtube(session, username)
                    if title: stream_title = title
                elif platform == 'kick':
                    is_live, title = await self.check_kick(session, username)
                    if title: stream_title = title
                elif platform == 'tiktok':
                    is_live, title = await self.check_tiktok(session, username)
                    if title: stream_title = title

                # Logic to send alert only once per stream
                # We use a simple timestamp check. If is_live and (now - last_live) > 1 hour (to avoid spam if bot restarts), send alert.
                now = datetime.datetime.now().timestamp()
                
                if is_live:
                    if (now - last_live) > 3600: # 1 hour cooldown
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            embed = discord.Embed(title=f"🔴 {username} is LIVE on {platform.capitalize()}!", 
                                                  description=f"**{stream_title}**\n\n[Watch Here](https://www.{platform}.com/{username})", 
                                                  color=discord.Color.red())
                            embed.set_thumbnail(url=f"https://cdn.iconscout.com/icon/free/png-256/free-{platform}-logo-icon-download-in-svg-png-gif-file-formats--social-media-company-brand-pack-logos-icons-2674087.png?f=webp") # Generic icon
                            await channel.send(embed=embed)
                        
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
