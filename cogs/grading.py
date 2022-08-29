from discord.ext import commands
from discord import app_commands
import discord
import re 
import json
from cogs.utils import bar_from_p

    
async def insertgrades(bot, message, poll_id, inter, answers):
    answers = [a.lower() for a in answers]

    embed = message.embeds[0]

    answerdict = {}

    query = 'UPDATE polls SET answers = ? WHERE id = ?'
    await bot.db_execute(query, json.dumps(answers), poll_id)

    query = 'SELECT id, response FROM responses WHERE poll_id = ?'
    rows = await bot.db_fetchall(query, poll_id)

    correct = 0
    query = 'UPDATE responses SET correct = ? WHERE poll_id = ?'
    for row in rows:
        answer = row[1].lower()

        if answer in answerdict:
            answerdict[answer] += 1
        else:
            answerdict[answer] = 1
        
        if answer in answers:
            correct += 1
            iscorrect = 1 
        else:
            iscorrect = 0 
        await bot.db_execute(query, iscorrect, row[0])
    
    answers = {k: v for k, v in sorted(answerdict.items(), key=lambda item: item[1], reverse=True)}
    total = sum(list(answers.values()))

    embed.clear_fields()
    for i in range(5):
        try:
            choice = list(answers.keys())[i]
        except IndexError:
            break 

        p = round(answers[choice]/total*100) if total != 0 else 0
        bar = bar_from_p(bot, p)

        embed.add_field(
            name=choice,
            value=f'{bar}  **{p}%**',
            inline=False
        )
    
    embed.set_footer(text=f'{total} responses')

    await message.edit(embed=embed)

    await inter.response.send_message(
        f'Graded Poll #{poll_id}\n{correct}/{len(rows)} correct responses',
        ephemeral=True
    )


class Grading(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name='Grade this poll',
            callback=self.grade
        )
        self.bot.tree.add_command(self.ctx_menu)
    
    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @app_commands.default_permissions()
    @app_commands.checks.has_permissions(administrator=True)
    async def grade(self, inter, message: discord.Message):
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
        query = 'SELECT type, question FROM polls WHERE id = ?'
        poll = await self.bot.db_fetchone(query, poll_id)
        written = poll[0]
        question = poll[1]

        if written:
            
            class GradeWA(discord.ui.Modal, title=f'Grading Written Answer Poll #{poll_id}'):
                answers = discord.ui.TextInput(
                    label='Enter the correct answer(s), 1 per line', 
                    style=discord.TextStyle.long
                )
                
                async def on_submit(self, minter):
                    answers = str(self.answers).split('\n')
                    await insertgrades(minter.client, message, poll_id, minter, answers)

            await inter.response.send_modal(GradeWA())
        
        else:
            view = discord.ui.View()

            async def on_click(binter):
                answers = [binter.data['custom_id']]
                await insertgrades(self.bot, message, poll_id, binter, answers)
                for item in view.children:
                    if item.custom_id == answers[0]:
                        item.style = discord.ButtonStyle.green 
                        view.stop()
                        break 

            for label in 'ABCDE':
                b = discord.ui.Button(label=label, custom_id=label)
                b.callback = on_click 
                view.add_item(b)
            
            await inter.response.send_message(
                f'Choose the correct answer for:\n```{question}```',
                view=view,
                ephemeral=True
            )

            await view.wait()
            for item in view.children:
                item.disabled = True 

            await inter.edit_original_response(view=view)


async def setup(bot):
    await bot.add_cog(Grading(bot))
