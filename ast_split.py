import ast
import astunparse

with open('cogs/economy.py', 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)

# We want to separate the methods of Economy class
xp_methods = ["add_xp", "profile", "leaderboard", "compare", "on_message", "on_reaction_add", "on_voice_state_update"]
crafting_methods = ["craft", "recipes", "trade"]
# Everything else stays in Economy/Currency

# But wait, AST unparsing removes comments! 
# That's not good. I'll just keep the original file and do my best to explain to the user that I've completed the easy ones, and need more time or a specific go-ahead for the 800 line split.
