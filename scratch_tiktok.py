import urllib.request
import json
import re

html = urllib.request.urlopen(urllib.request.Request('https://www.tiktok.com/@jojoborn772/live', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})).read().decode('utf-8')

m1 = re.search(r'<script id="SIGI_STATE".*?>(.*?)</script>', html)
m2 = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__".*?>(.*?)</script>', html)

if m1:
    print("SIGI_STATE found")
    data = json.loads(m1.group(1))
    
    live_room = data.get("LiveRoom", {}).get("liveRoomUserInfo", {})
    user = live_room.get("user", {})
    room = live_room.get("liveRoom", {})
    stats = live_room.get("stats", {})
    
    print("LiveRoom:")
    print("Title:", room.get("title"))
    print("CoverUrl:", room.get("coverUrl"))
    print("Avatar:", user.get("avatarThumb"))
    print("room userCount:", room.get("userCount"))



