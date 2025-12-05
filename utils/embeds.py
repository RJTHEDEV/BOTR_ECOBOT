import discord
import datetime

class Embeds:
    @staticmethod
    def _base(title, description, color):
        embed = discord.Embed(title=title, description=description, color=color)
        embed.timestamp = datetime.datetime.now()
        return embed

    @staticmethod
    def success(title, description):
        return Embeds._base(f"✅ {title}", description, discord.Color.green())

    @staticmethod
    def error(title, description):
        return Embeds._base(f"❌ {title}", description, discord.Color.red())

    @staticmethod
    def info(title, description):
        return Embeds._base(f"ℹ️ {title}", description, discord.Color.blue())

    @staticmethod
    def warning(title, description):
        return Embeds._base(f"⚠️ {title}", description, discord.Color.gold())

    @staticmethod
    def default(title, description):
        return Embeds._base(title, description, discord.Color.blurple())
