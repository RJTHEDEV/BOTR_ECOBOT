import discord
from discord.ext import commands

class ServerBuilder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="build", description="Admin commands to help build the server faster.", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def build(self, ctx):
        embed = discord.Embed(
            title="🛠️ Server Builder Commands",
            description="Use these commands to quickly set up your server.",
            color=discord.Color.blue()
        )
        embed.add_field(name="/build role <name> [color]", value="Creates a new role with an optional hex color.", inline=False)
        embed.add_field(name="/build category <name>", value="Creates a new category.", inline=False)
        embed.add_field(name="/build textchannel <name> [category]", value="Creates a text channel in an optional category.", inline=False)
        embed.add_field(name="/build voicechannel <name> [category]", value="Creates a voice channel in an optional category.", inline=False)
        embed.add_field(name="/build multiroles <roles>", value="Creates multiple roles at once (comma separated).", inline=False)
        await ctx.send(embed=embed)

    @build.command(name="role", description="Creates a new role.")
    @commands.has_permissions(administrator=True)
    async def build_role(self, ctx, name: str, color: str = None):
        try:
            discord_color = discord.Color.default()
            if color:
                if color.startswith("#"):
                    color = color.strip("#")
                discord_color = discord.Color(int(color, 16))
            
            role = await ctx.guild.create_role(name=name, color=discord_color, reason=f"Created by {ctx.author} via builder command")
            await ctx.send(f"✅ Created role {role.mention} successfully.")
        except ValueError:
            await ctx.send("❌ Invalid color format. Please use a hex code (e.g., #FF0000 or FF0000).")
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to create roles.")
        except Exception as e:
            await ctx.send(f"❌ Error creating role: {e}")

    @build.command(name="multiroles", description="Creates multiple roles at once (comma-separated).")
    @commands.has_permissions(administrator=True)
    async def build_multiroles(self, ctx, *, roles: str):
        role_names = [r.strip() for r in roles.split(',') if r.strip()]
        if not role_names:
            await ctx.send("❌ Please provide at least one role name.")
            return

        created = []
        failed = 0
        await ctx.defer()
        
        for name in role_names:
            try:
                role = await ctx.guild.create_role(name=name, reason=f"Bulk created by {ctx.author}")
                created.append(role.name)
            except:
                failed += 1

        msg = f"✅ Successfully created {len(created)} roles: {', '.join(created)}"
        if failed > 0:
            msg += f"\n❌ Failed to create {failed} roles."
        await ctx.send(msg)

    @build.command(name="category", description="Creates a new category.")
    @commands.has_permissions(administrator=True)
    async def build_category(self, ctx, *, name: str):
        try:
            category = await ctx.guild.create_category(name=name, reason=f"Created by {ctx.author} via builder command")
            await ctx.send(f"✅ Created category **{category.name}** successfully.")
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to create categories.")
        except Exception as e:
            await ctx.send(f"❌ Error creating category: {e}")

    @build.command(name="textchannel", description="Creates a text channel in an optional category.")
    @commands.has_permissions(administrator=True)
    async def build_textchannel(self, ctx, name: str, category: discord.CategoryChannel = None):
        try:
            channel = await ctx.guild.create_text_channel(name=name, category=category, reason=f"Created by {ctx.author} via builder command")
            cat_text = f" in category **{category.name}**" if category else ""
            await ctx.send(f"✅ Created text channel {channel.mention}{cat_text} successfully.")
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to create channels.")
        except Exception as e:
            await ctx.send(f"❌ Error creating channel: {e}")

    @build.command(name="voicechannel", description="Creates a voice channel in an optional category.")
    @commands.has_permissions(administrator=True)
    async def build_voicechannel(self, ctx, name: str, category: discord.CategoryChannel = None):
        try:
            channel = await ctx.guild.create_voice_channel(name=name, category=category, reason=f"Created by {ctx.author} via builder command")
            cat_text = f" in category **{category.name}**" if category else ""
            await ctx.send(f"✅ Created voice channel **{channel.name}**{cat_text} successfully.")
        except discord.Forbidden:
            await ctx.send("❌ I do not have permission to create channels.")
        except Exception as e:
            await ctx.send(f"❌ Error creating channel: {e}")

    @build.command(name="multichannels", description="Creates multiple text channels at once (comma-separated) in an optional category.")
    @commands.has_permissions(administrator=True)
    async def build_multichannels(self, ctx, category: discord.CategoryChannel = None, *, channels: str = None):
        if not channels:
            # Maybe they didn't provide category, and put it all in category argument
            if type(category) is str:
                channels = category
                category = None
            else:
                await ctx.send("❌ Please provide channels.")
                return

        channel_names = [c.strip() for c in channels.split(',') if c.strip()]
        if not channel_names:
            await ctx.send("❌ Please provide at least one channel name.")
            return

        created = []
        failed = 0
        await ctx.defer()
        
        for name in channel_names:
            try:
                channel = await ctx.guild.create_text_channel(name=name, category=category, reason=f"Bulk created by {ctx.author}")
                created.append(channel.mention)
            except:
                failed += 1

        cat_text = f" in **{category.name}**" if category else ""
        msg = f"✅ Successfully created {len(created)} channels{cat_text}: {', '.join(created)}"
        if failed > 0:
            msg += f"\n❌ Failed to create {failed} channels."
        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(ServerBuilder(bot))
