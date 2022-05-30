import discord
from discord import file
from discord.ext import commands, tasks
from discord.ext.commands import bot
import asyncio
from discord.ext.commands import has_permissions
from random import choice
from discord.utils import get
from datetime import datetime, timedelta
import os
import aiosqlite
import json
import random
import string
import logging
from colorama import Fore, Back, Style


intents = discord.Intents.all()
client = commands.Bot(command_prefix='%', case_insensitive = True,intents=intents)
client.remove_command('help')

@client.event
async def on_ready():
    print('The bot is ready.')

async def update_totals(member):
    invites = await member.guild.invites()

    c = datetime.today().strftime("%Y-%m-%d").split("-")
    c_y = int(c[0])
    c_m = int(c[1])
    c_d = int(c[2])

    async with client.db.execute("SELECT id, uses FROM invites WHERE guild_id = ?", (member.guild.id,)) as cursor: # this gets the old invite counts
        async for invite_id, old_uses in cursor:
            for invite in invites:
                if invite.id == invite_id and invite.uses - old_uses > 0: # the count has been updated, invite is the invite that member joined by
                    if not (c_y == member.created_at.year and c_m == member.created_at.month and c_d - member.created_at.day < 7): # year can only be less or equal, month can only be less or equal, then check days
                        print(invite.id)
                        await client.db.execute("UPDATE invites SET uses = uses + 1 WHERE guild_id = ? AND id = ?", (invite.guild.id, invite.id))
                        await client.db.execute("INSERT OR IGNORE INTO joined (guild_id, inviter_id, joiner_id) VALUES (?,?,?)", (invite.guild.id, invite.inviter.id, member.id))
                        await client.db.execute("UPDATE totals SET normal = normal + 1 WHERE guild_id = ? AND inviter_id = ?", (invite.guild.id, invite.inviter.id))

                    else:
                        await client.db.execute("UPDATE totals SET normal = normal + 1, fake = fake + 1 WHERE guild_id = ? and inviter_id = ?", (invite.guild.id, invite.inviter.id))

                    return

# events
@client.event
async def on_member_join(member):
    await update_totals(member)
    await client.db.commit()
        
@client.event
async def on_member_remove(member):
    cur = await client.db.execute("SELECT inviter_id FROM joined WHERE guild_id = ? and joiner_id = ?", (member.guild.id, member.id))
    res = await cur.fetchone()
    if res is None:
        return
    
    inviter = res[0]
    
    await client.db.execute("DELETE FROM joined WHERE guild_id = ? AND joiner_id = ?", (member.guild.id, member.id))
    await client.db.execute("DELETE FROM totals WHERE guild_id = ? AND inviter_id = ?", (member.guild.id, member.id))
    await client.db.execute("UPDATE totals SET left = left + 1 WHERE guild_id = ? AND inviter_id = ?", (member.guild.id, inviter))
    await client.db.commit()

@client.event
async def on_invite_create(invite):
    await client.db.execute("INSERT OR IGNORE INTO totals (guild_id, inviter_id, normal, left, fake) VALUES (?,?,?,?,?)", (invite.guild.id, invite.inviter.id, invite.uses, 0, 0))
    await client.db.execute("INSERT OR IGNORE INTO invites (guild_id, id, uses) VALUES (?,?,?)", (invite.guild.id, invite.id, invite.uses))
    await client.db.commit()
    
@client.event
async def on_invite_delete(invite):
    await client.db.execute("DELETE FROM invites WHERE guild_id = ? AND id = ?", (invite.guild.id, invite.id))
    await client.db.commit()

@client.event
async def on_guild_join(guild): # add new invites to monitor
    for invite in await guild.invites():
        await client.db.execute("INSERT OR IGNORE INTO invites (guild_id, id, uses), VAlUES (?,?,?)", (guild.id, invite.id, invite.uses))
        
    await client.db.commit()
    
@client.event
async def on_guild_remove(guild): # remove all instances of the given guild_id
    await client.db.execute("DELETE FROM totals WHERE guild_id = ?", (guild.id,))
    await client.db.execute("DELETE FROM invites WHERE guild_id = ?", (guild.id,))
    await client.db.execute("DELETE FROM joined WHERE guild_id = ?", (guild.id,))

    await client.db.commit()


@client.event
async def on_member_join(member):
    channel = client.get_channel(978962393960939530)
    embed=discord.Embed(title=f"{member.name}",description=" Dobrodosao u day bar server zabavi se i budi aktivan\n Prije svega pročitajte pravila",color=0x00ff00)
    embed.set_thumbnail(url=member.avatar_url)
  
    await channel.send(embed=embed)


@client.command(pass_context=True)
@commands.has_permissions(kick_members=True)
async def announce(ctx,*,message):
    embed = discord.Embed(title="Announcement", description=message, color=0x00ff00)
    await ctx.send(embed=embed)

@client.command(aliases=["av"])
async def avatar(ctx,*, member: discord.Member=None):
    if not member:
        member = ctx.message.author
    userAvatar = member.avatar_url
    
    embed = discord.Embed(colour=member.color, timestamp=ctx.message.created_at)
    embed.set_author(name=f"Avatar of {member}")
    embed.set_image(url=member.avatar_url)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.message.author.avatar_url)
    
    await ctx.send(embed=embed)

@client.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx,amount=2):
    await ctx.channel.purge(limit=amount)

@client.command()
@commands.has_permissions(kick_members=True)   
async def kick(context, member : discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await context.send(f'{member} kicked')

@client.command()
@commands.has_permissions(ban_members=True)   
async def ban(context, member : discord.Member, *, reason=None):
    await member.ban(reason=reason)
    await context.send(f'{member} has been banned')


@client.command(description="Mutes the specified user.")
@commands.has_permissions(manage_messages=True)
async def mute(ctx, member : discord.Member, *, reason=None):
    guild = ctx.guild
    mutedRole = discord.utils.get(guild.roles, name="Muted")
    
    if not mutedRole:
        mutedRole = await guild.create_role(name="Muted")
        
        for channel in guild.text_channels:
            await channel.set_permissions(mutedRole, speak=False, send_messages=False, read_message_history=False, read_messages=False)
            
    await member.add_roles(mutedRole, reason=reason)
    await ctx.send(f"Muted {member.mention} for {reason}")
    await member.send(f"You have been muted in {guild.name} for {reason}")
           
@client.command(description="Unmutes the specified user.")
@commands.has_permissions(manage_messages=True)
async def unmute(ctx, member : discord.Member, *, reason=None):
    guild = ctx.guild
    mutedRole = discord.utils.get(guild.roles, name="Muted")
    
    await member.remove_roles(mutedRole, reason=reason)
    await ctx.send(f"Unmuted {member.mention} for {reason}")
    await member.send(f"You have been unmuted in {guild.name} for {reason}")
    
@client.command()
@commands.has_permissions(send_messages=True)
async def membercount(ctx):
    await ctx.send(f"The server has {len(ctx.guild.members)} members")

@client.command()
async def invites(ctx, member: discord.Member=None):
    if member is None: member = ctx.author

    # get counts
    cur = await client.db.execute("SELECT normal, left, fake FROM totals WHERE guild_id = ? AND inviter_id = ?", (ctx.guild.id, member.id))
    res = await cur.fetchone()
    if res is None:
        normal, left, fake = 0, 0, 0

    else:
        normal, left, fake = res

    total = normal - (left + fake)
    
    em = discord.Embed(
        title=f"{member.name}#{member.discriminator}",
        description=f"{member.mention} currently has **{total}** invites. (**{normal}** normal, **{left}** left, **{fake}** fake).",
        timestamp=datetime.now(),
        colour=discord.Colour.orange())

    await ctx.send(embed=em)
    
async def setup():
    await client.wait_until_ready()
    client.db = await aiosqlite.connect("inviteData.db")
    await client.db.execute("CREATE TABLE IF NOT EXISTS totals (guild_id int, inviter_id int, normal int, left int, fake int, PRIMARY KEY (guild_id, inviter_id))")
    await client.db.execute("CREATE TABLE IF NOT EXISTS invites (guild_id int, id string, uses int, PRIMARY KEY (guild_id, id))")
    await client.db.execute("CREATE TABLE IF NOT EXISTS joined (guild_id int, inviter_id int, joiner_id int, PRIMARY KEY (guild_id, inviter_id, joiner_id))")
    
    # fill invites if not there
    for guild in client.guilds:
        for invite in await guild.invites(): # invites before bot was added won't be recorded, invitemanager/tracker don't do this
            await client.db.execute("INSERT OR IGNORE INTO invites (guild_id, id, uses) VALUES (?,?,?)", (invite.guild.id, invite.id, invite.uses))
            await client.db.execute("INSERT OR IGNORE INTO totals (guild_id, inviter_id, normal, left, fake) VALUES (?,?,?,?,?)", (guild.id, invite.inviter.id, 0, 0, 0))
                                 
    await client.db.commit()

@client.command()
async def warn(ctx, member : discord.Member, *, reason=None):
    await member.send(f"You have been warned in {ctx.guild.name} for {reason}")
    await ctx.send(f"Warned {member.mention} for {reason}")
    
@client.command()
async def unwarn(ctx, member : discord.Member, *, reason=None):
    await member.send(f"You have been unwarned in {ctx.guild.name} for {reason}")
    await ctx.send(f"Unwarned {member.mention}")

@client.command()
async def serverinfo(ctx):
    embed = discord.Embed(title="Server Information", value=ctx.message.guild.name, color=0x9208ea)
    embed.add_field(name="Server Name", value=ctx.guild.name, inline=True)
    embed.add_field(name="Roles:", value=len(ctx.message.guild.roles), inline=True)
    embed.add_field(name="Members:", value=len(ctx.message.guild.members))
    embed.add_field(name="Owner:", value=ctx.message.guild.owner)
    embed.add_field(name="Region:", value=ctx.message.guild.region)
    embed.add_field(name="Channels" , value=len(ctx.message.guild.channels))
    embed.add_field(name="Verification Level:", value=ctx.message.guild.verification_level)
    embed.add_field(name="Requested by:", value=ctx.message.author)
    embed.add_field(name="emojis:", value=len(ctx.message.guild.emojis))
    embed.add_field(name="Role Count:", value=len(ctx.message.guild.roles))
    await ctx.send(embed=embed)  

@client.command()
async def help(ctx):
    embed = discord.Embed(title="Help", description="List of commands", color=0x9208ea)
    embed.add_field(name="invites", value="Shows your current invite count.")
    embed.add_field(name="avatar", value="Shows your avatar.")
    embed.add_field(name="serverinfo", value="Shows server information.")
    
    await ctx.send(embed=embed)

@client.command(aliases = ['start , g'])
@commands.has_permissions(manage_guild = True)
async def giveaway(ctx):
    await ctx.send(embed=discord.Embed(color=discord.Color.green(), title = "Select the channel, you would like the giveaway to be in"))
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    try:
        msg1 = await client.wait_for('message', check = check, timeout=30.0)

        channel_converter = discord.ext.commands.TextChannelConverter()
        try:
            giveawaychannel = await channel_converter.convert(ctx, msg1.content)
        except commands.BadArgument:
            return await ctx.send(embed=discord.Embed(color=discord.Color.red(), title = "This channel doesn't exist, please try again"))

    except asyncio.TimeoutError:
        await ctx.send("You took to long, please try again!")
    if not giveawaychannel.permissions_for(ctx.guild.me).send_messages or  not giveawaychannel.permissions_for(ctx.guild.me).add_reactions:
        return await ctx.send(embed=discord.Embed(color=discord.Color.red(), description = f"Bot does not have correct permissions to send in: {giveawaychannel}\n **Permissions needed:** ``Add reactions | Send messages``"))

    await ctx.send(embed=discord.Embed(color=discord.Color.green(), title = "How many winners to the giveaway would you like?"))
    try:
        msg2 = await client.wait_for('message', check = check, timeout=30.0)
        try:
            winerscount = int(msg2.content)
        except ValueError:
            return await ctx.send(embed=discord.Embed(color=discord.Color.red(), title = "You didn't specify a number of winners, please try again."))

    except asyncio.TimeoutError:
        await ctx.send("You took to long, please try again!")

    await ctx.send(embed=discord.Embed(color=discord.Color.green(), title = "Select an amount of time for the giveaway."))
    try:
        since = await client.wait_for('message', check = check, timeout=30.0)

    except asyncio.TimeoutError:
        await ctx.send("You took to long, please try again!")


    seconds = ("s", "sec", "secs", 'second', "seconds")
    minutes= ("m", "min", "mins", "minute", "minutes")
    hours= ("h", "hour", "hours")
    days = ("d", "day", "days")
    weeks = ("w", "week", "weeks")
    rawsince = since.content
    try:
        time = int(since.content.split(" ")[0])
    except ValueError:
        return await ctx.send(embed=discord.Embed(color=discord.Color.red(), title = "You did not specify a unit of time, please try again."))
    since = since.content.split(" ")[1]
    if since.lower() in seconds:
        timewait = time
    elif since.lower() in minutes:
        timewait = time*60
    elif since.lower() in hours:
        timewait = time*3600
    elif since.lower() in days:
        timewait = time*86400
    elif since.lower() in weeks:
        timewait = time*604800
    else:
        return await ctx.send(embed=discord.Embed(color=discord.Color.red(), title = "You did not specify a unit of time, please try again."))
        
    prizeembed = discord.Embed(title = "What would you like the prize to be?" , color = discord.Color.green())
    await ctx.send(embed = prizeembed)
    try:
        msg4 = await client.wait_for('message', check = check, timeout=30.0)


    except asyncio.TimeoutError:
        await ctx.send("You took to long, please try again.")

    logembed = discord.Embed(title = "Giveaway Logged" , description = f"**Prize:** ``{msg4.content}``\n**Winners:** ``{winerscount}``\n**Channel:** {giveawaychannel.mention}\n**Host:** {ctx.author.mention}" , color = discord.Color.red())
    logembed.set_thumbnail(url = ctx.author.avatar_url)
    
    guild = client.get_guild(977944889272713307) # Put your guild ID here!
    logchannel = guild.get_channel(979322719344668705) # Put your channel, you would like to send giveaway logs to.
    await logchannel.send(embed = logembed)

    futuredate = datetime.utcnow() + timedelta(seconds=timewait)
    embed1 = discord.Embed(color = discord.Color(random.randint(0x000000, 0xFFFFFF)), title=f"🎉GIVEAWAY🎉\n`{msg4.content}`",timestamp = futuredate, description=f'React with 🎉 to enter!\nEnd Date: {futuredate.strftime("%a, %b %d, %Y %I:%M %p")}\nHosted by: {ctx.author.mention}')
    
    embed1.set_footer(text=f"Giveaway will end")
    msg = await giveawaychannel.send(embed=embed1)
    await msg.add_reaction("🎉")
    await asyncio.sleep(timewait)
    message = await giveawaychannel.fetch_message(msg.id)
    for reaction in message.reactions:
        if str(reaction.emoji) == "🎉":
            users = await reaction.users().flatten()
            if len(users) == 1:
                return await msg.edit(embed=discord.Embed(title="Nobody has won"))

    winners = random.sample([user for user in users if not user.bot], k=winerscount)
    
    #await message.clear_reactions()
    winnerstosend = "\n".join([winner.mention for winner in winners])

    win = await msg.edit(embed = discord.Embed(title = "WINNER" , description = f"Congratulations {winnerstosend}, you have won **{msg4.content}**!" , color = discord.Color.blue()))
    
    
# Reroll command, used for chosing a new random winner in the giveaway
@client.command()
@commands.has_permissions(manage_guild = True)
async def reroll(ctx):
    async for message in ctx.channel.history(limit=100 , oldest_first = False):
        if message.author.id == client.user.id and message.embeds:
            reroll = await ctx.fetch_message(message.id)
            users = await reroll.reactions[0].users().flatten()
            users.pop(users.index(client.user))
            winner = random.choice(users)
            await ctx.send(f"The new winner is {winner.mention}")
            break
    else:
        await ctx.send("No giveaways going on in this channel.")

client.loop.create_task(setup())   
client.run("OTUxOTI5MTQwNDc3NTc5MzU0.Gjy485.bZ4EpBUBYkJiGZD5SSp97eNewTlGJ_KZzExeCE")
asyncio.run(client.db.close())
