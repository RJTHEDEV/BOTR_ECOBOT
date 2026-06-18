import discord
from discord.ext import commands
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageChops
import aiohttp

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def create_circular_mask(self, size):
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + size, fill=255)
        return mask

    async def generate_welcome_image(self, member):
        # Create a basic background
        width, height = 800, 300
        background = Image.new('RGB', (width, height), color=(44, 47, 51))
        
        # Add a banner line
        draw = ImageDraw.Draw(background)
        draw.rectangle([0, height-20, width, height], fill=(114, 137, 218))

        try:
            # Try to load a font, fallback to default
            font_title = ImageFont.truetype("arial.ttf", 48)
            font_sub = ImageFont.truetype("arial.ttf", 36)
        except IOError:
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()

        # Text
        title = "Welcome to the server!"
        sub = f"{member.display_name}"
        member_number = f"Member #{len(member.guild.members)}"
        
        draw.text((320, 80), title, font=font_title, fill=(255, 255, 255))
        draw.text((320, 150), sub, font=font_sub, fill=(114, 137, 218))
        draw.text((320, 200), member_number, font=font_sub, fill=(153, 170, 181))

        # Avatar
        if member.display_avatar:
            avatar_url = member.display_avatar.with_format("png").with_size(128).url
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status == 200:
                        avatar_data = await resp.read()
                        avatar_img = Image.open(BytesIO(avatar_data)).convert("RGBA")
                        avatar_img = avatar_img.resize((180, 180))
                        
                        # Apply circular mask
                        mask = self.create_circular_mask(avatar_img.size)
                        avatar_img.putalpha(mask)
                        
                        # Paste avatar onto background
                        background.paste(avatar_img, (80, 60), avatar_img)

        # Save to BytesIO
        buffer = BytesIO()
        background.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Find system channel or log channel
        channel = member.guild.system_channel
        if not channel:
            # Fallback: find any channel named 'welcome' or 'general'
            for c in member.guild.text_channels:
                if "welcome" in c.name.lower() or "general" in c.name.lower():
                    channel = c
                    break
                    
        if channel:
            try:
                buffer = await self.generate_welcome_image(member)
                file = discord.File(fp=buffer, filename="welcome.png")
                await channel.send(content=f"Welcome {member.mention}!", file=file)
            except Exception as e:
                print(f"Error generating welcome image: {e}")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
