import discord
from discord.ext import commands, tasks
import json
import datetime
import asyncio

class PollButton(discord.ui.Button):
    def __init__(self, label, index, poll_id):
        super().__init__(style=discord.ButtonStyle.primary, label=label, custom_id=f"poll:{poll_id}:{index}")
        self.index = index
        self.poll_id = poll_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cog = interaction.client.get_cog("Polls")
        if cog:
            await cog.handle_vote(interaction, self.poll_id, self.index)

class PollSelect(discord.ui.Select):
    def __init__(self, options, poll_id):
        choices = [discord.SelectOption(label=opt[:100], value=str(i)) for i, opt in enumerate(options)]
        super().__init__(placeholder="Select an option...", min_values=1, max_values=1, options=choices, custom_id=f"poll_select:{poll_id}")
        self.poll_id = poll_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        index = int(self.values[0])
        cog = interaction.client.get_cog("Polls")
        if cog:
            await cog.handle_vote(interaction, self.poll_id, index)

class PollView(discord.ui.View):
    def __init__(self, poll_id, options):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.options = options
        
        if len(options) <= 5:
            for i, opt in enumerate(options):
                self.add_item(PollButton(opt, i, poll_id))
        else:
            self.add_item(PollSelect(options, poll_id))

class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_polls_loop.start()
        self.bot.loop.create_task(self.load_views())

    def cog_unload(self):
        self.check_polls_loop.cancel()

    async def load_views(self):
        # Re-register views for active polls on startup
        await self.bot.wait_until_ready()
        async with self.bot.db.execute("SELECT message_id, options FROM polls WHERE active = 1") as cursor:
            rows = await cursor.fetchall()
        
        for msg_id, options_json in rows:
            try:
                options = json.loads(options_json)
                self.bot.add_view(PollView(msg_id, options))
            except Exception as e:
                print(f"Failed to load poll {msg_id}: {e}")

    @tasks.loop(minutes=1)
    async def check_polls_loop(self):
        await self.bot.wait_until_ready()
        now = datetime.datetime.now().isoformat()
        
        async with self.bot.db.execute("SELECT message_id, channel_id, end_time FROM polls WHERE active = 1") as cursor:
            rows = await cursor.fetchall()
        
        for msg_id, channel_id, end_time in rows:
            if end_time and now >= end_time:
                await self.end_poll(msg_id, channel_id)

    async def handle_vote(self, interaction, poll_id, option_index):
        user_id = interaction.user.id
        
        # Check if poll is active
        async with self.bot.db.execute("SELECT active, options, question, end_time FROM polls WHERE message_id = ?", (poll_id,)) as cursor:
            row = await cursor.fetchone()
        
        if not row or not row[0]:
            await interaction.followup.send("This poll has ended.", ephemeral=True)
            return

        active, options_json, question, end_time = row
        options = json.loads(options_json)

        # Update Vote
        # Check if user already voted
        async with self.bot.db.execute("SELECT option_index FROM poll_votes WHERE poll_id = ? AND user_id = ?", (poll_id, user_id)) as cursor:
            vote_row = await cursor.fetchone()
        
        if vote_row:
            if vote_row[0] == option_index:
                await interaction.followup.send("You already voted for this option.", ephemeral=True)
                return
            else:
                # Change vote
                await self.bot.db.execute("UPDATE poll_votes SET option_index = ? WHERE poll_id = ? AND user_id = ?", (option_index, poll_id, user_id))
                await interaction.followup.send(f"Changed vote to: **{options[option_index]}**", ephemeral=True)
        else:
            # New vote
            await self.bot.db.execute("INSERT INTO poll_votes (poll_id, user_id, option_index) VALUES (?, ?, ?)", (poll_id, user_id, option_index))
            await interaction.followup.send(f"Voted for: **{options[option_index]}**", ephemeral=True)
        
        await self.bot.db.commit()
        
        # Update Embed
        await self.update_poll_message(poll_id, interaction.channel)

    async def update_poll_message(self, poll_id, channel=None):
        if not channel:
            # Fetch channel from DB if not provided
            async with self.bot.db.execute("SELECT channel_id FROM polls WHERE message_id = ?", (poll_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    channel = self.bot.get_channel(row[0])
        
        if not channel: return

        try:
            msg = await channel.fetch_message(poll_id)
        except:
            return

        # Get Poll Data
        async with self.bot.db.execute("SELECT question, options, end_time, active FROM polls WHERE message_id = ?", (poll_id,)) as cursor:
            row = await cursor.fetchone()
        
        if not row: return
        question, options_json, end_time, active = row
        options = json.loads(options_json)

        # Get Votes
        async with self.bot.db.execute("SELECT option_index, COUNT(*) FROM poll_votes WHERE poll_id = ? GROUP BY option_index", (poll_id,)) as cursor:
            vote_counts = await cursor.fetchall()
        
        counts = {i: 0 for i in range(len(options))}
        total_votes = 0
        for idx, count in vote_counts:
            counts[idx] = count
            total_votes += count

        # Build Embed
        embed = discord.Embed(title=f"📊 {question}", color=discord.Color.blue() if active else discord.Color.greyple())
        
        desc = ""
        for i, opt in enumerate(options):
            count = counts[i]
            pct = (count / total_votes * 100) if total_votes > 0 else 0
            
            # Bar Chart
            filled = int(pct / 10)
            bar = "█" * filled + "░" * (10 - filled)
            
            desc += f"**{opt}**\n{bar} {pct:.1f}% ({count})\n\n"
        
        embed.description = desc
        
        status = "🟢 Active" if active else "🔴 Ended"
        if end_time:
            dt = datetime.datetime.fromisoformat(end_time)
            ts = int(dt.timestamp())
            if active:
                embed.add_field(name="Status", value=f"{status} • Ends <t:{ts}:R>")
            else:
                embed.add_field(name="Status", value=f"{status} • Ended <t:{ts}:R>")
        else:
            embed.add_field(name="Status", value=status)
            
        embed.set_footer(text=f"Total Votes: {total_votes}")

        await msg.edit(embed=embed)

    async def end_poll(self, poll_id, channel_id):
        channel = self.bot.get_channel(channel_id)
        if not channel: return

        await self.bot.db.execute("UPDATE polls SET active = 0 WHERE message_id = ?", (poll_id,))
        await self.bot.db.commit()

        try:
            msg = await channel.fetch_message(poll_id)
            # Disable view
            await msg.edit(view=None)
            # Update embed one last time
            await self.update_poll_message(poll_id, channel)
            await channel.send(f"🛑 Poll ended: {msg.jump_url}")
        except:
            pass

    @commands.hybrid_command(description="Create a new poll.")
    async def poll(self, ctx, question: str, options: str, duration: str = None):
        """
        Create a poll.
        Options separated by | (pipe).
        Duration example: 10m, 1h, 24h.
        """
        opts = [o.strip() for o in options.split("|")]
        if len(opts) < 2:
            await ctx.send("You need at least 2 options.")
            return
        if len(opts) > 25:
            await ctx.send("Max 25 options.")
            return

        end_time_iso = None
        if duration:
            unit = duration[-1]
            try:
                val = int(duration[:-1])
                seconds = 0
                if unit == 'm': seconds = val * 60
                elif unit == 'h': seconds = val * 3600
                elif unit == 'd': seconds = val * 86400
                else:
                    await ctx.send("Invalid duration unit. Use m, h, or d.")
                    return
                
                end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
                end_time_iso = end_time.isoformat()
            except:
                await ctx.send("Invalid duration format.")
                return

        embed = discord.Embed(title=f"📊 {question}", description="Preparing poll...", color=discord.Color.blue())
        msg = await ctx.send(embed=embed)

        # Save to DB
        await self.bot.db.execute("INSERT INTO polls (message_id, channel_id, guild_id, author_id, question, options, end_time) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                  (msg.id, ctx.channel.id, ctx.guild.id, ctx.author.id, question, json.dumps(opts), end_time_iso))
        await self.bot.db.commit()

        # Start View
        view = PollView(msg.id, opts)
        await msg.edit(view=view)
        
        # Initial Update
        await self.update_poll_message(msg.id, ctx.channel)

    @commands.hybrid_command(description="End a poll early.")
    @commands.has_permissions(administrator=True)
    async def endpoll(self, ctx, message_id: str):
        try:
            mid = int(message_id)
            await self.end_poll(mid, ctx.channel.id)
            await ctx.send("Poll ended.")
        except ValueError:
            await ctx.send("Invalid message ID.")

async def setup(bot):
    await bot.add_cog(Polls(bot))
