import itertools
from datetime import date
from operator import attrgetter
from textwrap import dedent

import feedparser
import requests
from discord import Color, Embed

from juniorguru.cli.sync import main as cli
from juniorguru.lib import loggers
from juniorguru.lib.discord_club import DISCORD_MUTATIONS_ENABLED, ClubChannel
from juniorguru.lib import discord_sync
from juniorguru.models.base import db
from juniorguru.models.club import (ClubDocumentedRole, ClubMessage,
                                    ClubSubscribedPeriod, ClubUser)
from juniorguru.models.event import Event
from juniorguru.models.partner import Partner


TODAY = date.today()

BLOG_RSS_URL = 'https://honzajavorek.cz/feed.xml'

BLOG_WEEKNOTES_PREFIX = 'Týdenní poznámky'

EVENTS_LIMIT = 10


logger = loggers.from_path(__file__)


@cli.sync_command(dependencies=['club-content',
                                'partners',
                                'events',
                                'subscriptions',
                                'roles'])
def main():
    discord_sync.run(discord_task)


@db.connection_context()
async def discord_task(client):
    discord_channel = await client.fetch_channel(ClubChannel.DASHBOARD)

    sections = [
        render_basic_tips(),
        render_roles(),
        render_partners(),
        render_events(),
        render_open(),
    ]
    messages = sorted(ClubMessage.channel_listing_bot(ClubChannel.DASHBOARD),
                      key=attrgetter('created_at'))

    if len(messages) != len(sections):
        logger.warning('The scheme of sections seems to be different, purging the channel and creating new messages')
        if DISCORD_MUTATIONS_ENABLED:
            await discord_channel.purge()
            for section in sections:
                await discord_channel.send(embed=Embed(**section))
        else:
            logger.warning('Discord mutations not enabled')
    else:
        logger.info("Editing existing dashboard messages")
        if DISCORD_MUTATIONS_ENABLED:
            for i, message in enumerate(messages):
                discord_message = await discord_channel.fetch_message(message.id)
                await discord_message.edit(embed=Embed(**sections[i]))
        else:
            logger.warning('Discord mutations not enabled')


def render_basic_tips():
    return {
        'title': 'Základní tipy',
        'color': Color.yellow(),
        'description': dedent('''
            Klub je místo, kde můžeš spolu s ostatními posunout svůj rozvoj v oblasti programování, nebo s tím pomoci ostatním.

            👋 Tykáme si, ⚠️ [Pravidla chování](https://junior.guru/coc/), 💳 [Nastavení placení](https://juniorguru.memberful.com/account), 🤔 [Časté dotazy](https://junior.guru/faq/)
        ''').strip()
    }


def render_roles():
    return {
        'title': 'Role',
        'description': '\n'.join([
            f'{format_role(role)}\n' for role
            in ClubDocumentedRole.listing()

        ])
    }


def format_role(role):
    text = f'**{role.mention}**'
    if role.emoji:
        text += f' {role.emoji}'
    text += f'\n{role.description}'
    return text


def render_partners():
    return {
        'title': 'Partneři',
        'color': Color.dark_grey(),
        'description': 'Následující firmy se podílejí na financování provozu junior.guru. Někdy sem pošlou své lidi. Ti pak mají roli <@&837316268142493736> a k tomu ještě i roli vždy pro konkrétní firmu, například <@&938306918097747968>.\n\n' + ', '.join([
            f'✨ [{partner.name}]({partner.url})' for partner
            in Partner.active_listing()
        ])
    }


def render_events():
    events = Event.listing()
    description = f'Odkazy na posledních {EVENTS_LIMIT} záznamů, ať je máš víc po ruce:\n\n'
    description += '\n'.join([
        format_event(event)
        for event in itertools.islice(events, EVENTS_LIMIT)
        if event.recording_url
    ])
    description += f'\nDalších {len(events) - EVENTS_LIMIT} akcí je [na webu](https://junior.guru/events/).'
    return {
        'title': 'Záznamy klubových akcí',
        'description': description,
    }


def format_event(event):
    return (
        f'📺 [{event.title}]({event.recording_url})\n'
        f'{event.start_at.date():%-d.%-m.%Y}, {event.bio_name}\n'
    )


def render_open():
    members_total_count = ClubUser.members_count()
    members_women_ptc = ClubSubscribedPeriod.women_ptc(TODAY)

    response = requests.get(BLOG_RSS_URL)
    response.raise_for_status()
    blog_entries = [entry for entry in feedparser.parse(response.content).entries
                    if entry.title.startswith(BLOG_WEEKNOTES_PREFIX)]
    blog_entries = sorted(blog_entries, key=attrgetter('published'), reverse=True)
    last_blog_entry = blog_entries[0]

    description = ', '.join([
        f'🙋 {members_total_count} členů v klubu, z toho asi {members_women_ptc} % žen',
        f'📝 [{last_blog_entry.title}]({last_blog_entry.link})',
        '📊 [Návštěvnost webu](https://simpleanalytics.com/junior.guru)',
        '<:github:842685206095724554> [Zdrojový kód](https://github.com/honzajavorek/junior.guru)',
        '📈 [Další čísla a grafy](https://junior.guru/open/)',
    ])
    description += '\n\n💡 Napadá tě vylepšení? Máš dotaz k fungování klubu? Šup s tím do <#806215364379148348>!'

    return {
        'title': 'Zákulisí junior.guru',
        'color': Color.greyple(),
        'description': description
    }
