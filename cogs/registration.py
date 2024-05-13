from discord.ext import commands
from discord import app_commands
import discord
import re
# from cogs import db
# from aiosqlite3 import IntegrityError
import logging
from config import TA_KEY

logger = logging.getLogger(__name__)

class Registration(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    """
    section_cmd = app_commands.Group(
        name='section',
        description='Links or unlinks a course section with a Discord channel.',
        default_permissions=discord.Permissions(8)
    )
    register_cmd = app_commands.Group(
        name='register',
        description='Registers your school ID and section.'
    )
    """

    @app_commands.command(name='get-ta-role')
    async def ta(self, inter):
        class Modal(discord.ui.Modal, title='Confirm'):
            key = discord.ui.TextInput(label='Enter the TA key for this server')
            async def on_submit(self, minter):
                if str(self.key) != TA_KEY:
                    return await minter.response.send_message(
                        "Incorrect TA key",
                        ephemeral=True
                    )

                ta_role = None   
                for role in inter.guild.roles:
                    if role.name.startswith("TA"):
                        ta_role = role
                        break

                if ta_role is None:
                    return await minter.response.edit_message(
                        content='Could not find the TA role. Check with your professors.',
                        view=None)

                # role = inter.guild.get_role(ta_role_id)

                await inter.user.add_roles(ta_role)
                await minter.response.send_message(
                    f":white_check_mark: You now have the {role.mention} role",
                    ephemeral=True
                )
                logger.info(f'gave the TA role to {inter.user.name}')
        modal = Modal()
        await inter.response.send_modal(modal)
        
    @app_commands.command(name='register')
    async def register_section(self, inter):
        """Lets me know your section."""

        sections = []
        for role in inter.guild.roles:
            if role.name.startswith("Section"):
                sections.append((role.id, role.name))

        if len(sections) == 0:
            await inter.response.send_message("Sections not found.", ephemeral=True)
            return 

        sections.sort(key=lambda role: role[1])

        select = discord.ui.Select(
            placeholder='Select a section',
            options=[discord.SelectOption(label=row[1], value=row[0]) for row in sections]
        )

        view = discord.ui.View()

        async def callback(vinter):
            section_id = int(vinter.data['values'][0])
            new_role = inter.guild.get_role(section_id)
            if new_role in inter.user.roles:
                await vinter.response.edit_message(
                    content=f'You already have section role {new_role.name}.',
                    view=None)
                return

            err_msg = ''

            for row in sections:
                role = inter.guild.get_role(row[0])
                if row[0] == section_id:
                    if role not in inter.user.roles:
                        try:
                            await inter.user.add_roles(role)
                            logger.info(f'added role {role.name} to {inter.user.name}')
                        except Exception as err:
                            err_msg = str(err)
                else:
                    if role in inter.user.roles:
                        try:
                            await inter.user.remove_roles(role)
                            logger.info(f'removed role {role.name} from {inter.user.name}')
                        except Exception as err:
                            err_msg = str(err)

            await vinter.response.edit_message(
                content=err_msg or f'Your section role has been successfully set to {new_role.name}.',
                view=None
            )

        select.callback = callback
        view.add_item(select)
        await inter.response.send_message('\u200b', view=view, ephemeral=True)

    '''
    @section_cmd.command(name='create')
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions()
    @app_commands.describe(
        name='The name of the section',
        channel='The Discord channel connected to the section',
        role='The Discord server role that the section members will have'
    )
    async def section_create(self, inter, name: str, channel: discord.TextChannel, role: discord.Role):
        """For an instructor to connect a new section to a channel."""

        top_role = inter.guild.me.top_role
        if role >= top_role:
            await inter.response.send_message(
                'The role you selected was higher than my highest role, so I am not able to add it to students.\n'
                f'Please visit `Server Settings` --> `Roles`, find the **{top_role.name}** role (my highest),'
                f' and click `Edit`. Then drag **{top_role.name}** above **{role.name}** and save changes.',
                ephemeral=True
            )
            return

        try:
            await db.insert_section(self.bot, inter.user.id, channel.id, role.id, name)
        except IntegrityError:
            await inter.response.send_message(
                'There is already a section with that name, channel, or role. '
                'If you would like to remove a section, run `/section remove`.',
                ephemeral=True
            )
            return
        await inter.response.send_message(
            f'`{name}` is now linked to {channel.mention}. Any students who register will be given {role.mention}.',
            ephemeral=True
        )

    @section_cmd.command(name='modify')
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions()
    @app_commands.describe(
        old_name='The existing name of the section to edit',
        new_name='The new name',
        channel='The new channel',
        role='The new role'
    )
    async def section_modify(self, inter, old_name: str, new_name: str = None, channel: discord.TextChannel = None, role: discord.Role = None):
        """For an instructor to edit the fields (name, channel, role) of an existing section."""

        top_role = inter.guild.me.top_role
        if role and role >= top_role:
            await inter.response.send_message(
                'The role you selected was higher than my highest role, so I am not able to add it to students.\n'
                f'Please visit `Server Settings` --> `Roles`, find the **{top_role.name}** role (my highest),'
                f' and click `Edit`. Then drag **{top_role.name}** above **{role.name}** and save changes.',
                ephemeral=True
            )
            return

        try:
            changes = await db.update_section(self.bot, old_name, new_name, channel, role)
        except db.NotFound:
            await inter.response.send_message(
                f'There is no existing section with name `{old_name}`.',
                ephemeral=True
            )
            return

        changelogs = []
        for name, value in changes.items():
            old, new = value
            if old != new:
                if name == 'role':
                    old = f'<@&{old}>'
                    new = f'<@&{new}>'
                    changelogs.append(f'**Role:** {old} `->` {new}')
                elif name == 'channel':
                    old = f'<#{old}>'
                    new = f'<#{new}>'
                    changelogs.append(f'**Channel:** {old} `->` {new}')
                else:
                    changelogs.append(f'**Name:** {old} `->` {new}')

        changelogs = '\n'.join(changelogs)

        await inter.response.send_message(
            f'Section was updated.\n\n{changelogs}',
            ephemeral=True
        )

    @section_cmd.command(name='remove')
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions()
    @app_commands.describe(name='The name of the section to remove')
    async def section_remove(self, inter, name: str):
        """For an instructor to remove a section that has already been created."""

        try:
            await db.delete_section(self.bot, name)
        except db.NotFound:
            await inter.response.send_message(
                f'There is no section with name `{name}`.',
                ephemeral=True
            )
            return
        except db.StudentsRemaining:
            await inter.response.send_message(
                f'There are still students registered in section `{name}`.',
                ephemeral=True
            )
            return

        await inter.response.send_message(
            f'Section `{name}` was removed. The corresponding role and channel have not been changed.',
            ephemeral=True
        )

    @section_cmd.command(name='list')
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions()
    async def section_list(self, inter):
        """Shows all the sections and the students in them."""

        sections = await db.fetch_sections(self.bot)
        if not sections:
            await inter.response.send_message(
                'You have not created any sections yet. Do `/section create` to create a new one.',
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f'Your Sections',
            color=0x2F3136,
        )
        for section in sections:
            name = section[4]
            role_id = section[3]
            channel_id = section[2]
            rows = await db.fetch_students(self.bot, section[0])
            mentions = '\n'.join([f'<@!{user_id}>' for user_id in [row[1] for row in rows]])
            role = f'<@&{role_id}>'
            channel = f'<#{channel_id}>'

            value = f'Hosted in {channel} with server role {role}\n\n{mentions}'
            embed.add_field(name=name, value=value)

        await inter.response.send_message(embed=embed, ephemeral=True)
    '''

async def setup(bot):
    await bot.add_cog(Registration(bot))
