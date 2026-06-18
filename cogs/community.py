import discord
from discord.ext import commands
import asyncio
import random
import datetime

class Community(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- News ---
    @commands.hybrid_command(description="Admin: Post a news update.")
    @commands.has_permissions(administrator=True)
    async def news(self, ctx, title: str, *, content: str):
        embed = discord.Embed(title=f"📰 {title}", description=content, color=discord.Color.blue())
        embed.set_footer(text=f"Posted by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Get info on how to claim the Active Developer Badge.")
    async def badge(self, ctx):
        await ctx.send("✅ **Command Executed!**\n\nTo claim your **Active Developer Badge**:\n1. Wait up to 24 hours for Discord to update.\n2. Go to: https://discord.com/developers/active-developer\n3. Select this bot and claim your badge!\n\n*(Running any slash command qualifies you, but this one confirms it works!)*")

    # --- Schedule ---
    @commands.hybrid_group(invoke_without_command=True, description="Manage streaming schedule.")
    async def schedule(self, ctx):
        await ctx.send("Use `!schedule view` or `!schedule add`")

    @schedule.command(description="View upcoming events.")
    async def view(self, ctx):
        async with self.bot.db.execute("SELECT event_name, event_time, description FROM schedule ORDER BY event_time") as cursor:
            events = await cursor.fetchall()
        
        if not events:
            await ctx.send("No upcoming events.")
            return

        embed = discord.Embed(title="📅 Streaming Schedule", color=discord.Color.purple())
        for name, time, desc in events:
            embed.add_field(name=f"{time} - {name}", value=desc, inline=False)
        await ctx.send(embed=embed)

    @schedule.command(description="Admin: Add an event to the schedule.")
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, time: str, name: str, *, description: str):
        await self.bot.db.execute("INSERT INTO schedule (event_name, event_time, description) VALUES (?, ?, ?)", (name, time, description))
        await self.bot.db.commit()
        await ctx.send(f"Added event: {name} at {time}")

    # --- Giveaways ---
    @commands.hybrid_command(description="Admin: Start a giveaway.")
    @commands.has_permissions(administrator=True)
    async def gstart(self, ctx, duration: str, winners: int, *, prize: str):
        # Simple duration parser (e.g., 10s, 1m, 1h)
        unit = duration[-1]
        try:
            val = int(duration[:-1])
        except ValueError:
            await ctx.send("Invalid duration format. Use 10s, 1m, 1h.")
            return

        seconds = 0
        if unit == 's': seconds = val
        elif unit == 'm': seconds = val * 60
        elif unit == 'h': seconds = val * 3600
        else:
            await ctx.send("Invalid unit. Use s, m, or h.")
            return

        embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"Prize: **{prize}**\nReact with 🎉 to enter!\nEnds in: {duration}", color=discord.Color.gold())
        embed.set_footer(text=f"{winners} winner(s)")
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("🎉")

        end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        await self.bot.db.execute("INSERT INTO giveaways (message_id, channel_id, prize, end_time, winners_count) VALUES (?, ?, ?, ?, ?)", 
                                  (msg.id, ctx.channel.id, prize, end_time.isoformat(), winners))
        await self.bot.db.commit()

        await asyncio.sleep(seconds)
        await self.end_giveaway(msg.id)

    async def end_giveaway(self, message_id):
        async with self.bot.db.execute("SELECT channel_id, prize, winners_count, ended FROM giveaways WHERE message_id = ?", (message_id,)) as cursor:
            data = await cursor.fetchone()
        
        if not data or data[3]: return # Already ended or doesn't exist

        channel_id, prize, winners_count, _ = data
        channel = self.bot.get_channel(channel_id)
        try:
            msg = await channel.fetch_message(message_id)
        except:
            return # Message deleted

        users = []
        async for user in msg.reactions[0].users():
            if not user.bot:
                users.append(user)

        if len(users) < winners_count:
            winners = users
        else:
            winners = random.sample(users, winners_count)

        if winners:
            winner_mentions = ", ".join([w.mention for w in winners])
            await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{prize}**!")
        else:
            await channel.send("No one entered the giveaway.")

        await self.bot.db.execute("UPDATE giveaways SET ended = 1 WHERE message_id = ?", (message_id,))
        await self.bot.db.commit()

    @commands.hybrid_command(description="Admin: End a giveaway early.")
    @commands.has_permissions(administrator=True)
    async def gend(self, ctx, message_id: int):
        await self.end_giveaway(message_id)

    @commands.hybrid_command(description="Admin: Reroll a giveaway winner.")
    @commands.has_permissions(administrator=True)
    async def greroll(self, ctx, message_id: int):
        # Simplified reroll logic (just picks one new winner)
        channel = ctx.channel
        try:
            msg = await channel.fetch_message(message_id)
        except:
            await ctx.send("Message not found.")
            return

        users = []
        async for user in msg.reactions[0].users():
            if not user.bot:
                users.append(user)

        if not users:
            await ctx.send("No valid entries.")
            return

        winner = random.choice(users)
        await ctx.send(f"🎉 New winner: {winner.mention}!")

    # --- Raffles ---
    @commands.hybrid_group(invoke_without_command=True, description="Manage raffles.")
    async def raffle(self, ctx):
        await ctx.send("Use `!raffle start`, `!raffle enter`, or `!raffle end`.")

    @raffle.command(description="Admin: Start a raffle.")
    @commands.has_permissions(administrator=True)
    async def start(self, ctx, prize: str, ticket_cost: int, duration: str):
        # Parse duration
        unit = duration[-1]
        try:
            val = int(duration[:-1])
        except ValueError:
            await ctx.send("Invalid duration. Use 10s, 1m, 1h.")
            return

        seconds = 0
        if unit == 's': seconds = val
        elif unit == 'm': seconds = val * 60
        elif unit == 'h': seconds = val * 3600
        else:
            await ctx.send("Invalid unit.")
            return

        embed = discord.Embed(title="🎟️ RAFFLE STARTED 🎟️", description=f"Prize: **{prize}**\nTicket Cost: **{ticket_cost}** 🎟️\nUse `!raffle enter <amount>` to join!", color=discord.Color.magenta())
        embed.set_footer(text=f"Ends in: {duration}")
        msg = await ctx.send(embed=embed)

        await self.bot.db.execute("INSERT INTO raffles (channel_id, message_id, prize, ticket_cost) VALUES (?, ?, ?, ?)", 
                                  (ctx.channel.id, msg.id, prize, ticket_cost))
        await self.bot.db.commit()

        # Auto-end task (simplified: just sleep)
        # In production, use a background task loop to check DB for ended raffles
        await asyncio.sleep(seconds)
        await self.end_raffle(msg.id)

    @raffle.command(description="Enter the current raffle.")
    async def enter(self, ctx, entries: int):
        if entries <= 0:
            await ctx.send("Entries must be positive.")
            return

        # Find active raffle in channel
        async with self.bot.db.execute("SELECT raffle_id, ticket_cost, ended FROM raffles WHERE channel_id = ? AND ended = 0 ORDER BY raffle_id DESC LIMIT 1", (ctx.channel.id,)) as cursor:
            raffle = await cursor.fetchone()
        
        if not raffle:
            await ctx.send("No active raffle in this channel.")
            return

        raffle_id, cost, ended = raffle
        total_cost = cost * entries

        # Check tickets
        async with self.bot.db.execute("SELECT tickets FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            user = await cursor.fetchone()
        
        if not user or user[0] < total_cost:
            await ctx.send(f"Not enough tickets! Cost: {total_cost}, You have: {user[0] if user else 0}")
            return

        # Deduct tickets
        await self.bot.db.execute("UPDATE users SET tickets = tickets - ? WHERE user_id = ?", (total_cost, ctx.author.id))

        # Add entries
        async with self.bot.db.execute("SELECT entries_count FROM raffle_entries WHERE raffle_id = ? AND user_id = ?", (raffle_id, ctx.author.id)) as cursor:
            entry = await cursor.fetchone()
        
        if entry:
            await self.bot.db.execute("UPDATE raffle_entries SET entries_count = entries_count + ? WHERE raffle_id = ? AND user_id = ?", (entries, raffle_id, ctx.author.id))
        else:
            await self.bot.db.execute("INSERT INTO raffle_entries (raffle_id, user_id, entries_count) VALUES (?, ?, ?)", (raffle_id, ctx.author.id, entries))
        
        await self.bot.db.commit()
        await ctx.send(f"Bought {entries} entries for 🎟️ {total_cost}!")

    async def end_raffle(self, message_id):
        async with self.bot.db.execute("SELECT raffle_id, channel_id, prize, ended FROM raffles WHERE message_id = ?", (message_id,)) as cursor:
            raffle = await cursor.fetchone()
        
        if not raffle or raffle[3]: return

        raffle_id, channel_id, prize, _ = raffle
        channel = self.bot.get_channel(channel_id)

        # Get entries (weighted)
        async with self.bot.db.execute("SELECT user_id, entries_count FROM raffle_entries WHERE raffle_id = ?", (raffle_id,)) as cursor:
            entries = await cursor.fetchall()
        
        pool = []
        for user_id, count in entries:
            pool.extend([user_id] * count)

        if pool:
            winner_id = random.choice(pool)
            winner = channel.guild.get_member(winner_id)
            mention = winner.mention if winner else f"User ID {winner_id}"
            await channel.send(f"🎟️ The raffle for **{prize}** has ended!\nWinner: {mention} 🎉")
        else:
            await channel.send(f"🎟️ The raffle for **{prize}** has ended. No entries.")

        await self.bot.db.execute("UPDATE raffles SET ended = 1 WHERE raffle_id = ?", (raffle_id,))
        await self.bot.db.commit()

    @raffle.command(name="end", description="Admin: End a raffle early.")
    @commands.has_permissions(administrator=True)
    async def end_cmd(self, ctx, message_id: int):
        await self.end_raffle(message_id)

    # --- Welcome ---
    @commands.hybrid_group(invoke_without_command=True, description="Manage welcome messages.")
    async def welcome(self, ctx):
        await ctx.send("Use `/welcome set <channel>` or `/welcome test`.")

    @welcome.command(description="Set the welcome channel.")
    @commands.has_permissions(administrator=True)
    async def set(self, ctx, channel: discord.TextChannel):
        await self.bot.db.execute("INSERT OR REPLACE INTO welcome_settings (guild_id, channel_id) VALUES (?, ?)", (ctx.guild.id, channel.id))
        await self.bot.db.commit()
        await ctx.send(f"✅ Welcome messages will be sent to {channel.mention}.")

    @welcome.command(description="Test the welcome message.")
    @commands.has_permissions(administrator=True)
    async def test(self, ctx):
        await self.send_welcome_message(ctx.guild, ctx.author, ctx.channel)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Auto Role
        async with self.bot.db.execute("SELECT role_id FROM auto_roles WHERE guild_id = ?", (member.guild.id,)) as cursor:
            auto_role_row = await cursor.fetchone()
        
        if auto_role_row:
            role = member.guild.get_role(auto_role_row[0])
            if role:
                try:
                    await member.add_roles(role, reason="Auto Role")
                except discord.Forbidden:
                    pass

        # Check if welcome channel is set
        async with self.bot.db.execute("SELECT channel_id FROM welcome_settings WHERE guild_id = ?", (member.guild.id,)) as cursor:
            row = await cursor.fetchone()
        
        if row:
            channel = member.guild.get_channel(row[0])
            if channel:
                await self.send_welcome_message(member.guild, member, channel)

    async def send_welcome_message(self, guild, member, channel):
        # Helper to find channel by name
        def get_chan(names):
            for ch in guild.text_channels + guild.voice_channels:
                if any(n.lower() in ch.name.lower() for n in names):
                    return ch
            return None

        # Find key channels
        rules_ch = get_chan(["official-rules", "rules"])
        intro_ch = get_chan(["introduce-yourself", "introductions"])
        announce_ch = get_chan(["announcements"])
        general_ch = get_chan(["general-chat", "general"])
        hangout_ch = get_chan(["hangout", "lounge"])

        # Build Description
        desc = f"Welcome to the **{guild.name}** community! 🚀 We're excited to have you here!\n\n"
        
        desc += "🔹 **What We Offer:**\n"
        desc += "🔥 A chill gaming community\n"
        desc += "💬 Fun chats & voice channels\n"
        desc += "🎉 Events, giveaways & more!\n\n"

        desc += "✅ **Get Started:**\n"
        if intro_ch: desc += f"1️⃣ Introduce Yourself in {intro_ch.mention}\n"
        if rules_ch: desc += f"2️⃣ Read the Rules in {rules_ch.mention}\n"
        if announce_ch: desc += f"3️⃣ Check Announcements in {announce_ch.mention}\n"
        
        join_fun = []
        if general_ch: join_fun.append(general_ch.mention)
        if hangout_ch: join_fun.append(hangout_ch.mention)
        
        if join_fun:
            desc += f"4️⃣ Join the Fun! Play, chat, and enjoy in {' or '.join(join_fun)}!\n"

        desc += f"\nIf you have any questions, feel free to ask our mods. Let's game on! 🎮✨"

        embed = discord.Embed(description=desc, color=discord.Color.teal())
        embed.set_author(name=f"Welcome {member.display_name} to {guild.name}!", icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"We are now {guild.member_count} members!")

        await channel.send(content=f"👋 Welcome {member.mention} to **{guild.name}**! 🎮", embed=embed)

    # --- Auto Role ---
    @commands.hybrid_group(invoke_without_command=True, description="Manage auto role settings.")
    async def autorole(self, ctx):
        await ctx.send("Use `/autorole set <role>` or `/autorole remove`.")

    @autorole.command(name="set", description="Set the auto role for new members.")
    @commands.has_permissions(administrator=True)
    async def set_autorole(self, ctx, role: discord.Role):
        await self.bot.db.execute("INSERT OR REPLACE INTO auto_roles (guild_id, role_id) VALUES (?, ?)", (ctx.guild.id, role.id))
        await self.bot.db.commit()
        await ctx.send(f"✅ Auto role set to **{role.name}**.")

    @autorole.command(name="remove", description="Remove the auto role.")
    @commands.has_permissions(administrator=True)
    async def remove_autorole(self, ctx):
        await self.bot.db.execute("DELETE FROM auto_roles WHERE guild_id = ?", (ctx.guild.id,))
        await self.bot.db.commit()
        await ctx.send("✅ Auto role removed.")

    # --- Starboard ---
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if str(payload.emoji) != "⭐": return
        
        channel = self.bot.get_channel(payload.channel_id)
        try:
            message = await channel.fetch_message(payload.message_id)
        except:
            return

        reaction = discord.utils.get(message.reactions, emoji="⭐")
        if not reaction or reaction.count < 3: return # Threshold: 3

        # Check if already posted
        async with self.bot.db.execute("SELECT starboard_message_id FROM starboard WHERE message_id = ?", (message.id,)) as cursor:
            row = await cursor.fetchone()
        
        starboard_channel = discord.utils.get(message.guild.text_channels, name="starboard")
        
        # Create channel if not exists
        if not starboard_channel:
            try:
                starboard_channel = await message.guild.create_text_channel("starboard")
            except:
                return # Missing permissions

        embed = discord.Embed(description=message.content, color=discord.Color.gold())
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        embed.add_field(name="Source", value=f"[Jump to Message]({message.jump_url})")
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)
        embed.set_footer(text=f"⭐ {reaction.count} | {message.created_at.strftime('%Y-%m-%d %H:%M')}")

        if row:
            # Update existing
            try:
                sb_msg = await starboard_channel.fetch_message(row[0])
                await sb_msg.edit(embed=embed)
            except:
                pass # Message deleted
        else:
            # Post new
            sb_msg = await starboard_channel.send(embed=embed)
            await self.bot.db.execute("INSERT INTO starboard (message_id, starboard_message_id) VALUES (?, ?)", (message.id, sb_msg.id))
            await self.bot.db.commit()

    # --- Birthdays ---
    @commands.hybrid_group(name="birthday", invoke_without_command=True, description="Manage birthdays.")
    async def birthday(self, ctx):
        await ctx.send("Use `/birthday set <MM-DD>` or `/birthday list`.")

    @birthday.command(description="Set your birthday (MM-DD).")
    async def set(self, ctx, date: str):
        try:
            month, day = map(int, date.split("-"))
            datetime.date(2000, month, day) # Validate date
        except ValueError:
            await ctx.send("Invalid format. Use MM-DD (e.g., 12-25).")
            return

        await self.bot.db.execute("INSERT OR REPLACE INTO birthdays (user_id, month, day) VALUES (?, ?, ?)", (ctx.author.id, month, day))
        await self.bot.db.commit()
        await ctx.send(f"✅ Birthday set to **{month}/{day}**!")

    @birthday.command(name="list", description="List upcoming birthdays.")
    async def list_birthdays(self, ctx):
        async with self.bot.db.execute("SELECT user_id, month, day FROM birthdays ORDER BY month, day") as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("No birthdays set.")
            return

        embed = discord.Embed(title="🎂 Upcoming Birthdays", color=discord.Color.pink())
        today = datetime.date.today()
        
        count = 0
        for uid, m, d in rows:
            bday = datetime.date(today.year, m, d)
            if bday < today: bday = datetime.date(today.year + 1, m, d)
            
            if (bday - today).days <= 30: # Show next 30 days
                user = ctx.guild.get_member(uid)
                name = user.display_name if user else f"User {uid}"
                embed.add_field(name=f"{m}/{d}", value=name, inline=True)
                count += 1
        
        if count == 0:
            embed.description = "No birthdays in the next 30 days."
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Create a button-based reaction role menu.")
    @commands.has_permissions(administrator=True)
    async def buttonroles(self, ctx, title: str, description: str, role1: discord.Role, role2: discord.Role = None, role3: discord.Role = None, role4: discord.Role = None, role5: discord.Role = None):
        view = discord.ui.View(timeout=None)
        roles = [r for r in [role1, role2, role3, role4, role5] if r]
        
        if len(roles) > 1:
            all_ids = ",".join(str(r.id) for r in roles)
            btn = discord.ui.Button(label="All", style=discord.ButtonStyle.blurple, custom_id=f"rr:all:{all_ids}")
            view.add_item(btn)
        
        for role in roles:
            style = discord.ButtonStyle.secondary
            name_lower = role.name.lower()
            if "red" in name_lower: style = discord.ButtonStyle.danger
            elif "green" in name_lower: style = discord.ButtonStyle.success
            elif "blue" in name_lower: style = discord.ButtonStyle.primary
            
            btn = discord.ui.Button(label=role.name, style=style, custom_id=f"rr:single:{role.id}")
            view.add_item(btn)
        
        embed = discord.Embed(title=title, description=description, color=discord.Color.dark_theme())
        await ctx.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.type == discord.InteractionType.component: return
        custom_id = interaction.data.get('custom_id', '')
        if not custom_id.startswith('rr:'): return
        
        parts = custom_id.split(':')
        if len(parts) < 3: return
        action = parts[1]
        
        if action == "all":
            role_ids = parts[2].split(',')
            roles = [interaction.guild.get_role(int(r_id)) for r_id in role_ids]
            roles = [r for r in roles if r]
            
            has_all = all(r in interaction.user.roles for r in roles)
            
            if has_all:
                await interaction.user.remove_roles(*roles)
                await interaction.response.send_message("Removed all roles.", ephemeral=True)
            else:
                await interaction.user.add_roles(*roles)
                await interaction.response.send_message("Added all roles.", ephemeral=True)
        elif action == "single":
            role_id = int(parts[2])
            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message("Role not found.", ephemeral=True)
                return
            
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(f"Removed {role.name}.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"Added {role.name}.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Community(bot))
