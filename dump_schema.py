import sqlite3
import json

db_path = 'data/bot.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cursor.fetchall()]

schema = {}
for t in tables:
    cursor.execute(f"PRAGMA table_info({t});")
    schema[t] = [r[1] for r in cursor.fetchall()]

with open('schema.json', 'w') as f:
    json.dump(schema, f, indent=4)
print(f"Dumped schema of {len(tables)} tables")
