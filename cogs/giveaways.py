import discord
from discord.ext import commands, tasks
import datetime
import random

class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @commands.hybrid_command(name="giveaway", description="Start a new giveaway.")
    @commands.has_permissions(administrator=True)
    async def start_giveaway(self, ctx, duration_minutes: int, winners_count: int, *, prize: str):
        if duration_minutes <= 0 or winners_count <= 0:
            await ctx.send("Duration and winners must be > 0.")
            return

        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        timestamp = int(end_time.timestamp())

        embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"**Prize:** {prize}\n**Winners:** {winners_count}\n**Ends:** <t:{timestamp}:R>", color=discord.Color.purple())
        
        view = discord.ui.View(timeout=None)
        button = discord.ui.Button(label="Enter (0)", style=discord.ButtonStyle.blurple, emoji="🎉", custom_id="giveaway_enter")
        view.add_item(button)

        msg = await ctx.send(embed=embed, view=view)

        await self.bot.db.execute("INSERT INTO giveaways (message_id, channel_id, prize, end_time, winners_count, ended) VALUES (?, ?, ?, ?, ?, 0)",
                                  (msg.id, ctx.channel.id, prize, end_time.isoformat(), winners_count))
        await self.bot.db.commit()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.message or not interaction.data: return
        custom_id = interaction.data.get("custom_id")
        
        if custom_id == "giveaway_enter":
            msg_id = interaction.message.id
            user_id = interaction.user.id
            
            # Check if giveaway is active
            async with self.bot.db.execute("SELECT ended FROM giveaways WHERE message_id = ?", (msg_id,)) as cursor:
                row = await cursor.fetchone()
                if not row or row[0]:
                    await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
                    return
            
            # Add entry
            try:
                await self.bot.db.execute("INSERT INTO giveaway_entries (message_id, user_id) VALUES (?, ?)", (msg_id, user_id))
                await self.bot.db.commit()
                
                # Update button count
                async with self.bot.db.execute("SELECT COUNT(*) FROM giveaway_entries WHERE message_id = ?", (msg_id,)) as cursor:
                    count = (await cursor.fetchone())[0]
                    
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    if getattr(child, "custom_id", None) == "giveaway_enter":
                        child.label = f"Enter ({count})"
                        break
                await interaction.message.edit(view=view)
                await interaction.response.send_message("You entered the giveaway!", ephemeral=True)
            except:
                # Likely a unique constraint failure (already entered)
                await interaction.response.send_message("You have already entered this giveaway.", ephemeral=True)

    @tasks.loop(minutes=1)
    async def check_giveaways(self):
        now = datetime.datetime.now().isoformat()
        
        async with self.bot.db.execute("SELECT message_id, channel_id, prize, winners_count FROM giveaways WHERE end_time <= ? AND ended = 0", (now,)) as cursor:
            ended_giveaways = await cursor.fetchall()
            
        for msg_id, chan_id, prize, winners_count in ended_giveaways:
            await self.bot.db.execute("UPDATE giveaways SET ended = 1 WHERE message_id = ?", (msg_id,))
            await self.bot.db.commit()
            
            channel = self.bot.get_channel(chan_id)
            if not channel: continue
            
            async with self.bot.db.execute("SELECT user_id FROM giveaway_entries WHERE message_id = ?", (msg_id,)) as cursor:
                entries = await cursor.fetchall()
                
            winners = []
            if entries:
                winner_ids = random.sample([e[0] for e in entries], min(len(entries), winners_count))
                winners = [f"<@{w}>" for w in winner_ids]
            
            try:
                msg = await channel.fetch_message(msg_id)
                embed = msg.embeds[0]
                embed.color = discord.Color.default()
                embed.description = f"**Prize:** {prize}\n**Ended!**\n**Winners:** {', '.join(winners) if winners else 'No valid entries.'}"
                
                # Disable button
                view = discord.ui.View.from_message(msg)
                for child in view.children:
                    child.disabled = True
                
                await msg.edit(embed=embed, view=view)
                
                if winners:
                    await channel.send(f"🎉 Congratulations {', '.join(winners)}! You won **{prize}**!\n[Jump to Giveaway]({msg.jump_url})")
                else:
                    await channel.send(f"😔 Nobody entered the giveaway for **{prize}**.")
            except: pass

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Giveaways(bot))
