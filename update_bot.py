with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'is_live INTEGER DEFAULT 0,\n                    custom_message TEXT',
    'is_live INTEGER DEFAULT 0,\n                    discord_user_id INTEGER,\n                    custom_message TEXT'
)

content = content.replace(
    'last_video_id TEXT,\n                    custom_message TEXT',
    'last_video_id TEXT,\n                    discord_user_id INTEGER,\n                    custom_message TEXT'
)

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)
