import discord
from discord.ext import commands
import aiofiles
import os
import datetime

class TicketView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user already has an open ticket
        async with self.bot.db.execute("SELECT channel_id FROM tickets WHERE user_id = ? AND guild_id = ? AND status = 'open'", 
                                       (interaction.user.id, interaction.guild.id)) as cursor:
            if await cursor.fetchone():
                await interaction.response.send_message("❌ You already have an open ticket!", ephemeral=True)
                return

        await interaction.response.send_message("Creating your ticket...", ephemeral=True)

        # Create Private Channel
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Add admin/mod roles to overwrites if needed (simplified here to just admins/mods with perms)
        # Ideally, we'd have a config for "Support Role"
        
        channel_name = f"ticket-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=interaction.channel.category)

        # Save to DB
        await self.bot.db.execute("INSERT INTO tickets (channel_id, guild_id, user_id, panel_message_id, status) VALUES (?, ?, ?, ?, ?)",
                                  (ticket_channel.id, guild.id, interaction.user.id, interaction.message.id, 'open'))
        await self.bot.db.commit()

        # Send Welcome Message
        embed = discord.Embed(title=f"Ticket for {interaction.user.name}", 
                              description="Support will be with you shortly.\nTo close this ticket, use `/close`.",
                              color=discord.Color.green())
        await ticket_channel.send(content=f"{interaction.user.mention}", embed=embed)

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Register the persistent view for listening to interactions
        self.bot.add_view(TicketView(self.bot))

    @commands.hybrid_group(name="panel", description="Manage ticket panels.")
    async def panel(self, ctx):
        pass

    @panel.command(name="create", description="Create a new ticket panel.")
    @commands.has_permissions(administrator=True)
    async def create(self, ctx, title: str = "Support Ticket", description: str = "Click the button below to open a ticket.", button_label: str = "Create Ticket"):
        embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
        view = TicketView(self.bot)
        # Update button label if needed (requires dynamic view recreation or modifying the item)
        view.children[0].label = button_label
        
        msg = await ctx.send(embed=embed, view=view)
        
        await self.bot.db.execute("INSERT INTO ticket_panels (message_id, channel_id, guild_id, title, description, button_label) VALUES (?, ?, ?, ?, ?, ?)",
                                  (msg.id, ctx.channel.id, ctx.guild.id, title, description, button_label))
        await self.bot.db.commit()
        
        await ctx.send("✅ Ticket panel created!", ephemeral=True)

    @commands.hybrid_command(description="Close the current ticket.")
    async def close(self, ctx):
        async with self.bot.db.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (ctx.channel.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await ctx.send("❌ This is not a ticket channel.", ephemeral=True)
                return
            
            user_id = row[0]

        await ctx.send("🔒 Closing ticket in 5 seconds...")
        
        # Generate Transcript
        messages = [message async for message in ctx.channel.history(limit=None, oldest_first=True)]
        transcript_text = f"Transcript for {ctx.channel.name}\nUser ID: {user_id}\nDate: {datetime.datetime.now()}\n\n"
        
        for msg in messages:
            transcript_text += f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author.name}: {msg.content}\n"
            for att in msg.attachments:
                transcript_text += f"[Attachment] {att.url}\n"

        # Save transcript to file
        filename = f"transcript-{ctx.channel.name}-{ctx.message.id}.txt"
        async with aiofiles.open(filename, mode='w', encoding='utf-8') as f:
            await f.write(transcript_text)

        # Log to log channel (if configured)
        async with self.bot.db.execute("SELECT channel_id FROM log_settings WHERE guild_id = ? AND log_type = 'other'", (ctx.guild.id,)) as cursor:
            log_row = await cursor.fetchone()
            if log_row:
                log_channel = ctx.guild.get_channel(log_row[0])
                if log_channel:
                    await log_channel.send(f"📕 **Ticket Closed**: {ctx.channel.name}", file=discord.File(filename))

        # Clean up file
        try:
            os.remove(filename)
        except:
            pass

        # Close Ticket in DB
        await self.bot.db.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (ctx.channel.id,))
        await self.bot.db.commit()

        # Delete Channel
        await ctx.channel.delete()

    @commands.hybrid_command(description="Add a user to the ticket.")
    @commands.has_permissions(manage_channels=True)
    async def add(self, ctx, user: discord.Member):
        async with self.bot.db.execute("SELECT 1 FROM tickets WHERE channel_id = ?", (ctx.channel.id,)) as cursor:
            if not await cursor.fetchone():
                await ctx.send("❌ This is not a ticket channel.", ephemeral=True)
                return

        await ctx.channel.set_permissions(user, read_messages=True, send_messages=True)
        await ctx.send(f"✅ Added {user.mention} to the ticket.")

    @commands.hybrid_command(description="Remove a user from the ticket.")
    @commands.has_permissions(manage_channels=True)
    async def remove(self, ctx, user: discord.Member):
        async with self.bot.db.execute("SELECT 1 FROM tickets WHERE channel_id = ?", (ctx.channel.id,)) as cursor:
            if not await cursor.fetchone():
                await ctx.send("❌ This is not a ticket channel.", ephemeral=True)
                return

        await ctx.channel.set_permissions(user, overwrite=None)
        await ctx.send(f"👋 Removed {user.mention} from the ticket.")

    @commands.hybrid_command(description="Claim this ticket.")
    @commands.has_permissions(manage_channels=True)
    async def claim(self, ctx):
        async with self.bot.db.execute("SELECT 1 FROM tickets WHERE channel_id = ?", (ctx.channel.id,)) as cursor:
            if not await cursor.fetchone():
                await ctx.send("❌ This is not a ticket channel.", ephemeral=True)
                return

        await ctx.channel.send(f"👮 **{ctx.author.mention}** has claimed this ticket!")
        # Logic to edit channel name or topic could go here

async def setup(bot):
    await bot.add_cog(Tickets(bot))
