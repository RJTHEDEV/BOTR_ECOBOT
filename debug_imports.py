import sys
import os

print("Current CWD:", os.getcwd())
print("Sys Path:", sys.path)

try:
    print("Importing utils.embeds...")
    from utils.embeds import Embeds
    print("Success: utils.embeds")
except Exception as e:
    print(f"Failed utils.embeds: {e}")

try:
    print("Importing cogs.help...")
    import cogs.help
    print("Success: cogs.help")
except Exception as e:
    print(f"Failed cogs.help: {e}")
