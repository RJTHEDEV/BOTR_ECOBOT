import discord
from discord.ext import commands
import os
import asyncio
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

# Intents setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

class BOTR(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=commands.DefaultHelpCommand())
        self.db = None

    async def setup_hook(self):
        # Initialize database
        self.db = await aiosqlite.connect('data/bot.db')
        await self.create_tables()
        
        # Load cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded {filename}')
        
        # Sync commands
        # Global sync can take up to an hour. For instant updates in dev, sync to guild.
        # await self.tree.sync() 
        
        # Sync to specific guild (Instant) - Replace with your Guild ID if needed, 
        # or just use global sync and wait. For now, I'll use global sync but print a warning.
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} commands globally.")
        except Exception as e:
            print(f"Error syncing commands: {e}")

        print(f'Logged in as {self.user} (ID: {self.user.id})')

    async def create_tables(self):
        async with self.db.cursor() as cursor:
            # Users Table
            try:
                await cursor.execute("ALTER TABLE users ADD COLUMN tickets INTEGER DEFAULT 0")
            except:
                pass # Column likely exists

            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    tickets INTEGER DEFAULT 0
                )
            ''')
            # Inventory Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id INTEGER,
                    item_name TEXT,
                    quantity INTEGER,
                    PRIMARY KEY (user_id, item_name)
                )
            ''')
            # Store Table
            try:
                await cursor.execute("ALTER TABLE store ADD COLUMN currency TEXT DEFAULT 'coins'")
            except:
                pass

            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS store (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    price INTEGER,
                    description TEXT,
                    currency TEXT DEFAULT 'coins'
                )
            ''')
            # Schedule Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT,
                    event_time TEXT,
                    description TEXT
                )
            ''')
            # Giveaways Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS giveaways (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    prize TEXT,
                    end_time TEXT,
                    winners_count INTEGER,
                    ended BOOLEAN DEFAULT 0
                )
            ''')
            # Raffles Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS raffles (
                    raffle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER,
                    prize TEXT,
                    ticket_cost INTEGER,
                    ended BOOLEAN DEFAULT 0
                )
            ''')
            # Raffle Entries Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS raffle_entries (
                    raffle_id INTEGER,
                    user_id INTEGER,
                    entries_count INTEGER,
                    PRIMARY KEY (raffle_id, user_id)
                )
            ''')
            # Log Settings Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS log_settings (
                    guild_id INTEGER,
                    log_type TEXT,
                    channel_id INTEGER,
                    PRIMARY KEY (guild_id, log_type)
                )
            ''')
            # Log Ignores Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS log_ignores (
                    guild_id INTEGER,
                    ignore_type TEXT,
                    target_id INTEGER,
                    PRIMARY KEY (guild_id, ignore_type, target_id)
                )
            ''')
            # Infractions Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS infractions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    mod_id INTEGER,
                    type TEXT,
                    reason TEXT,
                    timestamp TEXT
                )
            ''')
            # Sticky Roles Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS sticky_roles (
                    guild_id INTEGER,
                    user_id INTEGER,
                    role_ids TEXT,
                    PRIMARY KEY (guild_id, user_id)
                )
            ''')
            # Watchlist Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlist (
                    user_id INTEGER,
                    ticker TEXT,
                    PRIMARY KEY (user_id, ticker)
                )
            ''')
            # Portfolio Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS portfolio (
                    user_id INTEGER,
                    ticker TEXT,
                    avg_price REAL,
                    shares INTEGER,
                    PRIMARY KEY (user_id, ticker)
                )
            ''')
        await self.db.commit()

    async def close(self):
        await self.db.close()
        await super().close()

bot = BOTR()

if __name__ == '__main__':
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in .env")
    else:
        bot.run(TOKEN)
