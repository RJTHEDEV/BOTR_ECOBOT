import discord
from discord.ext import commands
from utils.embeds import Embeds

class HelpSelect(discord.ui.Select):
    def __init__(self, bot, mapping):
        self.bot = bot
        self.mapping = mapping
        
        options = [
            discord.SelectOption(label="Home", description="Back to main menu", emoji="🏠", value="home")
        ]
        
        # Curated descriptions for cogs
        COG_DESCRIPTIONS = {
            "Economy": "Manage your wealth, work jobs, and rob others.",
            "Market": "Real-time stock/crypto prices, charts, and news.",
            "Community": "Social features, reputation, and server events.",
            "Moderation": "Admin tools to kick, ban, and manage the server.",
            "Polls": "Create interactive polls with real-time charts.",
            "Gambling": "Test your luck with slots, blackjack, and more.",
            "Alerts": "Market open/close notifications.",
            "Logging": "Audit logs for server activities.",
            "Paper Trading": "Simulate trading without real money.",
            "Store": "Buy items and upgrades with your coins.",
            "Streamers": "Live stream alerts for Twitch/YouTube.",
            "Tickets": "Support ticket system for members.",
            "Voice": "Dynamic voice channel management."
        }

        # Filter cogs that have commands
        for cog, commands_list in mapping.items():
            if not cog or not commands_list: continue
            
            label = cog.qualified_name
            # Get description from dict or fallback to cog default
            desc = COG_DESCRIPTIONS.get(label, cog.description if cog.description else "No description.")
            
            # Simple emoji mapping based on name
            emoji = "⚙️"
            if label == "Economy": emoji = "💰"
            elif label == "Market": emoji = "📈"
            elif label == "Community": emoji = "🤝"
            elif label == "Moderation": emoji = "🛡️"
            elif label == "Polls": emoji = "📊"
            elif label == "Gambling": emoji = "🎰"
            elif label == "Store": emoji = "🛒"
            elif label == "Tickets": emoji = "🎫"
            elif label == "Streamers": emoji = "📺"
            
            options.append(discord.SelectOption(label=label, description=desc[:100], emoji=emoji, value=label))

        super().__init__(placeholder="Select a category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        
        if value == "home":
            embed = Embeds.default("🤖 BOTR Help", "Select a category below to view commands.")
            embed.add_field(name="Stats", value=f"Servers: {len(self.bot.guilds)}\nLatency: {round(self.bot.latency * 1000)}ms")
            await interaction.response.edit_message(embed=embed)
            return

        cog = self.bot.get_cog(value)
        if not cog:
            await interaction.response.send_message("Category not found.", ephemeral=True)
            return

        commands_list = cog.get_commands()
        desc = ""
        for cmd in commands_list:
            if cmd.hidden: continue
            # Handle hybrid commands
            name = f"/{cmd.name}" if isinstance(cmd, commands.HybridCommand) else f"!{cmd.name}"
            desc += f"**{name}** - {cmd.description or 'No description'}\n"

        embed = Embeds.info(f"{cog.qualified_name} Commands", desc)
        await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    def __init__(self, bot, mapping):
        super().__init__(timeout=180)
        self.add_item(HelpSelect(bot, mapping))

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="Show the help menu.")
    async def help(self, ctx):
        print("Help command triggered!")
        try:
            mapping = self.bot.help_command.get_bot_mapping()
        except AttributeError:
            # If help_command is None, we need to build mapping manually
            print("Building mapping manually...")
            mapping = {cog: cog.get_commands() for cog in self.bot.cogs.values()}
            # Add standalone commands
            mapping[None] = [c for c in self.bot.commands if c.cog is None]
        
        print(f"Mapping keys: {mapping.keys()}")
        
        view = HelpView(self.bot, mapping)
        
        embed = Embeds.default("🤖 BOTR Help", "Select a category below to view commands.")
        embed.add_field(name="Stats", value=f"Servers: {len(self.bot.guilds)}\nLatency: {round(self.bot.latency * 1000)}ms")
        
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Help(bot))
