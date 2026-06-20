import discord
from discord.ext import commands

CATEGORIES = {
    "Economy & Progression": {
        "description": "Manage wealth, jobs, shop, clans, and XP.",
        "emoji": "💰",
        "cogs": ["Economy", "Store", "Quests", "Clans", "XP", "Leveling"]
    },
    "Trading & Markets": {
        "description": "Real-time stock/crypto prices, paper trading.",
        "emoji": "📈",
        "cogs": ["Market", "PaperTrading", "Options", "Crypto", "Alerts"]
    },
    "Games & Gambling": {
        "description": "Test your luck with games and sports betting.",
        "emoji": "🎰",
        "cogs": ["Gambling", "Games", "Sportsbook", "Blackjack"]
    },
    "Community & Social": {
        "description": "Social features, streamers, polls, and tickets.",
        "emoji": "🤝",
        "cogs": ["Community", "Streamers", "Polls", "Tickets"]
    },
    "Moderation & Utility": {
        "description": "Admin tools, logging, and server utilities.",
        "emoji": "🛡️",
        "cogs": ["Moderation", "Utility", "Voice", "Logging"]
    },
    "Bot & Settings": {
        "description": "Custom commands, external feeds, and more.",
        "emoji": "⚙️",
        "cogs": ["CustomCommands", "External", "Notifications"]
    }
}

class HelpSelect(discord.ui.Select):
    def __init__(self, bot, mapping):
        self.bot = bot
        self.mapping = mapping
        
        options = [
            discord.SelectOption(label="Home", description="Back to the main menu", emoji="🏠", value="home")
        ]
        
        for cat_name, data in CATEGORIES.items():
            options.append(discord.SelectOption(
                label=cat_name,
                description=data["description"],
                emoji=data["emoji"],
                value=cat_name
            ))
            
        # Add an option for "Other" in case we missed a cog
        options.append(discord.SelectOption(
            label="Other Commands",
            description="Miscellaneous commands not categorized.",
            emoji="🔹",
            value="Other"
        ))

        super().__init__(placeholder="Select a command category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        
        if value == "home":
            embed = discord.Embed(
                title="🤖 Bot Help Center",
                description="Welcome to the main help menu! Please use the dropdown below to explore the bot's features organized by topic.",
                color=discord.Color.from_rgb(43, 45, 49)
            )
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.add_field(name="Navigation", value="Select a category from the dropdown menu to see all associated commands.", inline=False)
            embed.add_field(name="Master Directory", value="You can also use `/commands` to generate a master list of all commands.", inline=False)
            embed.add_field(name="Bot Stats", value=f"Servers: {len(self.bot.guilds)}\nLatency: {round(self.bot.latency * 1000)}ms", inline=False)
            await interaction.response.edit_message(embed=embed)
            return

        embed = discord.Embed(
            title=f"{value} Commands",
            color=discord.Color.from_rgb(43, 45, 49)
        )
        
        if value == "Other":
            # find all cogs not in CATEGORIES
            known_cogs = [c for cat in CATEGORIES.values() for c in cat["cogs"]]
            cogs_to_show = [cog for cog in self.mapping.keys() if cog and getattr(cog, "qualified_name", "Z") not in known_cogs and getattr(cog, "qualified_name", "Z") not in ["Help", "Jishaku", "ServerBuilder", "Admin", "Logging"]]
        else:
            cat_cogs = CATEGORIES[value]["cogs"]
            cogs_to_show = [cog for cog in self.mapping.keys() if cog and getattr(cog, "qualified_name", "Z") in cat_cogs]

        # Sort the cogs alphabetically for display
        cogs_to_show = sorted(cogs_to_show, key=lambda c: getattr(c, "qualified_name", "Z"))

        if not cogs_to_show:
            embed.description = "*No commands found in this category.*"
        else:
            for cog in cogs_to_show:
                commands_list = self.mapping[cog]
                visible_cmds = [cmd for cmd in commands_list if not cmd.hidden]
                if not visible_cmds: continue
                
                cmd_strings = []
                for cmd in visible_cmds:
                    if isinstance(cmd, commands.Group):
                        desc = cmd.description.split('\n')[0] if cmd.description else "Manage this feature."
                        cmd_strings.append(f"**/{cmd.name}** - *{desc}*")
                    else:
                        desc = cmd.description.split('\n')[0] if cmd.description else "No description available."
                        if len(desc) > 60: desc = desc[:57] + "..."
                        cmd_strings.append(f"**/{cmd.name}** - *{desc}*")
                
                cmd_text = "\n".join(cmd_strings)
                if len(cmd_text) > 1024: cmd_text = cmd_text[:1020] + "..."
                embed.add_field(name=f"✧ {getattr(cog, 'qualified_name', 'Unknown')}", value=cmd_text, inline=False)

        await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    def __init__(self, bot, mapping):
        super().__init__(timeout=180)
        self.add_item(HelpSelect(bot, mapping))

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="Interactive, categorized help menu.")
    async def help(self, ctx):
        try:
            mapping = self.bot.help_command.get_bot_mapping()
        except AttributeError:
            mapping = {cog: cog.get_commands() for cog in self.bot.cogs.values()}
            mapping[None] = [c for c in self.bot.commands if c.cog is None]
        
        view = HelpView(self.bot, mapping)
        
        embed = discord.Embed(
            title="🤖 Bot Help Center",
            description="Welcome to the main help menu! Please use the dropdown below to explore the bot's features organized by topic.",
            color=discord.Color.from_rgb(43, 45, 49)
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="Navigation", value="Select a category from the dropdown menu to see all associated commands.", inline=False)
        embed.add_field(name="Master Directory", value="You can also use `/commands` to generate a master list of all commands.", inline=False)
        embed.add_field(name="Bot Stats", value=f"Servers: {len(self.bot.guilds)}\nLatency: {round(self.bot.latency * 1000)}ms", inline=False)
        
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="commands", aliases=["cmds", "commandlist"], description="View a clean, professional list of all available bot commands.")
    async def commands_list(self, ctx):
        try:
            mapping = self.bot.help_command.get_bot_mapping()
        except AttributeError:
            mapping = {cog: cog.get_commands() for cog in self.bot.cogs.values()}
            mapping[None] = [c for c in self.bot.commands if c.cog is None]
            
        embeds = []
        current_embed = discord.Embed(
            title="📋 Master Command List", 
            description="Here is a clean and categorized list of everything I can do. For more details, use `/help`.", 
            color=discord.Color.from_rgb(43, 45, 49)
        )
        
        emojis = {
            "Economy": "💰", "Market": "📈", "Community": "🤝", "Moderation": "🛡️", 
            "Polls": "📊", "Gambling": "🎰", "Store": "🛒", "Tickets": "🎫", 
            "Streamers": "📺", "Clans": "🛡️", "XP": "⭐", "Leveling": "📈",
            "Sportsbook": "🏀", "Games": "🎮", "Notifications": "🔔",
            "CustomCommands": "⚙️", "Blackjack": "🃏"
        }
        
        sorted_cogs = sorted([c for c in mapping.keys() if c], key=lambda c: getattr(c, "qualified_name", "Z"))
        
        field_count = 0
        
        for cog in sorted_cogs:
            commands_list = mapping[cog]
            if not commands_list: continue
            
            visible_cmds = [cmd for cmd in commands_list if not cmd.hidden]
            if not visible_cmds: continue
            
            cog_name = getattr(cog, "qualified_name", "Other")
            if cog_name in ["Help", "Jishaku", "Logging", "ServerBuilder", "Admin"]: continue 
            
            emoji = emojis.get(cog_name, "🔹")
            
            cmd_strings = []
            for cmd in visible_cmds:
                if isinstance(cmd, commands.Group):
                    desc = cmd.description.split('\n')[0] if cmd.description else "Manage this feature."
                    cmd_strings.append(f"**/{cmd.name}** - *{desc}*")
                else:
                    desc = cmd.description.split('\n')[0] if cmd.description else "No description available."
                    if len(desc) > 55: desc = desc[:52] + "..."
                    cmd_strings.append(f"**/{cmd.name}** - *{desc}*")
            
            cmd_text = "\n".join(cmd_strings)
            if len(cmd_text) > 1024:
                cmd_text = cmd_text[:1020] + "..."
                
            if field_count >= 25:
                embeds.append(current_embed)
                current_embed = discord.Embed(color=discord.Color.from_rgb(43, 45, 49))
                field_count = 0
                
            current_embed.add_field(name=f"{emoji} {cog_name}", value=cmd_text, inline=False)
            field_count += 1
            
        current_embed.set_footer(text="Pro Tip: Use the drop-down in /help for interactive command navigation!")
        current_embed.timestamp = discord.utils.utcnow()
        embeds.append(current_embed)
        
        await ctx.send(embeds=embeds[:10])

async def setup(bot):
    await bot.add_cog(Help(bot))
