import asyncio
from datetime import datetime, timedelta

import discord
from discord import Client, MessageType, TextChannel
from juniorguru_chick.bot import (GREETER_ROLE_ID, INTRO_THREAD_NAME_TEMPLATE,
                                  add_members_with_role, create_thread,
                                  ensure_thread_name, is_thread_created)
from juniorguru_chick.intro_emojis import choose_intro_emojis

from juniorguru.cli.sync import main as cli
from juniorguru.lib import discord_sync, loggers, mutations
from juniorguru.lib.discord_club import (ClubChannelID, ClubMemberID, add_reactions,
                                         get_missing_reactions)
from juniorguru.lib.mutations import mutating_discord
from juniorguru.models.base import db
from juniorguru.models.club import ClubMessage


WELCOME_BACK_REACTIONS = ['👋', '🔄', '<:meowsheart:1002448596572061746>']

PROCESS_HISTORY_SINCE = timedelta(days=30)

THREADS_STARTING_AT = datetime(2022, 7, 17, 0, 0)

GREETERS_LIMIT = 5

PURGE_SAFETY_LIMIT = 20

# WELCOME_MESSAGE_PREFIXES = [
#     'Vítej!',
#     'Vítej v klubu!',
#     'Vítám tě v klubu!',
#     'Vítám tě mezi námi!',
#     'Vítej mezi námi!',
#     'Čau!',
#     'Čáááu!',
#     'Ahoj!',
#     'Ahój!',
#     'Nazdar!',
#     'Nazdááár!',
# ]


logger = loggers.from_path(__file__)


@cli.sync_command(dependencies=['club-content'])
def main():
    discord_sync.run(discord_task)


@db.connection_context()
async def discord_task(client: Client):
    discord_channel = await client.club_guild.fetch_channel(ClubChannelID.INTRO)

    logger.info('Processing messages')
    since_at = datetime.utcnow() - PROCESS_HISTORY_SINCE
    tasks = []
    for message in ClubMessage.channel_listing_since(ClubChannelID.INTRO, since_at):
        tasks.append(asyncio.create_task(process_message(discord_channel, message)))

    logger.info('Purging system messages about created threads')
    with mutating_discord(discord_channel) as proxy:
        await proxy.purge(check=is_thread_created, limit=PURGE_SAFETY_LIMIT, after=THREADS_STARTING_AT)

    logger.info('Waiting until all messages are processed')
    await asyncio.gather(*tasks)


async def process_message(discord_channel: TextChannel, message: ClubMessage):
    if message.type == 'default' and message.is_intro:
        logger.info(f'Welcoming member #{message.author.id}')
        await welcome(discord_channel, message)
    elif message.type == 'new_member' and message.author.first_seen_on() < message.created_at.date():
        logger.info(f'Welcoming back member #{message.author.id}')
        await welcome_back(discord_channel, message)


@mutations.mutates_discord()
async def welcome(discord_channel: TextChannel, message: ClubMessage):
    logger.debug(f"Welcoming {message.author.display_name!r} with emojis")

    if message.created_at < THREADS_STARTING_AT:
        logger.warning("The message is from before threads were introduced, skipping")
        return

    logger.debug(f"Ensuring emojis for {message.author.display_name!r}")
    discord_message = await discord_channel.fetch_message(message.id)
    emojis = choose_intro_emojis(message.content)
    missing_emojis = get_missing_reactions(discord_message.reactions, emojis)
    logger.debug(f"Reacting to {message.author.display_name!r} with {emojis!r}")
    await add_reactions(discord_message, missing_emojis)

    logger.debug(f"Ensuring thread for {message.author.display_name!r}")
    if discord_message.flags.has_thread:
        logger.debug(f"Thread for {message.author.display_name!r} already exists")
        thread = await discord_message.guild.fetch_channel(message.id)
    else:
        logger.debug(f"Creating thread for {message.author.display_name!r}")
        thread = await create_thread(discord_message, INTRO_THREAD_NAME_TEMPLATE)

    if thread.archived or thread.locked:
        logger.debug(f"Thread for {message.author.display_name!r} is archived or locked, skipping")
        return

    logger.debug(f"Ensuring correct thread name for {message.author.display_name!r}")
    await ensure_thread_name(thread, INTRO_THREAD_NAME_TEMPLATE)

    logger.debug(f"Analyzing if greeters are involved for {message.author.display_name!r}")
    thread_members = thread.members or await thread.fetch_members()
    if len(thread_members) < GREETERS_LIMIT:
        await add_members_with_role(thread, GREETER_ROLE_ID)

    # TODO https://github.com/juniorguru/juniorguru-chick/issues/11
    # discord_messages = [discord_message async for discord_message in thread.history(limit=None)]
    # logger.debug(f"Ensuring welcome message for '{message.author.display_name}'")
    # content_prefix = random.choice(WELCOME_MESSAGE_PREFIXES)
    # content = (f'{content_prefix} '
    #             'Dík, že se představuješ ostatním, protože to fakt hodně pomáhá v tom, aby šlo pochopit tvou konkrétní situaci. '
    #             'Takhle ti můžeme dávat rady na míru, a ne jenom nějaká obecná doporučení <:meowthumbsup:842730599906279494>\n\n'
    #             'Potřebuješ pošťouchnout s kariérním rozhodnutím? Pojď to probrat do <#788826407412170752>. '
    #             'Vybíráš kurz? Napiš do <#1075052469303906335>. Hledáš konkrétní recenze? Zkus vyhledávání. '
    #             'Něco jiného? <#769966887055392768> snese cokoliv 💬\n\n'
    #             'Na https://junior.guru/handbook/ najdeš příručku s radami pro všechny, '
    #             'kdo se chtějí naučit programovat a najít si práci v oboru. Hodně věcí je už zodpovězeno v ní, tak si ji nezapomeň projít 📖\n\n'
    #             'Příručka začíná popisem **osvědčené cesty juniora**, která má **10 fází** 🥚 🐣 🐥 '
    #             'Jaké z těch fází se tě zrovna teď týkají? Zaklikni čísla pod touto zprávou ⬇️')
    # logger.debug(f"Welcome message content: {content!r}")
    # try:
    #     welcome_discord_message = list(filter(is_welcome_message, discord_messages))[0]
    #     logger.debug(f"Welcome message already exists, updating: #{welcome_discord_message.id}")
    #     if welcome_discord_message.embeds or welcome_discord_message.content != content:
    #         with mutating_discord(welcome_discord_message) as proxy:
    #             await proxy.edit(content=content, suppress=True)
    # except IndexError:
    #     logger.debug("Sending welcome message")
    #     with mutating_discord(thread) as proxy:
    #         welcome_discord_message = await proxy.send(content=content, suppress=True)


async def welcome_back(discord_channel: TextChannel, message: ClubMessage):
    discord_message = await discord_channel.fetch_message(message.id)
    missing_emojis = get_missing_reactions(discord_message.reactions, WELCOME_BACK_REACTIONS)
    logger.debug(f"Welcoming back {message.author.display_name!r} with emojis {missing_emojis!r}")
    await add_reactions(discord_message, missing_emojis)


def is_welcome_message(discord_message: discord.Message) -> bool:
    return discord_message.type == MessageType.default and discord_message.author.id == ClubMemberID.BOT
