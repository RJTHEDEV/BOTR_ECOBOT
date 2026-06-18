import discord
from discord.ext import commands
import yt_dlp
import asyncio

# Suppress noise about console usage from errors
yt_dlp.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="music", invoke_without_command=True)
    async def music_group(self, ctx):
        await ctx.send("Use `/music <action>`")


    @music_group.command(description="Join the voice channel.")
    async def join(self, ctx):
        if not ctx.author.voice:
            await ctx.send("You are not connected to a voice channel.")
            return
        else:
            channel = ctx.author.voice.channel
        
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)
        
        try:
            await channel.connect()
            await ctx.send(f"Joined {channel.name}")
        except Exception as e:
            try:
                await ctx.send(f"❌ Failed to join voice channel! Error: `{type(e).__name__}: {e}`")
            except:
                pass
            print(f"Voice Connection Error: {type(e).__name__}: {e}")

    @music_group.command(description="Play audio from a YouTube URL or search query.")
    async def play(self, ctx, *, query: str):
        if not ctx.voice_client:
            await ctx.invoke(self.join)
            
        async with ctx.typing():
            try:
                player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
                ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
                await ctx.send(f'🎵 Now playing: **{player.title}**')
            except Exception as e:
                await ctx.send(f"An error occurred: {e}")

    @music_group.command(description="Stop the music and leave the voice channel.")
    async def stop(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("Stopped playing and left the channel.")
        else:
            await ctx.send("I'm not in a voice channel.")

    @music_group.command(description="Pause the currently playing audio.")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Paused the audio.")
            
    @music_group.command(description="Resume the currently paused audio.")
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Resumed the audio.")

async def setup(bot):
    await bot.add_cog(Music(bot))
