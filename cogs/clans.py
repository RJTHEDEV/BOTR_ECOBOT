import discord
from discord.ext import commands

class Clans(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CLAN_CREATION_COST = 10000

    @commands.hybrid_group(invoke_without_command=True, description="Manage your Clan.")
    async def clan(self, ctx):
        await ctx.send("Use `/clan create`, `/clan info`, `/clan invite`, `/clan join`, `/clan deposit`.")

    @clan.command(name="create", description="Create a new Clan (Cost: $10,000)")
    async def create_clan(self, ctx, *, name: str):
        # Check if already in a clan
        async with self.bot.db.execute("SELECT clan_id FROM clan_members WHERE user_id = ?", (ctx.author.id,)) as cursor:
            if await cursor.fetchone():
                await ctx.send("You are already in a clan. Leave it first.")
                return

        # Check funds
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < self.CLAN_CREATION_COST:
                await ctx.send(f"You need **${self.CLAN_CREATION_COST}** to create a clan.")
                return

        # Create Clan
        try:
            # Deduct funds
            await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (self.CLAN_CREATION_COST, ctx.author.id))
            
            # Insert Clan
            await self.bot.db.execute("INSERT INTO clans (name, owner_id) VALUES (?, ?)", (name, ctx.author.id))
            
            # Get Clan ID
            async with self.bot.db.execute("SELECT id FROM clans WHERE name = ?", (name,)) as cursor:
                clan_id = (await cursor.fetchone())[0]
                
            # Add owner to members
            await self.bot.db.execute("INSERT INTO clan_members (user_id, clan_id) VALUES (?, ?)", (ctx.author.id, clan_id))
            await self.bot.db.commit()
            
            await ctx.send(f"🛡️ Successfully created the clan **{name}**!")
        except Exception as e:
            await ctx.send(f"Failed to create clan. Name might be taken. ({e})")

    @clan.command(name="info", description="View info about a clan.")
    async def info(self, ctx, *, name: str = None):
        if not name:
            # View own clan
            async with self.bot.db.execute("SELECT clan_id FROM clan_members WHERE user_id = ?", (ctx.author.id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    await ctx.send("You are not in a clan. Specify a name to view another clan.")
                    return
                clan_id = row[0]
            async with self.bot.db.execute("SELECT name, owner_id, bank, level FROM clans WHERE id = ?", (clan_id,)) as cursor:
                clan_info = await cursor.fetchone()
        else:
            async with self.bot.db.execute("SELECT name, owner_id, bank, level, id FROM clans WHERE name = ?", (name,)) as cursor:
                clan_info = await cursor.fetchone()
                if not clan_info:
                    await ctx.send("Clan not found.")
                    return
                clan_id = clan_info[4]

        c_name, c_owner, c_bank, c_level = clan_info[:4]
        
        async with self.bot.db.execute("SELECT user_id FROM clan_members WHERE clan_id = ?", (clan_id,)) as cursor:
            members = await cursor.fetchall()
            
        owner = self.bot.get_user(c_owner)
        owner_name = owner.display_name if owner else f"User {c_owner}"
        
        embed = discord.Embed(title=f"🛡️ Clan: {c_name}", color=discord.Color.gold())
        embed.add_field(name="Owner", value=owner_name, inline=True)
        embed.add_field(name="Level", value=str(c_level), inline=True)
        embed.add_field(name="Clan Bank", value=f"${c_bank}", inline=True)
        embed.add_field(name="Members", value=f"{len(members)}", inline=True)
        await ctx.send(embed=embed)

    @clan.command(name="invite", description="Invite a user to your clan (Owner only).")
    async def invite(self, ctx, target: discord.Member):
        async with self.bot.db.execute("SELECT id, name FROM clans WHERE owner_id = ?", (ctx.author.id,)) as cursor:
            clan = await cursor.fetchone()
            if not clan:
                await ctx.send("You must be the owner of a clan to invite people.")
                return
                
        clan_id, clan_name = clan
        
        async with self.bot.db.execute("SELECT clan_id FROM clan_members WHERE user_id = ?", (target.id,)) as cursor:
            if await cursor.fetchone():
                await ctx.send("That user is already in a clan.")
                return

        # Simple invite (no persistent invites, just force join for now or use buttons)
        # For a robust system, we use a button view
        view = discord.ui.View()
        
        async def accept_callback(interaction):
            if interaction.user != target: return
            await self.bot.db.execute("INSERT INTO clan_members (user_id, clan_id) VALUES (?, ?)", (target.id, clan_id))
            await self.bot.db.commit()
            await interaction.response.edit_message(content=f"✅ {target.mention} joined the clan **{clan_name}**!", view=None)
            
        async def decline_callback(interaction):
            if interaction.user != target: return
            await interaction.response.edit_message(content=f"❌ {target.mention} declined the clan invite.", view=None)

        btn_yes = discord.ui.Button(label="Accept", style=discord.ButtonStyle.green)
        btn_no = discord.ui.Button(label="Decline", style=discord.ButtonStyle.red)
        btn_yes.callback = accept_callback
        btn_no.callback = decline_callback
        view.add_item(btn_yes)
        view.add_item(btn_no)
        
        await ctx.send(content=f"{target.mention}, you have been invited to join the clan **{clan_name}** by {ctx.author.mention}!", view=view)

    @clan.command(name="leave", description="Leave your current clan.")
    async def leave(self, ctx):
        async with self.bot.db.execute("SELECT clan_id FROM clan_members WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await ctx.send("You are not in a clan.")
                return
            clan_id = row[0]
            
        # Check if owner
        async with self.bot.db.execute("SELECT owner_id FROM clans WHERE id = ?", (clan_id,)) as cursor:
            owner_id = (await cursor.fetchone())[0]
            if owner_id == ctx.author.id:
                await ctx.send("You are the owner. You must transfer ownership or disband the clan (disband feature coming soon).")
                return

        await self.bot.db.execute("DELETE FROM clan_members WHERE user_id = ?", (ctx.author.id,))
        await self.bot.db.commit()
        await ctx.send("✅ You have left the clan.")

async def setup(bot):
    await bot.add_cog(Clans(bot))
