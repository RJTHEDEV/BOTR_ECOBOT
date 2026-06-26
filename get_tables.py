import sqlite3
import os

db_path = 'data/bot.db'
if not os.path.exists(db_path):
    print("No db at", db_path)
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall()]
    print("Tables:", tables)
    
    if "twitch_alerts" in tables:
        cursor.execute("SELECT * FROM twitch_alerts;")
        print("Twitch alerts:", cursor.fetchall())
    if "live_roles" in tables:
        cursor.execute("SELECT * FROM live_roles;")
        print("Live roles:", cursor.fetchall())
    conn.close()
