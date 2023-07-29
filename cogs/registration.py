from discord.ext import commands
from discord import app_commands
import discord
from config import UNIV_ID_REGEX
import re
from cogs import db
from aiosqlite3 import IntegrityError
import logging
from config import TA_KEY, TA_ROLE_ID


class NetIDForm(discord.ui.Modal):
    univ_id = discord.ui.TextInput(label='Your NetID', style=discord.TextStyle.short)

    def __init__(self, title):
        super().__init__(title=title)
        self.inter = None

    async def on_submit(self, inter):
        univ_id = str(self.univ_id)

        if not re.match(UNIV_ID_REGEX, univ_id):
            await inter.response.send_message(
                'Please try again and enter a NetID.',
                ephemeral=True
            )
            return

        self.inter = inter
        self.stop()


class Registration(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    section_cmd = app_commands.Group(
        name='section',
        description='Links or unlinks a course section with a Discord channel.',
        default_permissions=discord.Permissions(8)
    )
    register_cmd = app_commands.Group(
        name='register',
        description='Registers your school ID and section.'
    )

    @app_commands.command(name='give-me-ta')
    async def ta(self, inter):
        class Modal(discord.ui.Modal, title='Confirm'):
            key = discord.ui.TextInput(label='Enter the TA key for this server')
            async def on_submit(self, minter):
                if str(self.key) != TA_KEY:
                    return await minter.response.send_message(
                        "Incorrect TA key",
                        ephemeral=True
                    )
                role = inter.guild.get_role(TA_ROLE_ID)
                await inter.user.add_roles(role)
                await minter.response.send_message(
                    f":white_check_mark: Gave you the {role.mention} role",
                    ephemeral=True
                )
        modal = Modal()
        await inter.response.send_modal(modal)
        

    @register_cmd.command(name='netid')
    async def register_netid(self, inter):
        """Lets me know your school ID."""

        modal = NetIDForm('Link Your University ID')
        await inter.response.send_modal(modal)
        await modal.wait()

        univ_id = str(modal.univ_id)
        query = '''INSERT INTO students (user_id, univ_id) 
                   VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE
                   SET univ_id = ?
                '''
        await self.bot.db_execute(query, inter.user.id, univ_id, univ_id)

        await modal.inter.response.send_message(
            'Your NetID has been successfully linked to your Discord.',
            ephemeral=True
        )

    @register_cmd.command(name='section')
    async def register_section(self, inter):
        """Lets me know your section."""

        sections = await db.fetch_sections(self.bot)
        select = discord.ui.Select(
            placeholder='Select a section',
            options=[discord.SelectOption(label=row[4], value=row[0]) for row in sections]
        )

        view = discord.ui.View()

        async def callback(vinter):
            section_id = int(vinter.data['values'][0])
            query = '''INSERT INTO students (user_id, section_id) 
                       VALUES (?, ?)
                       ON CONFLICT(user_id) DO UPDATE
                       SET section_id = ?
                    '''
            await self.bot.db_execute(query, inter.user.id, section_id, section_id)

            err_msg = ''

            for row in sections:
                role = inter.guild.get_role(row[3])
                if row[0] == section_id:
                    if role not in inter.user.roles:
                        try:
                            await inter.user.add_roles(role)
                            print(f'added role {role.name}')
                        except Exception as err:
                            err_msg = str(err)
                else:
                    if role in inter.user.roles:
                        try:
                            await inter.user.remove_roles(role)
                            print(f'removed role {role.name}')
                        except Exception as err:
                            err_msg = str(err)

            await vinter.response.edit_message(
                content=err_msg or 'Your section has been successfully linked.',
                view=None
            )

        select.callback = callback
        view.add_item(select)
        await inter.response.send_message('\u200b', view=view, ephemeral=True)

    @section_cmd.command(name='create')
    @app_commands.checks.has_permissions(administrator=True)
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


async def setup(bot):
    await bot.add_cog(Registration(bot))
