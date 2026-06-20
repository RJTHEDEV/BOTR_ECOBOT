import discord
from discord.ext import commands

CLAN_SHOP = {
    "xp_booster": {"name": "XP Booster", "cost": 50000, "req_level": 2, "desc": "Gives +10% XP to all members", "db_col": "xp_buff"},
    "coin_booster": {"name": "Coin Booster", "cost": 100000, "req_level": 3, "desc": "Gives +10% Coins to all members", "db_col": "coin_buff"},
}

class Clans(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CLAN_CREATION_COST = 10000

    @commands.hybrid_group(invoke_without_command=True, description="Manage your Clan.")
    async def clan(self, ctx):
        await ctx.send("Use `/clan create`, `/clan info`, `/clan invite`, `/clan join`, `/clan deposit`, `/clan shop`, `/clan buy`, `/clan levelup`.")

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
            # Handle old databases without xp_buff
            try:
                async with self.bot.db.execute("SELECT name, owner_id, bank, level, xp_buff, coin_buff FROM clans WHERE id = ?", (clan_id,)) as cursor:
                    clan_info = await cursor.fetchone()
            except:
                async with self.bot.db.execute("SELECT name, owner_id, bank, level FROM clans WHERE id = ?", (clan_id,)) as cursor:
                    temp = await cursor.fetchone()
                    if temp: clan_info = (*temp, 0, 0)
                    else: clan_info = None
        else:
            try:
                async with self.bot.db.execute("SELECT name, owner_id, bank, level, xp_buff, coin_buff, id FROM clans WHERE name = ?", (name,)) as cursor:
                    clan_info = await cursor.fetchone()
                    if clan_info: clan_id = clan_info[6]
            except:
                async with self.bot.db.execute("SELECT name, owner_id, bank, level, id FROM clans WHERE name = ?", (name,)) as cursor:
                    temp = await cursor.fetchone()
                    if temp: 
                        clan_info = (*temp[:4], 0, 0, temp[4])
                        clan_id = temp[4]
                    else: clan_info = None

        if not clan_info:
            await ctx.send("Clan not found.")
            return

        c_name, c_owner, c_bank, c_level, c_xp_buff, c_coin_buff = clan_info[:6]
        
        async with self.bot.db.execute("SELECT user_id FROM clan_members WHERE clan_id = ?", (clan_id,)) as cursor:
            members = await cursor.fetchall()
            
        owner = self.bot.get_user(c_owner)
        owner_name = owner.display_name if owner else f"User {c_owner}"
        
        embed = discord.Embed(title=f"🛡️ Clan: {c_name}", color=discord.Color.gold())
        embed.add_field(name="Owner", value=owner_name, inline=True)
        embed.add_field(name="Level", value=str(c_level), inline=True)
        embed.add_field(name="Clan Bank", value=f"${c_bank:,}", inline=True)
        embed.add_field(name="Members", value=f"{len(members)}", inline=True)
        
        buffs_text = []
        if c_xp_buff > 0: buffs_text.append("✨ +10% XP Boost")
        if c_coin_buff > 0: buffs_text.append("💰 +10% Coin Boost")
        
        if buffs_text:
            embed.add_field(name="Active Buffs", value="\n".join(buffs_text), inline=False)
        else:
            embed.add_field(name="Active Buffs", value="None (Check `/clan shop`!)", inline=False)
            
        await ctx.send(embed=embed)

    @clan.command(name="deposit", description="Deposit money into the clan bank.")
    async def deposit(self, ctx, amount: int):
        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        async with self.bot.db.execute("SELECT clan_id FROM clan_members WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await ctx.send("You are not in a clan.")
                return
            clan_id = row[0]

        # Check user balance
        async with self.bot.db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < amount:
                await ctx.send("You don't have enough money.")
                return

        # Deduct from user and add to clan bank
        await self.bot.db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, ctx.author.id))
        await self.bot.db.execute("UPDATE clans SET bank = bank + ? WHERE id = ?", (amount, clan_id))
        await self.bot.db.commit()

        await ctx.send(f"✅ Successfully deposited **${amount:,}** into the clan bank.")

    @clan.command(name="shop", description="View items and buffs you can buy for the clan.")
    async def shop(self, ctx):
        embed = discord.Embed(title="🛒 Clan Shop", description="Use clan funds to upgrade your clan and gain buffs!\nUse `/clan buy <item_id>`.", color=discord.Color.blue())
        
        for item_id, item in CLAN_SHOP.items():
            embed.add_field(
                name=f"{item['name']} (`{item_id}`)", 
                value=f"**Cost:** ${item['cost']:,}\n**Req. Level:** {item['req_level']}\n*{item['desc']}*", 
                inline=False
            )
            
        embed.set_footer(text="Clan owner can purchase these using the clan bank.")
        await ctx.send(embed=embed)

    @clan.command(name="levelup", description="Level up your clan using the clan bank.")
    async def levelup(self, ctx):
        async with self.bot.db.execute("SELECT id, name, owner_id, bank, level FROM clans WHERE owner_id = ?", (ctx.author.id,)) as cursor:
            clan = await cursor.fetchone()
            if not clan:
                await ctx.send("You must be the owner of a clan to level it up.")
                return
                
        clan_id, clan_name, owner_id, bank, level = clan
        cost = level * 50000
        
        if bank < cost:
            await ctx.send(f"❌ Your clan bank only has **${bank:,}**. You need **${cost:,}** to reach Level {level + 1}.")
            return
            
        # Deduct from bank and level up
        await self.bot.db.execute("UPDATE clans SET bank = bank - ?, level = level + 1 WHERE id = ?", (cost, clan_id))
        await self.bot.db.commit()
        
        await ctx.send(f"🎉 **{clan_name}** has leveled up to **Level {level + 1}**! (Cost: ${cost:,})")

    @clan.command(name="buy", description="Buy an item or buff for the clan.")
    async def buy(self, ctx, item_id: str):
        item_id = item_id.lower()
        if item_id not in CLAN_SHOP:
            await ctx.send("Invalid item. Use `/clan shop` to see available items.")
            return
            
        item = CLAN_SHOP[item_id]
        
        # Handle old databases without xp_buff
        try:
            async with self.bot.db.execute("SELECT id, name, owner_id, bank, level, xp_buff, coin_buff FROM clans WHERE owner_id = ?", (ctx.author.id,)) as cursor:
                clan = await cursor.fetchone()
        except:
            async with self.bot.db.execute("SELECT id, name, owner_id, bank, level FROM clans WHERE owner_id = ?", (ctx.author.id,)) as cursor:
                temp = await cursor.fetchone()
                if temp: clan = (*temp, 0, 0)
                else: clan = None
                
        if not clan:
            await ctx.send("You must be the owner of a clan to buy upgrades.")
            return
            
        clan_id, clan_name, owner_id, bank, level, xp_buff, coin_buff = clan[:7]
        
        if level < item['req_level']:
            await ctx.send(f"❌ Your clan must be at least **Level {item['req_level']}** to buy this.")
            return
            
        if bank < item['cost']:
            await ctx.send(f"❌ Your clan bank only has **${bank:,}**. You need **${item['cost']:,}** for {item['name']}.")
            return
            
        # Check if already owned
        is_owned = False
        if item['db_col'] == 'xp_buff' and xp_buff > 0: is_owned = True
        elif item['db_col'] == 'coin_buff' and coin_buff > 0: is_owned = True
        
        if is_owned:
            await ctx.send(f"❌ Your clan already has the {item['name']} active!")
            return
            
        # Purchase
        try:
            await self.bot.db.execute(f"UPDATE clans SET bank = bank - ?, {item['db_col']} = 1 WHERE id = ?", (item['cost'], clan_id))
            await self.bot.db.commit()
            await ctx.send(f"🎊 Successfully purchased **{item['name']}** for **{clan_name}**!")
        except Exception as e:
            await ctx.send(f"Error making purchase: {e}")

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
