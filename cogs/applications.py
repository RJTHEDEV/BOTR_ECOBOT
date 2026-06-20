import discord
from discord.ext import commands

class PersistentApplicationReviewView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="persistent_app_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Disable buttons
        for child in self.children:
            child.disabled = True
            
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        footer_text = embed.footer.text
        
        try:
            # Extract user ID from footer "User ID: 123456789"
            user_id_str = footer_text.split("User ID: ")[1].split(" |")[0]
            user_id = int(user_id_str)
        except:
            user_id = None

        embed.set_footer(text=f"{footer_text} | Accepted by {interaction.user}")
        await interaction.message.edit(embed=embed, view=self)

        if user_id:
            user = interaction.guild.get_member(user_id)
            if user:
                try:
                    await user.send(f"🎉 Your application in **{interaction.guild.name}** has been **ACCEPTED**!")
                except:
                    pass
        await interaction.response.send_message("Application accepted.", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="persistent_app_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
            
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        footer_text = embed.footer.text
        
        try:
            user_id_str = footer_text.split("User ID: ")[1].split(" |")[0]
            user_id = int(user_id_str)
        except:
            user_id = None

        embed.set_footer(text=f"{footer_text} | Denied by {interaction.user}")
        await interaction.message.edit(embed=embed, view=self)

        if user_id:
            user = interaction.guild.get_member(user_id)
            if user:
                try:
                    await user.send(f"❌ Your application in **{interaction.guild.name}** has been **DENIED**.")
                except:
                    pass
        await interaction.response.send_message("Application denied.", ephemeral=True)


class ApplicationModalPart2(discord.ui.Modal):
    def __init__(self, bot, target_channel_id, all_questions, part1_values, title="Application Form"):
        super().__init__(title=(title + " (Part 2)")[:45])
        self.bot = bot
        self.target_channel_id = target_channel_id
        self.all_questions = all_questions
        self.part1_values = part1_values
        self.q_start = 5
        self.q_count = len(all_questions[5:])
        
        for i, q in enumerate(all_questions[5:]):
            style = discord.TextStyle.short if len(q) < 15 and "?" not in q else discord.TextStyle.paragraph
            text_input = discord.ui.TextInput(
                label=q[:45],
                style=style,
                required=True,
                max_length=1000,
                custom_id=f"question_{i+5}"
            )
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Your application has been submitted successfully!", ephemeral=True)
        
        target_channel = interaction.guild.get_channel(self.target_channel_id)
        if not target_channel: return
        
        embed = discord.Embed(title=f"New Application: {interaction.user.name}", color=discord.Color.gold())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
        
        # Add Part 1
        for i in range(5):
            embed.add_field(name=self.all_questions[i][:256], value=self.part1_values[i][:1024], inline=False)
            
        # Add Part 2
        for i in range(self.q_count):
            embed.add_field(name=self.all_questions[i+5][:256], value=self.children[i].value[:1024], inline=False)

        embed.set_footer(text=f"User ID: {interaction.user.id}")
        view = PersistentApplicationReviewView(self.bot)
        await target_channel.send(embed=embed, view=view)


class ApplicationModalPart1(discord.ui.Modal):
    def __init__(self, bot, target_channel_id, all_questions, title="Application Form"):
        super().__init__(title=(title + " (Part 1)")[:45] if len(all_questions) > 5 else title[:45])
        self.bot = bot
        self.target_channel_id = target_channel_id
        self.all_questions = all_questions
        self.is_multipart = len(all_questions) > 5
        
        for i, q in enumerate(all_questions[:5]):
            style = discord.TextStyle.short if len(q) < 15 and "?" not in q else discord.TextStyle.paragraph
            text_input = discord.ui.TextInput(
                label=q[:45],
                style=style,
                required=True,
                max_length=1000,
                custom_id=f"question_{i}"
            )
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        part1_values = [child.value for child in self.children]
        
        if self.is_multipart:
            # Open Part 2
            panel_title = self.title.replace(" (Part 1)", "")
            modal2 = ApplicationModalPart2(self.bot, self.target_channel_id, self.all_questions, part1_values, title=panel_title)
            await interaction.response.send_modal(modal2)
        else:
            # Submit normally
            await interaction.response.send_message("✅ Your application has been submitted successfully!", ephemeral=True)
            target_channel = interaction.guild.get_channel(self.target_channel_id)
            if not target_channel: return
            
            embed = discord.Embed(title=f"New Application: {interaction.user.name}", color=discord.Color.gold())
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
            
            for i, q in enumerate(self.all_questions):
                embed.add_field(name=q[:256], value=part1_values[i][:1024], inline=False)

            embed.set_footer(text=f"User ID: {interaction.user.id}")
            view = PersistentApplicationReviewView(self.bot)
            await target_channel.send(embed=embed, view=view)


class ApplicationPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Apply Now", style=discord.ButtonStyle.blurple, custom_id="create_application", emoji="📝")
    async def apply_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Fetch target channel and questions from db
        query = "SELECT target_channel_id, q1, q2, q3, q4, q5, q6, q7, q8, q9, q10 FROM application_panels WHERE message_id = ?"
        
        async with self.bot.db.execute(query, (interaction.message.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message("❌ This application panel is broken or no longer valid.", ephemeral=True)
                return
            target_channel_id = row[0]
            
            # Filter out null/empty questions
            questions = [q for q in row[1:11] if q]
            
            # Default questions if none set (for older panels)
            if not questions:
                questions = [
                    "Why do you want to join/apply?",
                    "What is your experience?",
                    "How active can you be?",
                    "Any additional information?"
                ]

        panel_title = interaction.message.embeds[0].title if interaction.message.embeds else "Application Form"
        modal = ApplicationModalPart1(self.bot, target_channel_id, questions, title=panel_title)
        await interaction.response.send_modal(modal)


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Ensure table exists with up to 10 custom question columns
        async with self.bot.db.cursor() as cursor:
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS application_panels (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    guild_id INTEGER,
                    title TEXT,
                    description TEXT,
                    target_channel_id INTEGER,
                    q1 TEXT,
                    q2 TEXT,
                    q3 TEXT,
                    q4 TEXT,
                    q5 TEXT,
                    q6 TEXT,
                    q7 TEXT,
                    q8 TEXT,
                    q9 TEXT,
                    q10 TEXT
                )
            ''')
            # Add columns for migrations
            try: await cursor.execute("ALTER TABLE application_panels ADD COLUMN q1 TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE application_panels ADD COLUMN q2 TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE application_panels ADD COLUMN q3 TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE application_panels ADD COLUMN q4 TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE application_panels ADD COLUMN q5 TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE application_panels ADD COLUMN q6 TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE application_panels ADD COLUMN q7 TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE application_panels ADD COLUMN q8 TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE application_panels ADD COLUMN q9 TEXT")
            except: pass
            try: await cursor.execute("ALTER TABLE application_panels ADD COLUMN q10 TEXT")
            except: pass
        await self.bot.db.commit()

        self.bot.add_view(ApplicationPanelView(self.bot))
        self.bot.add_view(PersistentApplicationReviewView(self.bot))

    @commands.hybrid_group(name="apply", description="Manage applications.")
    async def apply(self, ctx):
        pass

    @apply.command(name="panel", description="Create an application panel with up to 10 custom questions.")
    @discord.app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def panel(self, ctx, target_channel: discord.TextChannel, title: str, description: str, 
                    q1: str, q2: str = None, q3: str = None, q4: str = None, q5: str = None, 
                    q6: str = None, q7: str = None, q8: str = None, q9: str = None, q10: str = None):
        embed = discord.Embed(title=title, description=description, color=discord.Color.gold())
        view = ApplicationPanelView(self.bot)
        
        msg = await ctx.send(embed=embed, view=view)
        
        await self.bot.db.execute('''INSERT INTO application_panels 
                                  (message_id, channel_id, guild_id, title, description, target_channel_id, 
                                  q1, q2, q3, q4, q5, q6, q7, q8, q9, q10) 
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                  (msg.id, ctx.channel.id, ctx.guild.id, title, description, target_channel.id, 
                                   q1, q2, q3, q4, q5, q6, q7, q8, q9, q10))
        await self.bot.db.commit()
        
        try: await ctx.message.delete()
        except: pass
        await ctx.send(f"✅ Application panel created! Applications will be sent to {target_channel.mention}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Applications(bot))
