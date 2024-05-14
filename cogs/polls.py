from discord.ext import commands
from discord import app_commands
import discord
import time
import asyncio
import logging
# import re

from config import LOG_DIR
from datetime import datetime
from pathlib import Path

import typing
import traceback
from discord.ui.select import BaseSelect

logger = logging.getLogger(__name__)

DEFAULT_QUESTION = "Lecture 1.1 slide 10"

def     get_unique_uc_id(inter):
    return f"{inter.user.id}.{inter.channel_id}" # .{inter.guild_id}"

class PollQuestion:

    def __init__(self, question, typ, inter):
        self.question = question
        self.typ = typ
        self.interaction = inter
        self.responses = {}
        self.start_time = time.time()
        self.uc_id = get_unique_uc_id(inter) 
        self.open = True
        self.saved = False

    def add_answer(self, sid, answer):
        self.responses[sid] = answer
        logger.info(f"User {sid}'s answer is {answer}")

    def end(self):
        self.open = False

    def isOpen(self):
        return self.open

    def save(self, dstfile):
        """append the poll to dstfile"""

        if self.open: 
            return False
        if self.saved: 
            return False
        dt_local = datetime.fromtimestamp(self.start_time).astimezone()

        time_str = dt_local.strftime("%Y-%m-%d %H:%M:%S")
        data = f'Time: {time_str}\n\nQuestion: {self.question}\n\nResponses:\n'
        for k,v in self.responses.items():
            data += f'{k},{v}\n'
        with dstfile.open("a") as file:
            file.write(data)
            file.write("\n")
        self.saved = True
        return True

async def display_results(inter, poll, keepprivate):

    total = len(poll.responses)
    if total == 0: 
        await inter.response.send_message('The poll did not have any responses.',
            ephemeral=True)
        return

    embed = discord.Embed(
        title="Poll results",
        description=poll.question,
        color=0x2F3136
    ); 

    answerdict = {}

    for k, v in poll.responses.items():

        answer = v.upper()

        if answer in answerdict:
            answerdict[answer] += 1
        else:
            answerdict[answer] = 1
        
    if poll.typ: 
        answers = [ (k, v) for k, v in sorted(answerdict.items(), key=lambda item: item[1], reverse=True)]
    else:
        answers = [ (k, v) for k, v in sorted(answerdict.items(), key=lambda item: item[0], reverse=True)]

    embed.clear_fields()

    full_bar = "\u2588"*12
    n = min(len(answers), 10)
    for i in range(n):
        choice = answers[i][0]
        p = round(answers[i][1]/total*100)
        # bar = bar_from_p(bot, p)
        e = (p // 10) + 1 
        bar = full_bar[0:e]

        embed.add_field(
            name=choice,
            value=f'`{bar}`  **{p}%**',
            inline=False
        )
    
    embed.set_footer(text=f'{total} response(s)')

    await inter.response.send_message(embed=embed, ephemeral=keepprivate)
    # await inter.response.send_message(embed=embed)

class QuestionForm(discord.ui.Modal, title='What is the question you are asking?'):
    question = discord.ui.TextInput(label='Type the question', 
            style=discord.TextStyle.long, 
            max_length=1024)

    def __init__(self, default_question):
        super().__init__()
        self.question.default = default_question

    async def on_submit(self, inter):
        await inter.response.send_message(f'Created poll in {inter.channel.mention}', ephemeral=True)
        self.stop()

class AnswerForm(discord.ui.Modal, title="Answer"):
    answer = discord.ui.TextInput(label='Enter your answer', 
             style=discord.TextStyle.short,
             max_length=40)

    def __init__(self, poll):
        super().__init__()
        self.poll = poll

    async def on_submit(self, inter):
        answer = str(self.answer)
        # await db.upsert_poll_response(inter.client, answer, inter.user.id, self.poll_id)
        self.poll.add_answer(inter.user.id, answer)
        await inter.response.send_message(f'Your answer:\n`{answer}`', ephemeral=True)
        self.stop()

# Based on examples on 
# https://fallendeity.github.io/discord.py-masterclass/views
class PollView(discord.ui.View):
    interaction: discord.Interaction | None = None
    message: discord.Message | None = None

    def __init__(self, user: discord.User | discord.Member, poll, timeout: float = 600.0):
        super().__init__(timeout=timeout)
        self.user = user
        self.poll = poll

    # make sure that the view only processes interactions from the user who invoked the command
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "You cannot interact with this view.", ephemeral=True
            )
            return False
        # update the interaction attribute when a valid interaction is received
        """
        self.interaction = interaction
        return True

    # to handle errors we first notify the user that an error has occurred and then disable all components

    def _disable_all(self) -> None:
        # disable all components
        # so components that can be disabled are buttons and select menus
        for item in self.children:
            if isinstance(item, discord.ui.Button) or isinstance(item, BaseSelect):
                item.disabled = True
        self.poll.end()

    # after disabling all components we need to edit the message with the new view
    # now when editing the message there are two scenarios:
    # 1. the view was never interacted with i.e in case of plain timeout here message attribute will come in handy
    # 2. the view was interacted with and the interaction was processed and we have the latest interaction stored in the interaction attribute
    async def _edit(self, **kwargs: typing.Any) -> None:
        if self.interaction is None and self.message is not None:
            # if the view was never interacted with and the message attribute is not None, edit the message
            await self.message.edit(**kwargs)
        elif self.interaction is not None:
            try:
                # if not already responded to, respond to the interaction
                await self.interaction.response.edit_message(**kwargs)
            except discord.InteractionResponded:
                # if already responded to, edit the response
                await self.interaction.edit_original_response(**kwargs)

    # async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[PollView]) -> None:
    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        message = f"An error occurred while processing the interaction for {str(item)}:\n```py\n{tb}\n```"
        # disable all components
        self._disable_all()
        # edit the message with the error message
        await self._edit(content=message, view=self)
        # stop the view
        self.stop()

    async def on_timeout(self) -> None:
        # disable all components
        self._disable_all()
        # edit the message with the new view
        await self._edit(content="Time out", view=self)

    async def on_stop_button(self) -> None:
        # disable all components
        self._disable_all()
        # edit the message with the new view
        await self._edit(content="Poll was stopped", view=self)
        self.stop()

class Polls(commands.Cog):
    poll_cmd = app_commands.Group(
        name='poll',
        description='Parent command for creating multiple choices and short answer polls'
    )

    def __init__(self, bot):
        self.bot = bot
        self.polls = []
        # self.bot.tree.add_command(self.ctx_menu)

    def find_last_poll(self, inter):
        if len(self.polls) > 100:
            self.polls = self.polls[10:]
        uc_id = get_unique_uc_id(inter) 
        logger.info(f"Search last poll from {uc_id}")
        for p in reversed(self.polls):
            if p.uc_id == uc_id:
                return p
        return None

    async def cog_unload(self):
        pass
        # self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def create_poll(self, inter, typ, question):

        poll = PollQuestion(question, typ, inter)

        self.polls.append(poll)

        # view = discord.ui.View(timeout=None)
        view = PollView(inter.user, poll, 600)

        async def callback(button_inter):
            choice = button_inter.data['custom_id']
            poll.add_answer(button_inter.user.id, choice)
            await button_inter.response.send_message(f'You chose **{choice}**', ephemeral=True)

        if typ == 0:
            for letter in 'ABCDE':
                button = discord.ui.Button(label=letter, custom_id=letter, style=discord.ButtonStyle.blurple)
                button.callback = callback
                view.add_item(button)

            title = 'Multiple Choices Poll'
        else:
            btn_answer = discord.ui.Button(
                label='Enter your answer',
                emoji='\U0001f4ac',
                style=discord.ButtonStyle.blurple
            )

            async def answer_callback(answer_inter):
                modal = AnswerForm(poll)
                await answer_inter.response.send_modal(modal)

            btn_answer.callback = answer_callback
            title = 'Short Answer Poll'
            view.add_item(btn_answer)

        # stop button
        async def stop_callback(stop_inter):
            if not stop_inter.user.guild_permissions.administrator:
                await stop_inter.response.send_message('No privilege.', ephemeral=True)
                return
            await view.on_stop_button()

        btn_stop = discord.ui.Button(
            label='Stop',
            emoji='\U0001f6d1',
            style=discord.ButtonStyle.red,
            row=1
        )

        btn_stop.callback = stop_callback

        view.add_item(btn_stop)

        # check responses
        async def check_callback(cb_inter):
            if not cb_inter.user.guild_permissions.administrator:
                await cb_inter.response.send_message('No privilege.', ephemeral=True)
                return
            await cb_inter.response.send_message(f"{str(len(poll.responses))} response(s).", ephemeral=True)
            return 

        btn_check = discord.ui.Button(
            label='Check Progress',
            emoji=None,
            style=discord.ButtonStyle.blurple,
            row=1
        )
        btn_check.callback = check_callback
        view.add_item(btn_check)

        embed = discord.Embed(
            title=title,
            description=question,
            color=0x2F3136
        ); 
        # .set_author( name=f'ID: {poll_id}')

        view.message = await inter.channel.send(embed=embed, view=view)

    @poll_cmd.command(name='multiplechoices')
    @app_commands.default_permissions()
    @app_commands.checks.has_permissions(administrator=True)
    async def multiplechoices(self, inter):
        """Creates a multiple-choice poll."""

        last = self.find_last_poll(inter)
        if last: 
            if last.isOpen():
                await inter.response.send_message('The previous poll is still open.', ephemeral=True)
                return
            question = last.question
        else:
            question = DEFAULT_QUESTION
        modal = QuestionForm(question)
        await inter.response.send_modal(modal)
        await modal.wait()
        question = str(modal.question)
        await self.create_poll(inter, 0, question)

    @poll_cmd.command(name="shortanswer")
    @app_commands.default_permissions()
    @app_commands.checks.has_permissions(administrator=True)
    async def shortanswer(self, inter):
        """Creates a poll that requires a self-written response."""

        last = self.find_last_poll(inter)
        if last: 
            if last.isOpen():
                await inter.response.send_message('The previous poll is still open.', ephemeral=True)
                return
            question = last.question
        else:
            question = DEFAULT_QUESTION
        modal = QuestionForm(question)
        await inter.response.send_modal(modal)
        await modal.wait()
        question = str(modal.question)
        await self.create_poll(inter, 1, question)

    @poll_cmd.command(name="results")
    @app_commands.default_permissions()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        keepprivate = 'do not send the results to everyone.'
    )
    async def results(self, inter, keepprivate: bool = False):
        """Show the result of the last poll"""
        last = self.find_last_poll(inter)
        if last is None:
            await inter.response.send_message('Did not find a poll.', ephemeral=True)
            return
        if last.isOpen():
            await inter.response.send_message('The last poll is still open.', ephemeral=True)
            return

        await display_results(inter, last, keepprivate) 
        # await inter.response.send_message('Not supported yet.', ephemeral=True)

    @poll_cmd.command(name="close")
    @app_commands.default_permissions()
    @app_commands.checks.has_permissions(administrator=True)
    async def close(self, inter):
        """Close the last poll"""
        last = self.find_last_poll(inter)
        if last is None:
            await inter.response.send_message('Did not find a poll.', ephemeral=True)
            return
        last.end()
        await inter.response.send_message('The last poll has been closed.', ephemeral=True)

    @poll_cmd.command(name="save")
    @app_commands.default_permissions()
    @app_commands.checks.has_permissions(administrator=True)
    async def save(self, inter):
        """Close the last poll"""
        filepath = Path(LOG_DIR).joinpath(get_unique_uc_id(inter))
        filepath.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        for p in [x for x in self.polls if (x.interaction.user.id == inter.user.id 
                and x.interaction.channel_id == inter.channel_id 
                and not x.open and not x.saved)] :
            count += p.save(filepath)
        await inter.response.send_message(f'{count} poll(s) saved.', ephemeral=True)

async def setup(bot):
    await bot.add_cog(Polls(bot))
