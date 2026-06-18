import discord
from discord.ext import commands
import os
import asyncio
import aiosqlite
from dotenv import load_dotenv
import sys
import traceback
import datetime
from utils.embeds import Embeds
import difflib
import atexit
import subprocess

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

# Intents setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.presences = True

class BOTR(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None) # Disable default help
        self.db = None

    async def setup_hook(self):
        with open("startup.log", "w") as f:
            f.write("Starting setup_hook...\n")
        
        try:
            # Initialize database
            self.db = await aiosqlite.connect('data/bot.db')
            await self.create_tables()
            with open("startup.log", "a") as f: f.write("Tables created.\n")
            
            # Load cogs
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        print(f'Loaded {filename}')
                        with open("startup.log", "a") as f: f.write(f"Loaded {filename}\n")
                    except Exception as e:
                        print(f"Failed to load {filename}: {e}")
                        with open("startup.log", "a") as f: f.write(f"Failed to load {filename}: {e}\n")
            
            # Sync commands
            try:
                synced = await self.tree.sync()
                print(f"Synced {len(synced)} commands globally.")
                with open("startup.log", "a") as f: f.write(f"Synced {len(synced)} commands globally.\n")
            except Exception as e:
                print(f"Error syncing commands: {e}")
                with open("startup.log", "a") as f: f.write(f"Error syncing commands: {e}\n")

            print(f'Logged in as {self.user} (ID: {self.user.id})')
            with open("startup.log", "a") as f: f.write(f"Logged in as {self.user}\n")
            
        except Exception as e:
            print(f"Setup Hook Error: {e}")
            with open("startup.log", "a") as f: f.write(f"Setup Hook Error: {e}\n")

        # Global tree error handler
        self.tree.on_error = self.on_app_command_error
        
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(description=f"❌ You are missing permissions to use this command: `{', '.join(error.missing_permissions)}`", color=discord.Color.red())
            await ctx.send(embed=embed, ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(description=f"❌ I am missing permissions to execute this command: `{', '.join(error.missing_permissions)}`", color=discord.Color.red())
            await ctx.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(description=f"❌ An error occurred: {str(error)}", color=discord.Color.red())
            await ctx.send(embed=embed, ephemeral=True)
            print(f"Command Error: {error}")

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        embed = discord.Embed(description=f"❌ An error occurred: {str(error)}", color=discord.Color.red())
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"App Command Error: {error}")
            


    async def create_tables(self):
        async with self.db.cursor() as cursor:
            # Users Table
            try: await cursor.execute("ALTER TABLE users ADD COLUMN tickets INTEGER DEFAULT 0")
            except: pass 
            
            # Phase 1 Columns
            try: await cursor.execute("ALTER TABLE users ADD COLUMN bank INTEGER DEFAULT 0")
            except: pass
            try: await cursor.execute("ALTER TABLE users ADD COLUMN reputation INTEGER DEFAULT 0")
            except: pass
            try: await cursor.execute("ALTER TABLE users ADD COLUMN last_daily TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE users ADD COLUMN last_work TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE users ADD COLUMN last_crime TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE users ADD COLUMN last_rob TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE users ADD COLUMN last_rep TEXT")
            except: pass

            try: await cursor.execute("ALTER TABLE users ADD COLUMN work_shifts INTEGER DEFAULT 0")
            except: pass
            try: await cursor.execute("ALTER TABLE users ADD COLUMN wanted_level INTEGER DEFAULT 0")
            except: pass
            
            try: await cursor.execute("ALTER TABLE users ADD COLUMN casino_vip INTEGER DEFAULT 0")
            except: pass
            try: await cursor.execute("ALTER TABLE users ADD COLUMN xp_boost_expiry TEXT")
            except: pass

            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    tickets INTEGER DEFAULT 0,
                    bank INTEGER DEFAULT 0,
                    reputation INTEGER DEFAULT 0,
                    last_daily TEXT,
                    last_work TEXT,
                    last_crime TEXT,
                    last_rob TEXT,
                    last_rep TEXT,
                    daily_streak INTEGER DEFAULT 0,
                    work_shifts INTEGER DEFAULT 0,
                    wanted_level INTEGER DEFAULT 0,
                    casino_vip INTEGER DEFAULT 0,
                    xp_boost_expiry TEXT
                )
            ''')
            
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS kick_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    kick_username TEXT,
                    is_live INTEGER DEFAULT 0,
                    custom_message TEXT
                )
            ''')
            
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS tiktok_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    tiktok_username TEXT,
                    is_live INTEGER DEFAULT 0,
                    last_video_id TEXT,
                    custom_message TEXT
                )
            ''')
            
            # YouTube Alerts Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS youtube_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    youtube_channel_id TEXT,
                    last_video_id TEXT,
                    custom_message TEXT
                )
            ''')
            
            # Twitch Alerts Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS twitch_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    twitch_username TEXT,
                    is_live INTEGER DEFAULT 0,
                    custom_message TEXT
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
            try: await cursor.execute("ALTER TABLE store ADD COLUMN currency TEXT DEFAULT 'coins'")
            except: pass

            # Phase 2 Columns
            try: await cursor.execute("ALTER TABLE users ADD COLUMN daily_streak INTEGER DEFAULT 0")
            except: pass
            try: await cursor.execute("ALTER TABLE store ADD COLUMN category TEXT DEFAULT 'Items'")
            except: pass

            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS store (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    price INTEGER,
                    description TEXT,
                    currency TEXT DEFAULT 'coins',
                    category TEXT DEFAULT 'Items'
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
            # Giveaway Entries Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS giveaway_entries (
                    message_id INTEGER,
                    user_id INTEGER,
                    PRIMARY KEY (message_id, user_id)
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
            # Streamers Table
            try: await cursor.execute("ALTER TABLE streamers ADD COLUMN is_live INTEGER DEFAULT 0")
            except: pass

            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS streamers (
                    guild_id INTEGER,
                    channel_id INTEGER,
                    platform TEXT,
                    username TEXT,
                    last_live REAL,
                    is_live INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, platform, username)
                )
            ''')
            # Ticket Panels Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS ticket_panels (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    guild_id INTEGER,
                    title TEXT,
                    description TEXT,
                    button_label TEXT
                )
            ''')
            # Tickets Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS tickets (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    user_id INTEGER,
                    panel_message_id INTEGER,
                    status TEXT DEFAULT 'open'
                )
            ''')
            # Portfolio Table
            try: await cursor.execute("ALTER TABLE portfolio ADD COLUMN avg_buy_price REAL DEFAULT 0.0")
            except: pass

            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS portfolio (
                    user_id INTEGER,
                    ticker TEXT,
                    avg_price REAL,
                    shares INTEGER,
                    avg_buy_price REAL DEFAULT 0.0,
                    PRIMARY KEY (user_id, ticker)
                )
            ''')

            # Limit Orders Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS limit_orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    symbol TEXT,
                    order_type TEXT, -- 'buy_limit' or 'sell_limit'
                    target_price REAL,
                    quantity INTEGER,
                    created_at TEXT
                )
            ''')
            # Voice Hubs Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS voice_hubs (
                    guild_id INTEGER,
                    channel_id INTEGER PRIMARY KEY,
                    category_id INTEGER,
                    name_template TEXT
                )
            ''')
            # Temp Channels Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS temp_channels (
                    channel_id INTEGER PRIMARY KEY,
                    owner_id INTEGER
                )
            ''')
            # Welcome Settings Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS welcome_settings (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER
                )
            ''')
            # Auto Roles Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS auto_roles (
                    guild_id INTEGER PRIMARY KEY,
                    role_id INTEGER
                )
            ''')
            # Price Alerts Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    target_price REAL,
                    condition TEXT,
                    triggered BOOLEAN DEFAULT 0
                )
            ''')
            # Polls Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS polls (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    guild_id INTEGER,
                    author_id INTEGER,
                    question TEXT,
                    options TEXT,
                    end_time TEXT,
                    active BOOLEAN DEFAULT 1
                )
            ''')
            # Poll Votes Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS poll_votes (
                    poll_id INTEGER,
                    user_id INTEGER,
                    option_index INTEGER,
                    PRIMARY KEY (poll_id, user_id)
                )
            ''')
            # Options Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS options (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    option_type TEXT, -- 'call' or 'put'
                    strike_price REAL,
                    expiration_date TEXT,
                    premium REAL,
                    contracts INTEGER,
                    status TEXT DEFAULT 'active'
                )
            ''')
            # Birthdays Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS birthdays (
                    user_id INTEGER PRIMARY KEY,
                    month INTEGER,
                    day INTEGER
                )
            ''')
            # Starboard Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS starboard (
                    message_id INTEGER PRIMARY KEY,
                    starboard_message_id INTEGER
                )
            ''')
            # Transaction Logs Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS transaction_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT, -- 'daily', 'work', 'shop', etc.
                    amount INTEGER,
                    description TEXT,
                    timestamp TEXT
                )
            ''')
            # Live Roles Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS live_roles (
                    guild_id INTEGER PRIMARY KEY,
                    role_id INTEGER
                )
            ''')
            # Creator Profiles Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS creator_profiles (
                    user_id INTEGER PRIMARY KEY,
                    bio TEXT,
                    twitch TEXT,
                    youtube TEXT,
                    twitter TEXT,
                    kick TEXT,
                    tiktok TEXT
                )
            ''')
            # Streamer Subscriptions Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS streamer_subs (
                    user_id INTEGER,
                    streamer_name TEXT,
                    platform TEXT,
                    PRIMARY KEY (user_id, streamer_name, platform)
                )
            ''')
            # Clips Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS clips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    submitter_id INTEGER,
                    streamer_name TEXT,
                    url TEXT,
                    description TEXT,
                    upvotes INTEGER DEFAULT 0,
                    timestamp TEXT
                )
            ''')
            # Automod Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS automod_settings (
                    guild_id INTEGER PRIMARY KEY,
                    banned_words TEXT,
                    anti_spam INTEGER DEFAULT 1,
                    anti_caps INTEGER DEFAULT 1,
                    punishment TEXT DEFAULT 'warn'
                )
            ''')
            # Custom Commands Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS custom_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    trigger TEXT,
                    response TEXT
                )
            ''')
            # Reminders Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    channel_id INTEGER,
                    message TEXT,
                    remind_time TEXT
                )
            ''')
            # Clans Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS clans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    owner_id INTEGER,
                    bank INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1
                )
            ''')
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS clan_members (
                    user_id INTEGER PRIMARY KEY,
                    clan_id INTEGER
                )
            ''')
            # Quests Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS quests (
                    user_id INTEGER PRIMARY KEY,
                    quest_type TEXT,
                    target INTEGER,
                    progress INTEGER DEFAULT 0,
                    completed INTEGER DEFAULT 0,
                    date_assigned TEXT
                )
            ''')
            # Price Alerts Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    target_price REAL,
                    direction TEXT
                )
            ''')
            # Copy Trades Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS copy_trades (
                    follower_id INTEGER,
                    target_id INTEGER,
                    PRIMARY KEY (follower_id, target_id)
                )
            ''')
            # Active Bets Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS active_bets (
                    message_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    question TEXT,
                    pool_yes INTEGER DEFAULT 0,
                    pool_no INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'open'
                )
            ''')
            # Bet Entries Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS bet_entries (
                    message_id INTEGER,
                    user_id INTEGER,
                    choice TEXT,
                    amount INTEGER,
                    PRIMARY KEY (message_id, user_id)
                )
            ''')
            # Pets Table Migration for multiple pets
            try:
                # Check if it's the old schema (no 'id' column)
                await cursor.execute("SELECT id FROM pets LIMIT 1")
            except:
                try:
                    # It's the old schema, migrate it
                    await cursor.execute("ALTER TABLE pets RENAME TO pets_old")
                    await cursor.execute('''
                        CREATE TABLE pets (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            pet_type TEXT,
                            name TEXT,
                            level INTEGER DEFAULT 1,
                            xp INTEGER DEFAULT 0,
                            last_fed TEXT
                        )
                    ''')
                    await cursor.execute('''
                        INSERT INTO pets (user_id, pet_type, name, level, xp, last_fed)
                        SELECT user_id, pet_type, name, level, xp, last_fed FROM pets_old
                    ''')
                    await cursor.execute("DROP TABLE pets_old")
                except Exception as e:
                    print(f"Failed to migrate pets table: {e}")

            # Ensure table exists if fresh start
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS pets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    pet_type TEXT,
                    name TEXT,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    last_fed TEXT
                )
            ''')
            # VIP Roles Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS vip_roles (
                    guild_id INTEGER,
                    role_id INTEGER,
                    multiplier REAL DEFAULT 1.5,
                    PRIMARY KEY (guild_id, role_id)
                )
            ''')
            # Guild Settings Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    starboard_channel_id INTEGER,
                    starboard_threshold INTEGER DEFAULT 3,
                    starboard_emoji TEXT DEFAULT '⭐',
                    log_channel_id INTEGER,
                    auto_role_id INTEGER,
                    live_role_id INTEGER,
                    bot_admin_role_id INTEGER
                )
            ''')
            # Casino Jackpot Table
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS casino_jackpot (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    amount INTEGER DEFAULT 10000
                )
            ''')
            await cursor.execute("INSERT OR IGNORE INTO casino_jackpot (id, amount) VALUES (1, 10000)")
        await self.db.commit()

    async def close(self):
        await self.db.close()
        await super().close()

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            # Suggest closest match
            cmd = ctx.invoked_with
            all_cmds = [c.name for c in self.commands]
            matches = difflib.get_close_matches(cmd, all_cmds, n=1, cutoff=0.6)
            
            msg = f"Command `!{cmd}` not found."
            if matches:
                msg += f"\nDid you mean `!{matches[0]}`?"
            
            await ctx.send(embed=Embeds.error("Unknown Command", msg))
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=Embeds.warning("Cooldown", f"Try again <t:{int(datetime.datetime.now().timestamp() + error.retry_after)}:R>."))
            return

        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(embed=Embeds.error("Permission Denied", f"You need **{perms}** permissions."))
            return

        print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    async def on_error(self, event_method, *args, **kwargs):
        print(f"Ignoring exception in {event_method}:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    async def on_message(self, message):
        if message.author.bot:
            return
        
        # Add a sync command for admins
        if message.content == "!sync" and message.author.guild_permissions.administrator:
            try:
                # Sync globally
                synced = await self.tree.sync()
                # Clear any lingering guild-specific commands that cause duplicates
                self.tree.clear_commands(guild=message.guild)
                await self.tree.sync(guild=message.guild)
                await message.channel.send(f"✅ Synced {len(synced)} global commands and cleared duplicate guild commands.\n*Note: You may need to restart your Discord app to see the duplicates disappear.*")
            except Exception as e:
                await message.channel.send(f"Error syncing: {e}")
            return

        await self.process_commands(message)

bot = BOTR()

def cleanup_lock():
    """Removes the lock file on exit."""
    if os.path.exists("bot.lock"):
        try:
            os.remove("bot.lock")
        except OSError:
            pass

def check_single_instance():
    """Checks for an existing lock file and verifies if the process is actually running."""
    lock_file = "bot.lock"
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                content = f.read().strip()
                if content:
                    pid = int(content)
                    try:
                        # Check if process exists.
                        if sys.platform == 'win32':
                            cmd = f'tasklist /FI "PID eq {pid}"'
                            output = subprocess.check_output(cmd, creationflags=0x08000000).decode()
                            if str(pid) in output:
                                print(f"Error: Bot is already running (PID: {pid}). Aborting start.")
                                sys.exit(1)
                            else:
                                raise OSError("Process not found")
                        else:
                            os.kill(pid, 0)
                            print(f"Error: Bot is already running (PID: {pid}). Aborting start.")
                            sys.exit(1)
                    except (OSError, subprocess.CalledProcessError):
                        # Process dead or access denied (unlikely for own bot unless different user).
                        # We treat OSError usually as "process not found" for signal 0.
                        print(f"Found stale lock file for PID {pid}. Taking over.")
        except (ValueError, IOError) as e:
             print(f"Error reading lock file: {e}. Overwriting.")

    # Write current PID
    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
        atexit.register(cleanup_lock)
    except IOError as e:
        print(f"Could not write lock file: {e}")
        sys.exit(1)

if __name__ == '__main__':
    check_single_instance()
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in .env")
    else:
        bot.run(TOKEN)
