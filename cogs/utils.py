names = [
    'bar_left_empty',
    'bar_left_full',
    'bar_middle_empty',
    'bar_middle_full',
    'bar_right_empty',
    'bar_right_full'
]


def get_emojis(bot):
    guild = bot.guilds[0]

    for emoji in guild.emojis:
        if emoji.roles == [guild.self_role]:
            for name in names:
                if name in emoji.name:
                    setattr(bot, name, str(emoji))
                    break


def bar_from_p(bot, p):

    full = round(p / 10)
    bar = ''
    if full < 1:
        bar = bot.bar_left_empty + 8 * bot.bar_middle_empty + bot.bar_right_empty
    else:
        bar += bot.bar_left_full
        full -= 1
        if full > 8:
            bar += 8 * bot.bar_middle_full
        else:
            bar += full * bot.bar_middle_full + (8 - full) * bot.bar_middle_empty
        full -= 8
        if full > 0:
            bar += bot.bar_right_full
        else:
            bar += bot.bar_right_empty

    return bar
