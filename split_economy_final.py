import os

with open("cogs/economy.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

def get_lines(start, end):
    # 1-indexed to 0-indexed
    return lines[start-1:end]

header = get_lines(1, 6)
level_data = get_lines(7, 68)

init_economy = get_lines(70, 88)
log_trans = get_lines(90, 172)
add_xp = get_lines(174, 218)
economy_cmds_1 = get_lines(219, 360)
banking = get_lines(361, 423)
income = get_lines(424, 519)
rep = get_lines(520, 530)
profile = get_lines(532, 552)
leaderboard = get_lines(554, 581)
richest = get_lines(583, 611)
compare = get_lines(613, 654)
on_msg = get_lines(656, 681)
on_react = get_lines(683, 687)
on_voice = get_lines(689, 719)
crafting_block = get_lines(721, 765)
trade_block = get_lines(767, 795)
trade_view = get_lines(797, 853)

# Build economy.py
economy_content = []
economy_content.extend(header)
economy_content.extend(init_economy)
economy_content.extend(log_trans)
economy_content.extend(economy_cmds_1)
economy_content.extend(banking)
economy_content.extend(income)
economy_content.extend(rep)
economy_content.extend(richest)
economy_content.append("\nasync def setup(bot):\n")
economy_content.append("    await bot.add_cog(Economy(bot))\n")

with open("cogs/economy.py", "w", encoding="utf-8") as f:
    f.writelines(economy_content)

# Build xp.py
xp_content = []
xp_content.extend(header)
xp_content.extend(level_data)
xp_content.append("\nclass XP(commands.Cog):\n")
xp_content.append("    def __init__(self, bot):\n")
xp_content.append("        self.bot = bot\n")
xp_content.append("        self.voice_tracking = {}\n")
xp_content.append("        self.last_xp_time = {}\n\n")
xp_content.extend(add_xp)
xp_content.extend(profile)
xp_content.extend(leaderboard)
xp_content.extend(compare)
xp_content.extend(on_msg)
xp_content.extend(on_react)
xp_content.extend(on_voice)
xp_content.append("\nasync def setup(bot):\n")
xp_content.append("    await bot.add_cog(XP(bot))\n")

with open("cogs/xp.py", "w", encoding="utf-8") as f:
    f.writelines(xp_content)

# Build crafting.py
crafting_content = []
crafting_content.extend(header)
crafting_content.append("\nclass Crafting(commands.Cog):\n")
crafting_content.append("    def __init__(self, bot):\n")
crafting_content.append("        self.bot = bot\n\n")
crafting_content.extend(crafting_block)
crafting_content.extend(trade_block)
crafting_content.append("\n")
crafting_content.extend(trade_view)
crafting_content.append("\nasync def setup(bot):\n")
crafting_content.append("    await bot.add_cog(Crafting(bot))\n")

with open("cogs/crafting.py", "w", encoding="utf-8") as f:
    f.writelines(crafting_content)

print("Split successful!")
