import os

with open("cogs/economy.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

def extract_class_block(lines, cls_name):
    start = -1
    for i, l in enumerate(lines):
        if l.startswith(f"class {cls_name}"):
            start = i
            break
    if start == -1: return []
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("class ") or lines[i].startswith("async def setup"):
            end = i
            break
    return lines[start:end]

# It is easier to read economy.py, find the ranges of each function, and delete them from respective files.
# Let's just generate the clean files.
