from pathlib import Path

from discord import ButtonStyle, Color, Embed, NotFound, ui
from strictyaml import Bool, Int, Map, Optional, Seq, Str, Url, load

from juniorguru.cli.sync import main as cli
from juniorguru.lib import discord_sync, loggers
from juniorguru.lib.discord_club import (ClubChannel, delete_message, edit_message,
                                         send_message)
from juniorguru.models.base import db
from juniorguru.models.club import ClubMessage
from juniorguru.models.mentor import Mentor


MENTOR_EMOJI = '💁'

INFO_EMOJI = '💡'

DATA_PATH = Path(__file__).parent.parent / 'data' / 'mentors.yml'

SCHEMA = Seq(
    Map({
        'id': Int(),
        'name': Str(),
        Optional('company'): Str(),
        Optional('bio_url'): Url(),
        'topics': Str(),
        Optional('english_only', default=False): Bool(),
        Optional('book_url'): Url(),
    })
)


logger = loggers.from_path(__file__)


@cli.sync_command(dependencies=['club-content'])
def main():
    discord_sync.run(discord_task)


@db.connection_context()
async def discord_task(client):
    logger.info('Setting up db table')
    Mentor.drop_table()
    Mentor.create_table()

    logger.info('Parsing YAML')
    for yaml_record in load(DATA_PATH.read_text(), SCHEMA):
        Mentor.create(user=yaml_record.data['id'], **yaml_record.data)
    mentors = Mentor.listing()
    logger.debug(f'Loaded {len(mentors)} mentors from YAML')

    messages_trash = set(ClubMessage.channel_listing(ClubChannel.MENTORING))
    info_message = ClubMessage.last_bot_message(ClubChannel.MENTORING, INFO_EMOJI)
    discord_channel = await client.fetch_channel(ClubChannel.MENTORING)

    logger.info('Syncing mentors')
    for mentor in mentors:
        try:
            discord_member = await client.club_guild.fetch_member(mentor.user.id)
        except NotFound:
            logger.error(f"Not a member! #{mentor.id} ({mentor.name} from {mentor.company})")
            continue
        mentor_params = get_mentor_params(mentor, thumbnail_url=discord_member.display_avatar.url)

        message = ClubMessage.last_bot_message(ClubChannel.MENTORING, MENTOR_EMOJI, mentor.user.mention)
        if message:
            messages_trash.remove(message)
            logger.info(f"Editing existing message for mentor {mentor.name}")
            discord_message = await discord_channel.fetch_message(message.id)
            await edit_message(discord_message, **mentor_params)
            mentor.message_url = message.url
            mentor.save()
        else:
            logger.info(f"Creating a new message for mentor {mentor.name}")
            if info_message:
                logger.info("Deleting info message")
                messages_trash.remove(info_message)
                info_discord_message = await discord_channel.fetch_message(info_message.id)
                await delete_message(info_discord_message)
                info_message.delete_instance()
                info_message = None
            discord_message = await send_message(discord_channel, **mentor_params)
            mentor.message_url = discord_message.jump_url
            mentor.save()

    logger.info('Syncing info')
    info_content = f'{INFO_EMOJI} Co to tady je? Jak to funguje?'
    info_mentee_description = ('Pomohlo by ti pravidelně si s někým na hodinku zavolat a probrat svůj postup? '
                               'Předchozí zprávy v tomto kanálu představují seznam **mentorů**, kteří se k takové pomoci nabídli. '
                               'Postupuj následovně:\n'
                               '\n'
                               '1️⃣ 🧭 Stanov si dlouhodobější cíl (např. porozumět API)\n'
                               '2️⃣ 👋 Podle tématu si vyber mentorku/mentora a rezervuj si čas na videohovor\n'
                               '3️⃣ 🤝 Domluvte se, jak často si budete volat (např. každé dva týdny, půl roku)\n'
                               '4️⃣ 📝 Rezervuj jednotlivé schůzky a předem měj jasno, co na nich chceš řešit\n'
                               '5️⃣ 🚀 Mentor ti pomáhá dosáhnout cíle. Radí a posouvá tě správným směrem\n'
                               '\n'
                               '❤️ Mentoři jsou dobrovolníci, ne placení učitelé. Aktivita je na tvé straně. Važ si jejich času a dopřej jim dobrý pocit, pokud pomohli.\n')
    info_mentor_description = ('🦸 I ty můžeš mentorovat! '
                               'Nemusíš mít 10 let zkušeností v oboru. '
                               'Pusť si [přednášku o mentoringu](https://www.youtube.com/watch?v=8xeX7wfX_x4) od Anny Ossowski, ať víš, co od toho čekat. '
                               'Existuje i [přepis](https://github.com/honzajavorek/become-mentor/blob/master/README.md) a [český překlad](https://github.com/honzajavorek/become-mentor/blob/master/cs.md). '
                               'Potom napiš Honzovi, přidá tě do [seznamu](https://github.com/honzajavorek/junior.guru/blob/main/juniorguru/data/mentors.yml).')
    info_params = dict(content=info_content,
                       embeds=[Embed(title='Mentoring', color=Color.orange(),
                                     description=info_mentee_description),
                               Embed(description=info_mentor_description)])
    if info_message:
        messages_trash.remove(info_message)
        logger.info("Editing info message")
        discord_message = await discord_channel.fetch_message(info_message.id)
        await edit_message(discord_message, **info_params)
    else:
        logger.info("Creating new info message")
        await send_message(discord_channel, **info_params)

    logger.info('Deleting extraneous messages')
    for message in messages_trash:
        logger.debug(f'Deleting message #{message.id}: {message.content[:10]}…')
        try:
            discord_message = await discord_channel.fetch_message(message.id)
            await delete_message(discord_message)
            message.delete_instance()
        except:
            logger.error(f'Could not delete message #{message.id}: {message.content[:10]}…')
            raise


def get_mentor_params(mentor, thumbnail_url=None):
    content = f'{MENTOR_EMOJI} {mentor.user.mention}'
    if mentor.company:
        content += f' ({mentor.company})'

    description = ''
    if mentor.english_only:
        description += "🇬🇧 Pouze anglicky!\n"
    description += f"📖 {mentor.topics}\n"

    buttons = []
    if mentor.bio_url:
        buttons.append(ui.Button(emoji='👋',
                                 label='Představení',
                                 url=mentor.bio_url,
                                 style=ButtonStyle.secondary))
    if mentor.book_url:
        buttons.append(ui.Button(emoji='🗓',
                                 label='Rezervuj',
                                 url=mentor.book_url,
                                 style=ButtonStyle.secondary))
    else:
        buttons.append(ui.Button(emoji='<:discord:935790609023787018>',
                                 label='(Piš přímo přes Discord)',
                                 style=ButtonStyle.secondary,
                                 disabled=True))

    discord_embed = Embed(description=description)
    if thumbnail_url:
        discord_embed.set_thumbnail(url=thumbnail_url)

    return dict(content=content, embed=discord_embed, view=ui.View(*buttons))
