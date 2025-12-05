import discord
from discord.ext import commands, tasks
import aiohttp
import os
import tweepy
import datetime

class External(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.news_api_key = os.getenv("NEWS_API_KEY")
        
        # Twitter Setup
        self.twitter_client = None
        try:
            api_key = os.getenv("TWITTER_API_KEY")
            api_secret = os.getenv("TWITTER_API_SECRET")
            access_token = os.getenv("TWITTER_ACCESS_TOKEN")
            access_secret = os.getenv("TWITTER_ACCESS_SECRET")
            
            if api_key and api_secret and access_token and access_secret:
                self.twitter_client = tweepy.Client(
                    consumer_key=api_key,
                    consumer_secret=api_secret,
                    access_token=access_token,
                    access_token_secret=access_secret
                )
                print("Twitter Client Initialized")
        except Exception as e:
            print(f"Twitter Setup Error: {e}")

    @commands.hybrid_command(description="Get top news headlines.")
    async def marketnews(self, ctx, query: str = None):
        if not self.news_api_key:
            await ctx.send("❌ News API Key not configured.")
            return

        url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={self.news_api_key}"
        if query:
            url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&apiKey={self.news_api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await ctx.send("❌ Error fetching news.")
                    return
                
                data = await resp.json()
                articles = data.get('articles', [])
                
                if not articles:
                    await ctx.send("No articles found.")
                    return

                embed = discord.Embed(title="📰 Top Headlines" if not query else f"📰 News: {query}", color=discord.Color.red())
                for article in articles[:5]:
                    title = article.get('title', 'No Title')
                    url = article.get('url', '')
                    source = article.get('source', {}).get('name', 'Unknown')
                    embed.add_field(name=f"{source}: {title}", value=f"[Read Article]({url})", inline=False)
                
                await ctx.send(embed=embed)

    @commands.hybrid_command(description="Admin: Post a tweet.")
    @commands.has_permissions(administrator=True)
    async def tweet(self, ctx, *, message: str):
        if not self.twitter_client:
            await ctx.send("❌ Twitter API not configured.")
            return
        
        try:
            response = self.twitter_client.create_tweet(text=message)
            tweet_id = response.data['id']
            await ctx.send(f"✅ Tweet posted! https://twitter.com/user/status/{tweet_id}")
        except Exception as e:
            await ctx.send(f"❌ Error posting tweet: {e}")

async def setup(bot):
    await bot.add_cog(External(bot))
