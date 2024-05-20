import discord
from discord.ext import commands
import os
import datetime
import logging
import traceback
import typing

from config import TOKEN

class MyBot(commands.Bot):
    _uptime: datetime.datetime = datetime.datetime.now()

    def __init__(self, prefix: str, ext_dir: str, synced: bool, *args: typing.Any, **kwargs: typing.Any) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(*args, **kwargs, command_prefix=commands.when_mentioned_or(prefix), intents=intents)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ext_dir = ext_dir
        # self.synced = False
        self.synced = synced

    async def _load_extensions(self) -> None:
        cogs = (
            'cogs.registration',
            'cogs.polls',
            # 'cogs.db',
            # 'cogs.grading',
            # 'cogs.sessions'
            'jishaku'
        )
        for cog in cogs:
            try:
                await self.load_extension(cog)
                self.logger.info(f"Loaded extension {cog}")
            except commands.ExtensionError:
                self.logger.error(f"Failed to load extension {cog}\n{traceback.format_exc()}")
        return


        # the following load all extensions in the ext_dir
        if not os.path.isdir(self.ext_dir):
            self.logger.error(f"Extension directory {self.ext_dir} does not exist.")
            return
        for filename in os.listdir(self.ext_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                try:
                    await self.load_extension(f"{self.ext_dir}.{filename[:-3]}")
                    self.logger.info(f"Loaded extension {filename[:-3]}")
                except commands.ExtensionError:
                    self.logger.error(f"Failed to load extension {filename[:-3]}\n{traceback.format_exc()}")

    async def on_error(self, event_method: str, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.logger.error(f"An error occurred in {event_method}.\n{traceback.format_exc()}")

    async def on_ready(self) -> None:
        # Note that this might be called many times
        self.logger.info(f"Logged in as {self.user} ({self.user.id})")
        self.logger.info(f'{len(self.guilds)} GUILDS | {len(self.users)} USERS')

    async def setup_hook(self) -> None:
        await self._load_extensions()
        if not self.synced:
            await self.tree.sync()
            self.synced = not self.synced
            self.logger.info("Synced command tree")

    async def close(self) -> None:
        await super().close()
        # await self.client.close()

    def run(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        try:
            super().run(TOKEN, *args, **kwargs)
        except (discord.LoginFailure, KeyboardInterrupt):
            self.logger.info("Exiting...")
            exit()

    @property
    def user(self) -> discord.ClientUser:
        assert super().user, "Bot is not ready yet"
        return typing.cast(discord.ClientUser, super().user)

    @property
    def uptime(self) -> datetime.timedelta:
        return datetime.datetime.now() - self._uptime

@commands.command()
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def sync(ctx: commands.Context, 
               guilds: commands.Greedy[discord.Object], 
               spec: typing.Optional[typing.Literal["~", "*", "^"]] = None) -> None:
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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Lectern bot')
    parser.add_argument('-v', action='count', default=0, help='verbose')
    parser.add_argument('--sync', action='store_true', help='sync commands')

    args = parser.parse_args()

    if args.v > 0:
        discord.utils.setup_logging(level=logging.DEBUG)
        # logging.basicConfig(level=logging.DEBUG)
    else: 
        # the default level is INFO
        discord.utils.setup_logging(level=logging.INFO)

    logger = logging.getLogger("__main__")
    logger.debug(args)

    # logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

    discord.VoiceClient.warn_nacl = False
    bot = MyBot(prefix="!", ext_dir="cogs", synced=not args.sync)
    bot.add_command(sync)
    bot.run()
