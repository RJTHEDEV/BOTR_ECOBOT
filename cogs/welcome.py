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

    def create_gradient(self, width, height, color1, color2):
        base = Image.new('RGBA', (width, height), color1)
        top = Image.new('RGBA', (width, height), color2)
        mask = Image.new('L', (width, height))
        mask_data = []
        for y in range(height):
            for x in range(width):
                val = int(255 * ((x / width + y / height) / 2))
                mask_data.append(val)
        mask.putdata(mask_data)
        base.paste(top, (0, 0), mask)
        return base

    async def generate_welcome_image(self, member):
        width, height = 850, 300
        
        # 1. Premium Gradient Background (Dark Space to Deep Blue/Purple)
        color1 = (15, 20, 30, 255)
        color2 = (35, 25, 50, 255)
        background = self.create_gradient(width, height, color1, color2)
        
        # Add some subtle background shapes/lines
        draw = ImageDraw.Draw(background, "RGBA")
        draw.line([(0, 280), (200, 250), (400, 290), (600, 220), (850, 260)], fill=(255, 255, 255, 10), width=3)
        draw.line([(0, 300), (200, 270), (400, 310), (600, 240), (850, 280)], fill=(114, 137, 218, 20), width=6)

        # 2. Add an accent banner / border at the bottom and top
        draw.rectangle([0, height-6, width, height], fill=(114, 137, 218, 255))
        draw.rectangle([0, 0, width, 4], fill=(114, 137, 218, 150))

        # 3. Transparent Overlay Box for the Text to increase readability
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        # We use a rounded_rectangle if available in this PIL version, else normal rectangle
        try:
            overlay_draw.rounded_rectangle([320, 45, 810, 255], radius=15, fill=(0, 0, 0, 100))
        except AttributeError:
            overlay_draw.rectangle([320, 45, 810, 255], fill=(0, 0, 0, 100))
            
        background = Image.alpha_composite(background, overlay)
        draw = ImageDraw.Draw(background, "RGBA")

        import os
        try:
            if os.path.exists("C:\\Windows\\Fonts\\segoeuib.ttf"):
                font_title = ImageFont.truetype("C:\\Windows\\Fonts\\segoeuib.ttf", 46)
                font_name = ImageFont.truetype("C:\\Windows\\Fonts\\segoeuib.ttf", 52)
                font_sub = ImageFont.truetype("C:\\Windows\\Fonts\\segoeui.ttf", 30)
            elif os.path.exists("C:\\Windows\\Fonts\\arialbd.ttf"):
                font_title = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 46)
                font_name = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 52)
                font_sub = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 30)
            else:
                font_title = ImageFont.truetype("arial.ttf", 46)
                font_name = ImageFont.truetype("arial.ttf", 52)
                font_sub = ImageFont.truetype("arial.ttf", 30)
        except Exception:
            font_title = ImageFont.load_default()
            font_name = ImageFont.load_default()
            font_sub = ImageFont.load_default()

        def draw_text(pos, text, font, fill):
            # Drop Shadow
            draw.text((pos[0]+3, pos[1]+3), text, font=font, fill=(0, 0, 0, 200))
            # Main Text
            draw.text(pos, text, font=font, fill=fill)

        # Texts
        title = "WELCOME TO AWT!"
        name = member.display_name
        if len(name) > 16: name = name[:14] + "..."
        member_number = f"Member #{len(member.guild.members)}"
        
        draw_text((350, 65), title, font=font_title, fill=(114, 137, 218, 255))
        draw_text((350, 125), name.upper(), font=font_name, fill=(255, 255, 255, 255))
        draw_text((350, 195), member_number, font=font_sub, fill=(180, 190, 200, 255))

        # 4. Avatar setup with premium glowing/border ring
        avatar_size = 180
        avatar_pos = (80, 60)
        
        if member.display_avatar:
            avatar_url = member.display_avatar.with_format("png").with_size(256).url
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status == 200:
                        avatar_data = await resp.read()
                        avatar_img = Image.open(BytesIO(avatar_data)).convert("RGBA")
                        avatar_img = avatar_img.resize((avatar_size, avatar_size))
                        
                        mask = self.create_circular_mask(avatar_img.size)
                        avatar_img.putalpha(mask)
                        
                        ring_thickness = 8
                        ring_size = avatar_size + (ring_thickness * 2)
                        ring_bg = Image.new("RGBA", (ring_size, ring_size), (0,0,0,0))
                        ring_draw = ImageDraw.Draw(ring_bg)
                        
                        # Drop shadow under ring
                        ring_draw.ellipse((4, 4, ring_size-1, ring_size-1), fill=(0,0,0,180))
                        # The colored ring
                        ring_draw.ellipse((0, 0, ring_size-1-4, ring_size-1-4), fill=(114, 137, 218, 255))
                        # Inner dark ring for depth
                        inner_offset = ring_thickness - 2
                        ring_draw.ellipse((inner_offset, inner_offset, ring_size-inner_offset-1-4, ring_size-inner_offset-1-4), fill=(30, 30, 40, 255))

                        ring_bg.paste(avatar_img, (ring_thickness, ring_thickness), avatar_img)
                        background.paste(ring_bg, (avatar_pos[0]-ring_thickness, avatar_pos[1]-ring_thickness), ring_bg)

        final_image = background.convert("RGB")
        buffer = BytesIO()
        final_image.save(buffer, format="PNG")
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
