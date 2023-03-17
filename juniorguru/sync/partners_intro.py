import asyncio
from datetime import date, timedelta
from pathlib import Path
from textwrap import dedent

from discord import ButtonStyle, Color, Embed, File, ui
from jinja2 import Template

from juniorguru.cli.sync import main as cli
from juniorguru.lib import loggers
from juniorguru.lib.discord_club import (DISCORD_MUTATIONS_ENABLED, ClubChannel,
                                         ClubEmoji, is_message_over_period_ago)
from juniorguru.lib import discord_sync
from juniorguru.models.base import db
from juniorguru.models.club import ClubMessage
from juniorguru.models.partner import Partner


BOT_REACTIONS = ['👋', '👍', '💕', '💰', '🎉']

IMAGES_DIR = Path(__file__).parent.parent / 'images'

DESCRIPTION_TEMPLATE = dedent('''
    {%- set partnership = partner.active_partnership() -%}
    **Tarif „{{ partnership.plan.name }}” {% for _ in range(partnership.plan.hierarchy_rank + 1) %}:star:{% endfor %}**

    {% for benefit in partnership.evaluate_benefits() -%}
    {{ benefit.text }}
    {% endfor %}
    {%- if partnership.student_role_id %}Posílají sem své studenty: <@&{{ partner.student_role_id }}>
    {% endif %}
    {%- if partnership.agreements_registry|length %}A ještě nějaká [další ujednání](https://junior.guru/open/{{ partner.slug }}#dalsi-ujednani)
    {% endif %}
    {% if partner.is_course_provider -%}
    ℹ️ Partnerství neznamená, že junior.guru doporučuje konkrétní kurzy, nebo že na ně nemáš psát recenze v klubu.
    {%- endif %}
''')


logger = loggers.from_path(__file__)


@cli.sync_command(dependencies=['club-content', 'partners', 'roles'])
def main():
    run_discord_task('juniorguru.sync.partners_intro.discord_task')


@db.connection_context()
async def discord_task(client):
    last_message = ClubMessage.last_bot_message(ClubChannel.INTRO, ClubEmoji.PARTNER_INTRO)
    if is_message_over_period_ago(last_message, timedelta(weeks=1)):
        logger.info('Last partner intro message is more than one week old!')

        partners = [partner for partner in Partner.active_listing()
                    if is_message_over_period_ago(partner.intro, timedelta(days=365))]
        if partners:
            logger.debug(f'Choosing from {len(partners)} partners to announce')
            partner = sorted(partners, key=sort_key)[0]
            logger.debug(f'Decided to announce {partner!r}')
            template = Template(DESCRIPTION_TEMPLATE)
            description = template.render(partner=partner)
            content = (
                f"{ClubEmoji.PARTNER_INTRO} Partnerství! "
                f"Firma {partner.name_markdown_bold} chce pomáhat juniorům. "
                f"Členové, které sem pošle, mají roli <@&{partner.role_id}> (aktuálně {len(partner.list_members)})."
            )
            embed = Embed(title=partner.name,
                          color=Color.dark_grey(),
                          description=description)
            embed.set_thumbnail(url=f"attachment://{Path(partner.poster_path).name}")
            file = File(IMAGES_DIR / partner.poster_path)
            buttons = [
                ui.Button(emoji='👉',
                          label=partner.name,
                          url=partner.url,
                          style=ButtonStyle.secondary),
                ui.Button(emoji='👀',
                          label='Detaily partnerství',
                          url=f'https://junior.guru/open/{partner.slug}',
                          style=ButtonStyle.secondary)
            ]
            if DISCORD_MUTATIONS_ENABLED:
                channel = await client.fetch_channel(ClubChannel.INTRO)
                message = await channel.send(content=content, embed=embed, file=file, view=ui.View(*buttons))
                await asyncio.gather(*[message.add_reaction(emoji) for emoji in BOT_REACTIONS])
            else:
                logger.warning('Discord mutations not enabled')
        else:
            logger.info('No partners to announce')
    else:
        logger.info('Last partner intro message is less than one week old')


def sort_key(partner, today=None):
    today = today or date.today()
    partnership = partner.active_partnership()
    expires_on = (partnership.expires_on or date(3000, 1, 1))
    expires_in_days = (expires_on - today).days
    started_days_ago = (today - partnership.starts_on).days
    return (expires_in_days if expires_in_days <= 30 else 1000,
            started_days_ago,
            partner.name)
