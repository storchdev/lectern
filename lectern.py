import discord
from discord.ext import commands
from config import TOKEN, DB_FILENAME
import os
from cogs.utils import get_emojis
from typing import Literal, Optional

discord.utils.setup_logging()

if not os.path.exists(DB_FILENAME):
    new = True
else:
    new = False
    

intents = discord.Intents.default()
intents.members = True 

bot = commands.Bot(
    intents=intents,
    command_prefix='l '
)


@bot.event
async def setup_hook():
    bot.loop.create_task(startup())


@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
    for cmd in ctx.bot.tree.get_commands():
        cmd.guild_only = True 
        
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return

    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

async def startup():
    await bot.wait_until_ready()

    cogs = (
        'cogs.db',
        'cogs.registration',
        'cogs.polls',
        'cogs.grading',
        'cogs.sessions'
    )
    for cog in cogs:
        await bot.load_extension(cog)
        print(f'Loaded {cog}')

    if new:
        await bot.tree.sync()
        guild = bot.guilds[0]
        roles = [guild.self_role]
        for image in os.listdir('assets'):
            with open(f'assets/{image}', 'rb') as f:
                await guild.create_custom_emoji(name=image[:-4], image=f.read(), roles=roles)

    get_emojis(bot)

    print('----------------------------------------------------')
    print(f'{bot.user} is ready.')
    print(f'{len(bot.guilds)} GUILDS | {len(bot.users)} USERS')


if __name__ == '__main__':
    bot.run(TOKEN)
