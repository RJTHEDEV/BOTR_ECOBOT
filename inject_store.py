import re

with open('cogs/store.py', 'r', encoding='utf-8') as f:
    content = f.read()

with open('scratch_store.py', 'r', encoding='utf-8') as f:
    replacement = f.read()

# Replace everything from "class ItemBuySelect" down to "async def setup"
pattern = re.compile(r"class ItemBuySelect\(.*?async def setup", re.DOTALL)
content = pattern.sub(replacement + "\nasync def setup", content)

with open('cogs/store.py', 'w', encoding='utf-8') as f:
    f.write(content)
