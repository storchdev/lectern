import discord
from discord.ext import commands
from config import TOKEN, DB_FILENAME
import os
from cogs.utils import get_emojis
from typing import Literal, Optional
import logging

discord.utils.setup_logging()

logger = logging.getLogger(__name__)

intents = discord.Intents.all()

bot = commands.Bot(
    intents=intents,
    command_prefix='//'
)

@bot.event
async def setup_hook():
    bot.loop.create_task(startup())

@bot.command()
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
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
        'cogs.registration',
        'cogs.polls',
        # 'cogs.db',
        # 'cogs.grading',
        # 'cogs.sessions'
        'jishaku'
    )
    for cog in cogs:
        await bot.load_extension(cog)
        logger.info(f'Loaded {cog}')

    if args.sync:
        await bot.tree.sync()
        '''
        guild = bot.guilds[0]
        roles = [guild.self_role]
        for image in os.listdir('assets'):
            with open(f'assets/{image}', 'rb') as f:
                await guild.create_custom_emoji(name=image[:-4], image=f.read(), roles=roles)
        '''

    # get_emojis(bot)

    logger.info(f'{bot.user} is ready.')
    logger.info(f'{len(bot.guilds)} GUILDS | {len(bot.users)} USERS')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Lectern bot')
    parser.add_argument('-v', action='count', help='generate trace file')
    parser.add_argument('--sync', action='store_true', help='sync commands')

    args = parser.parse_args()

    if args.v:
        logging.basicConfig(level=logging.DEBUG)
    else: 
        logging.basicConfig(level=logging.INFO)

    logging.debug(args)

    bot.run(TOKEN)
