from discord.ext import commands
import discord

class Db(commands.Cog):
    """The description for Db goes here."""

    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(Db(bot))
