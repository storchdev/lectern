from discord.ext import commands
import discord

class Registration(commands.Cog):
    """The description for Registration goes here."""

    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(Registration(bot))
