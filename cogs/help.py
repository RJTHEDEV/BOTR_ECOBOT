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
            "Economy": "Manage wealth, jobs, xp leaderboard, and robbing.",
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
            "Voice": "Dynamic voice channel management.",
            "External": "News headlines and Twitter integration.",
            "Help": "Shows this help menu.",
            "Options": "Trade stock options (calls/puts) and check expiry.",
            "PaperTrading": "Simulate stock trading without real money.",
            "Utility": "User info, server info, and avatar lookup.",
            "Games": "Social games like Connect 4 and Tic-Tac-Toe."
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
            elif label == "Tickets": emoji = "🎫"
            elif label == "Streamers": emoji = "📺"
            elif label == "External": emoji = "🌐"
            elif label == "Help": emoji = "ℹ️"
            elif label == "Options": emoji = "📉"
            elif label == "PaperTrading": emoji = "📝"
            elif label == "Utility": emoji = "🛠️"
            elif label == "Games": emoji = "🎮"
            
            options.append(discord.SelectOption(label=label, description=desc[:100], emoji=emoji, value=label))

        super().__init__(placeholder="Select a category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        
        if value == "home":
            embed = Embeds.default("🤖 ALL WITH TIME Help", "Select a category below to view commands.")
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
        
        view = HelpView(self.bot, mapping)
        
        embed = Embeds.default("🤖 Bot Help Menu", "Select a category below to view detailed commands.")
        embed.add_field(name="Stats", value=f"Servers: {len(self.bot.guilds)}\nLatency: {round(self.bot.latency * 1000)}ms")
        
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="commands", aliases=["cmds", "commandlist"], description="View a clean, professional list of all available bot commands.")
    async def commands_list(self, ctx):
        try:
            mapping = self.bot.help_command.get_bot_mapping()
        except AttributeError:
            mapping = {cog: cog.get_commands() for cog in self.bot.cogs.values()}
            mapping[None] = [c for c in self.bot.commands if c.cog is None]
            
        embed = discord.Embed(
            title="📋 Master Command List", 
            description="Here is a clean and categorized list of everything I can do. For more details, use `/help`.", 
            color=discord.Color.from_rgb(43, 45, 49) # Clean Discord dark theme color
        )
        
        # Premium emojis for known cogs
        emojis = {
            "Economy": "💰", "Market": "📈", "Community": "🤝", "Moderation": "🛡️", 
            "Polls": "📊", "Gambling": "🎰", "Store": "🛒", "Tickets": "🎫", 
            "Streamers": "📺", "Clans": "🛡️", "XP": "⭐", "Leveling": "📈",
            "Sportsbook": "🏀", "Games": "🎮", "Notifications": "🔔",
            "CustomCommands": "⚙️", "Blackjack": "🃏"
        }
        
        # Sort cogs alphabetically, pushing None to the end
        sorted_cogs = sorted([c for c in mapping.keys() if c], key=lambda c: c.qualified_name)
        
        for cog in sorted_cogs:
            commands_list = mapping[cog]
            if not commands_list: continue
            
            # Filter visible commands
            visible_cmds = [cmd for cmd in commands_list if not cmd.hidden]
            if not visible_cmds: continue
            
            cog_name = cog.qualified_name
            # Skip backend/admin cogs to keep it clean for normal users
            if cog_name in ["Help", "Jishaku", "Logging", "ServerBuilder", "Admin"]: continue 
            
            emoji = emojis.get(cog_name, "🔹")
            
            cmd_strings = []
            for cmd in visible_cmds:
                # If command has subcommands (like group), we can just list the main command for cleanliness
                if isinstance(cmd, commands.Group):
                    desc = cmd.description.split('\n')[0] if cmd.description else "Manage this feature."
                    cmd_strings.append(f"**/{cmd.name}** - *{desc}*")
                else:
                    desc = cmd.description.split('\n')[0] if cmd.description else "No description available."
                    if len(desc) > 55: desc = desc[:52] + "..."
                    cmd_strings.append(f"**/{cmd.name}** - *{desc}*")
            
            # Join and truncate if needed
            cmd_text = "\n".join(cmd_strings)
            if len(cmd_text) > 1024:
                cmd_text = cmd_text[:1020] + "..."
                
            embed.add_field(name=f"{emoji} {cog_name}", value=cmd_text, inline=False)
            
        embed.set_footer(text="Pro Tip: Use the drop-down in /help for interactive command navigation!")
        embed.timestamp = discord.utils.utcnow()
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
