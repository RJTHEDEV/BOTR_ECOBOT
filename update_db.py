import sqlite3

def patch_db():
    try:
        conn = sqlite3.connect('data/bot.db')
        tables = ['kick_alerts', 'tiktok_alerts', 'youtube_alerts', 'twitch_alerts']
        for table in tables:
            try:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN discord_user_id INTEGER;')
                print(f"Added discord_user_id to {table}")
            except Exception as e:
                pass
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB Patch Error:", e)

