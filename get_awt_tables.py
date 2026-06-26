import sqlite3
import os

db_path = r'Z:\AWT\data\bot.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print([r[0] for r in cursor.fetchall()])
    
    cursor.execute("SELECT * FROM twitch_alerts;")
    print("Twitch alerts:", cursor.fetchall())
    conn.close()
else:
    print("No DB at AWT")
