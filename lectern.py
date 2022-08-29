import discord
from discord.ext import commands
from config import TOKEN, PSQL_LOGIN
import asyncpg


class Lectern(commands.Bot):

    def __init__(self):
        super().__init__(
            intents=discord.Intents.all(),
            command_prefix=None,
        )
        self.db = None

    async def setup_hook(self):
        self.db = await asyncpg.create_pool(**PSQL_LOGIN)

        await self.wait_until_ready()
        print(f'Connected to {len(self.guilds)} guilds, {len(self.users)} users')


lectern = Lectern()


