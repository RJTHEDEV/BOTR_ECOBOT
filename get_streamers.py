import sqlite3

conn = sqlite3.connect('data/bot.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(streamers);")
print(cursor.fetchall())
conn.close()
