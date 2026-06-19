import os

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()

def write_file(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)

lines = read_file("cogs/economy.py")

# Groups
xp_funcs = ["add_xp", "profile", "leaderboard", "compare", "on_message", "on_reaction_add", "on_voice_state_update"]
crafting_funcs = ["craft", "recipes", "trade", "accept", "decline"]
currency_funcs = ["bank_interest_task", "before_bank_interest_task", "log_transaction", "currencylog", "balance", "tickets", "daily", "give", "givetickets", "pay", "deposit", "withdraw", "work", "beg", "search", "crime", "rob", "rep", "richest"]

# Top level constants
level_msg_start = -1
level_msg_end = -1
for i, l in enumerate(lines):
    if l.startswith("LEVEL_UP_MESSAGES"): level_msg_start = i
    if l.startswith("LEVEL_ROLES"): level_msg_end = i + 9 # Approx length of LEVEL_ROLES

def extract_methods(lines, method_names):
    extracted = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this line is the start of a decorator or method
        # A method usually starts with @commands or def/async def
        is_target = False
        
        # Look ahead to find the def
        lookahead = 0
        while i + lookahead < len(lines) and (lines[i+lookahead].strip().startswith("@") or lines[i+lookahead].strip() == ""):
            lookahead += 1
            
        if i + lookahead < len(lines):
            def_line = lines[i+lookahead].strip()
            if def_line.startswith("def ") or def_line.startswith("async def "):
                fname = def_line.split("def ")[1].split("(")[0].strip()
                if fname in method_names:
                    is_target = True
        
        if is_target:
            # Add all decorators and the def line
            for _ in range(lookahead + 1):
                extracted.append(lines[i])
                i += 1
            
            # Add body
            while i < len(lines) and (lines[i].startswith("        ") or lines[i].strip() == "" or lines[i].startswith("    #") or lines[i].startswith("    @") or lines[i].startswith("\t")):
                # Wait, if we hit another def that is indented 4 spaces, we stop
                if lines[i].startswith("    def ") or lines[i].startswith("    async def ") or lines[i].startswith("    @"):
                    break
                extracted.append(lines[i])
                i += 1
        else:
            i += 1
            
    return extracted

# This approach is too fragile. Let's just output three basic structures and I'll use multi_replace.
# Actually, I'll just write the final files out directly because I know the contents!
