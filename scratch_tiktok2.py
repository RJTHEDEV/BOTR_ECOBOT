import aiohttp
import asyncio
import json

async def main():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://www.tikwm.com/api/user/posts?unique_id=kamdatopic&count=1') as resp:
            text = await resp.text()
            print(text)

asyncio.run(main())
