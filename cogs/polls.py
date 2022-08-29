from discord.ext import commands
from discord import app_commands
import discord
import time
import asyncio
from cogs import db
import re
from config import DEFAULT_POINTS


class QuestionForm(discord.ui.Modal, title='What are you asking?'):
    question = discord.ui.TextInput(label='Type the question', style=discord.TextStyle.long, max_length=1024)

    async def on_submit(self, inter):
        await inter.response.send_message(f'Created poll in {inter.channel.mention}', ephemeral=True)
        self.stop()


class AnswerForm(discord.ui.Modal):
    answer = discord.ui.TextInput(label='Type your answer', style=discord.TextStyle.short)

    def __init__(self, title, *, poll_id):
        super().__init__(title=title)
        self.poll_id = poll_id

    async def on_submit(self, inter):
        answer = str(self.answer)
        await db.upsert_poll_response(inter.client, answer, inter.user.id, self.poll_id)
        await inter.response.send_message(f'Your answer:\n`{answer}`', ephemeral=True)


class Polls(commands.Cog):
    poll_cmd = app_commands.Group(
        name='poll',
        description='Parent command for creating multiple choice and written polls'
    )

    def __init__(self, bot):
        self.bot = bot
        self.saved_id = None
        self.ctx_menu = app_commands.ContextMenu(
            name='Reopen this poll',
            callback=self.reopen
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def create_poll(self, inter, typ, question, duration, points):
        poll_id = await db.insert_poll(
            self.bot,
            question,
            typ=0,
            duration=duration,
            poll_id=self.saved_id,
            points=points
        )
        self.saved_id = None

        end_time = int(time.time() + duration)
        view = discord.ui.View(timeout=None)

        if typ == 0:
            for letter in 'ABCDE':
                button = discord.ui.Button(label=letter, custom_id=letter, style=discord.ButtonStyle.blurple)

                async def callback(button_inter):
                    choice = button_inter.data['custom_id']

                    await db.upsert_poll_response(self.bot, choice, button_inter.user.id, poll_id)
                    await button_inter.response.send_message(f'You chose **{choice}**', ephemeral=True)

                button.callback = callback
                view.add_item(button)

            title = 'Multiple Choice Poll'
        else:
            btn_answer = discord.ui.Button(
                label='Enter your answer',
                emoji='\U0001f4ac',
                style=discord.ButtonStyle.blurple
            )
            modal = AnswerForm(question, poll_id=poll_id)

            async def answer_callback(answer_inter):
                await answer_inter.response.send_modal(modal)

            btn_answer.callback = answer_callback
            title = 'Written Answer Poll'
            view.add_item(btn_answer)

        btn_stop = discord.ui.Button(
            label='\u200b',
            emoji='\U0001f6d1',
            style=discord.ButtonStyle.red,
            row=1
        )
        btn_addtime = discord.ui.Button(
            label='+',
            emoji='\U000023f2',
            style=discord.ButtonStyle.green,
            row=1
        )

        manualstop = False

        async def stop_callback(stop_inter):
            nonlocal manualstop

            if not stop_inter.user.guild_permissions.administrator:
                return

            manualstop = True

            stop_task.cancel()
            view.stop()
            await stop_inter.response.send_message(
                'Poll stopped. Reopen or grade it by clicking the `...` on the poll message, and going to `Apps`',
                ephemeral=True
            )

        btn_stop.callback = stop_callback

        async def addtime_callback(addtime_inter):
            nonlocal stop_task
            nonlocal end_time

            if not addtime_inter.user.guild_permissions.administrator:
                return

            stop_task.cancel()
            end_time += 20
            stop_task = self.bot.loop.create_task(stop(end_time))
            embed.set_field_at(0, name='Expires', value=f'<t:{end_time}:R>')

            await m.edit(embed=embed)
            await addtime_inter.response.send_message('20 seconds added', ephemeral=True)

        btn_addtime.callback = addtime_callback

        view.add_item(btn_stop)
        view.add_item(btn_addtime)

        embed = discord.Embed(
            title=title,
            description=question,
            color=0x2F3136
        ).add_field(
            name='Expires',
            value=f'<t:{end_time}:R>'
        ).set_author(
            name=f'ID: {poll_id}'
        )

        m = await inter.channel.send(embed=embed, view=view)

        async def stop(end):
            await asyncio.sleep(end - time.time())
            view.stop()

        stop_task = self.bot.loop.create_task(stop(end_time))

        await view.wait()

        if not manualstop:
            await inter.followup.send(
                'Poll stopped. Reopen or grade it by clicking the `...` on the poll message, and going to `Apps`',
                ephemeral=True
            )

        embed.set_field_at(0, name='Expired', value='Waiting to be graded...')
        for button in view.children:
            button.disabled = True

        await m.edit(embed=embed, view=view)

    @app_commands.default_permissions()
    @app_commands.checks.has_permissions(administrator=True)
    async def reopen(self, inter, message: discord.Message):
        poll_id = None

        if message.author.id == self.bot.user.id and message.embeds and message.embeds[0].author:
            embed = message.embeds[0]
            poll_id = re.findall(r'ID: (\d+)', embed.author.name)

        if not poll_id:
            return await inter.response.send_message(
                'This message is not a poll.',
                ephemeral=True
            )

        poll_id = int(poll_id[0])
        query = 'SELECT answers, question, type, duration FROM polls WHERE id = ?'
        row = await self.bot.db_fetchone(query, poll_id)

        if row[0] is not None:
            return await inter.response.send_message(
                'You have already graded this poll.',
                ephemeral=True
            )

        await inter.response.send_message(
            f'Reopening poll #{poll_id}',
            ephemeral=True
        )
        self.saved_id = poll_id
        question = row[1]
        typ = row[2]
        duration = row[3]

        query = 'DELETE FROM polls WHERE id = ?'
        await self.bot.db_execute(query, poll_id)
        await self.create_poll(inter, typ, question, duration)

    @poll_cmd.command(name='choice')
    @app_commands.default_permissions()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        duration='The time (in seconds) before the poll expires'
    )
    async def choice(self, inter, duration: int = 60, points: int = DEFAULT_POINTS):
        """Creates a multiple-choice poll."""

        query = 'SELECT * FROM sections WHERE channel_id = ?'
        exists = await self.bot.db_fetchone(query, inter.channel.id)
        if not exists:
            await inter.response.send_message(
                'This channel is not linked to a section. Do `/section create` to create a new section.',
                ephemeral=True
            )
            return

        modal = QuestionForm()
        await inter.response.send_modal(modal)
        await modal.wait()
        question = str(modal.question)
        await self.create_poll(inter, 0, question, duration, points)

    @poll_cmd.command()
    @app_commands.default_permissions()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        duration='The time (in seconds) before the poll expires'
    )
    async def written(self, inter, duration: int = 60, points: int = DEFAULT_POINTS):
        """Creates a poll that requires a self-written response."""

        query = 'SELECT channel_id FROM sections WHERE instructor_id = ?'
        channel_id = await self.bot.db_fetchone(query, inter.user.id)
        if not channel_id:
            await inter.response.send_message(
                'You have not created a section yet. Do `/section create` to create one.',
                ephemeral=True
            )
            return

        modal = QuestionForm()
        await inter.response.send_modal(modal)
        await modal.wait()
        question = str(modal.question)
        await self.create_poll(inter, 1, question, duration, points)


async def setup(bot):
    await bot.add_cog(Polls(bot))
