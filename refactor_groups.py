import re

def refactor(file_path, class_name, group_name):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find __init__ to inject group
    init_pattern = r'class ' + class_name + r'\(commands\.Cog\):\n    def __init__\(self, bot\):\n        self\.bot = bot[^\n]*\n'
    
    match = re.search(init_pattern, content)
    if match:
        injection = f'\n    @commands.hybrid_group(name="{group_name}", invoke_without_command=True)\n    async def {group_name}_group(self, ctx):\n        await ctx.send("Use `/{group_name} <action>`")\n\n'
        content = content[:match.end()] + injection + content[match.end():]

    # Replace all hybrid_command decorators
    pattern = r'@commands\.hybrid_command\([^)]*\)\n\s*(?:@commands\.[a-zA-Z_]+\([^)]*\)\n\s*)?async def ([a-zA-Z0-9_]+)'
    
    def replacer(m):
        cmd = m.group(1)
        original = m.group(0)
        return original.replace('@commands.hybrid_command', f'@{group_name}_group.command')

    content = re.sub(pattern, replacer, content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

refactor('cogs/gambling.py', 'Gambling', 'casino')
refactor('cogs/music.py', 'Music', 'music')
refactor('cogs/store.py', 'Store', 'store')
refactor('cogs/community.py', 'Community', 'community')
