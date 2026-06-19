import re
with open('cogs/moderation.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('class Moderation(commands.Cog):\n    def __init__(self, bot):\n        self.bot = bot\n        self.sniped_messages = {}\n', 'class Moderation(commands.Cog):\n    def __init__(self, bot):\n        self.bot = bot\n        self.sniped_messages = {}\n\n    @commands.hybrid_group(name="mod", invoke_without_command=True)\n    async def mod(self, ctx):\n        await ctx.send("Use `/mod <action>`")\n')

# Find all @commands.hybrid_command and replace with @mod.command except for say, history, snipe
for cmd in ['kick', 'ban', 'mute', 'unmute', 'warn', 'purge', 'slowmode', 'softban', 'unban', 'nick', 'lockdown', 'unlock', 'history']:
    pattern = r'@commands\.hybrid_command\([^)]*\)\n\s*(?:@commands\.[a-zA-Z_]+\([^)]*\)\n\s*)?async def ' + cmd
    def replacer(match):
        return match.group(0).replace('@commands.hybrid_command', '@mod.command')
    content = re.sub(pattern, replacer, content)

with open('cogs/moderation.py', 'w', encoding='utf-8') as f:
    f.write(content)
