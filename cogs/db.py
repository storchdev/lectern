from discord.ext import commands
import aiosqlite3
from time import time
import random 
from config import DB_FILENAME


class NotFound(aiosqlite3.Error):
    pass


class StudentsRemaining(aiosqlite3.Error):
    pass


async def fetch_sections(bot):
    query = 'SELECT * FROM sections'
    return await bot.db_fetchall(query)


async def insert_section(bot, instructor_id, channel_id, role_id, name):
    query = 'INSERT INTO sections (instructor_id, channel_id, role_id, name) VALUES (?, ?, ?, ?)'
    await bot.db_execute(query, instructor_id, channel_id, role_id, name)


async def fetch_students(bot, section_id):
    query = 'SELECT * FROM students WHERE section_id = ?'
    return await bot.db_fetchall(query, section_id)


async def delete_section(bot, name):
    query = 'SELECT id FROM sections WHERE name = ?'
    row = await bot.db_fetchone(query, name)
    if not row:
        raise NotFound()

    query = 'SELECT id FROM students WHERE section_id = ?'
    row = await bot.db_fetchone(query, row[0])

    if row:
        raise StudentsRemaining()

    query = 'DELETE FROM sections WHERE name = ?'
    await bot.db_execute(query, name)


async def update_section(bot, old_name, new_name, channel, role):
    query = 'SELECT name, channel_id, role_id, id FROM sections WHERE name = ?'
    row = await bot.db_fetchone(query, old_name)

    if not row:
        raise NotFound()

    if new_name is None:
        new_name = row[0]

    if channel is None:
        channel_id = row[1]
    else:
        channel_id = channel.id

    if role is None:
        role_id = row[2]
    else:
        role_id = role.id

    query = 'UPDATE sections SET name = ?, channel_id = ?, role_id = ? WHERE id = ?'
    await bot.db_execute(query, new_name, channel_id, role_id, row[3])

    changes = {
        'name': (row[0], new_name),
        'channel': (row[1], channel_id),
        'role': (row[2], role_id)
    }
    return changes


async def insert_poll(bot, question, typ, duration, poll_id, points):
    if poll_id is None:
        poll_id = random.randint(1000000, 9999999)
    query = 'INSERT INTO polls (id, points, timestamp, question, type, duration) VALUES (?, ?, ?, ?, ?, ?)'
    await bot.db_execute(query, poll_id, points, int(time()), question, typ, duration)
    return poll_id


async def upsert_poll_response(bot, response, user_id, poll_id):
    response = response.lower()
    query = '''INSERT INTO responses (user_id, poll_id, response) 
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, poll_id)
               DO UPDATE SET response = ?
            '''
    await bot.db_execute(query, user_id, poll_id, response, response)


class DB(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.db = await aiosqlite3.connect(DB_FILENAME)

        async def db_fetchone(query, *args):
            async with self.bot.db.cursor() as cursor:
                await cursor.execute(query, args)
                return await cursor.fetchone()

        async def db_fetchall(query, *args):
            async with self.bot.db.cursor() as cursor:
                await cursor.execute(query, args)
                return await cursor.fetchall()

        async def db_execute(query, *args):
            async with self.bot.db.cursor() as cursor:
                await cursor.execute(query, args)
                await self.bot.db.commit()

        self.bot.db_fetchone = db_fetchone
        self.bot.db_fetchall = db_fetchall
        self.bot.db_execute = db_execute

        with open('cogs/query.sql') as f:
            for line in f.readlines():
                await self.bot.db_execute(line)


async def setup(bot):
    await bot.add_cog(DB(bot))
