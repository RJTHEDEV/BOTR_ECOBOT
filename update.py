with open('cogs/notifications.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add to WENT LIVE
content = content.replace(
    '# WENT LIVE',
    '# WENT LIVE\n                        await self._handle_live_role(guild_id, discord_user_id, add=True)'
)

# Add to WENT OFFLINE
# Wait, let's just do a regex replace for the WENT OFFLINE parts
import re

# Twitch offline
content = re.sub(
    r'(elif not is_live_now and db_is_live:\n\s+# WENT OFFLINE\n\s+await self\.bot\.db\.execute\("UPDATE twitch_alerts SET is_live = 0 WHERE id = \?", \(db_id,\)\)\n\s+await self\.bot\.db\.commit\(\))',
    r'\1\n                        await self._handle_live_role(guild_id, discord_user_id, add=False)',
    content
)

# Kick offline
content = re.sub(
    r'(elif not is_live_now and db_is_live:\n\s+await self\.bot\.db\.execute\("UPDATE kick_alerts SET is_live = 0 WHERE id = \?", \(db_id,\)\)\n\s+await self\.bot\.db\.commit\(\))',
    r'\1\n                        await self._handle_live_role(guild_id, discord_user_id, add=False)',
    content
)

# TikTok offline
content = re.sub(
    r'(elif not is_live_now and db_is_live:\n\s+await self\.bot\.db\.execute\("UPDATE tiktok_alerts SET is_live = 0 WHERE id = \?", \(db_id,\)\)\n\s+await self\.bot\.db\.commit\(\))',
    r'\1\n                        await self._handle_live_role(guild_id, discord_user_id, add=False)',
    content
)

with open('cogs/notifications.py', 'w', encoding='utf-8') as f:
    f.write(content)
