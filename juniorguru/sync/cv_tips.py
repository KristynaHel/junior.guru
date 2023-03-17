from datetime import timedelta
from textwrap import dedent

import emoji
from discord import ButtonStyle, Embed, ui

from juniorguru.cli.sync import main as cli
from juniorguru.lib import loggers
from juniorguru.lib.discord_club import (DISCORD_MUTATIONS_ENABLED, ClubChannel,
                                         ClubMember, is_message_over_period_ago)
from juniorguru.lib.discord_proc import run_discord_task
from juniorguru.models.base import db
from juniorguru.models.club import ClubMessage


logger = loggers.from_path(__file__)


@cli.sync_command(dependencies=['club-content'])
def main():
    run_discord_task('juniorguru.sync.cv_group.discord_task')


@db.connection_context()
async def discord_task(client):
    last_message = ClubMessage.last_bot_message(ClubChannel.CV_FEEDBACK, '💡')
    if is_message_over_period_ago(last_message, timedelta(days=30)):
        logger.info('Last message is more than one month old!')
        if DISCORD_MUTATIONS_ENABLED:
            channel = await client.fetch_channel(ClubChannel.CV_FEEDBACK)
            await channel.purge(check=is_message_bot_reminder)
            await channel.send(
                content='💡 Jsem tady zas se svou pravidelnou dávkou užitečných tipů!',
                embeds=[
                    Embed(
                        title='📋 Návod na CV',
                        description=dedent('''
                            Než nás poprosíš o zpětnou vazbu na svoje CV, přečti si [návod v příručce](https://junior.guru/handbook/cv/). Ušetříš čas sobě i nám! Ve zpětné vazbě nebudeme muset opakovat rady z návodu a budeme se moci soustředit na to podstatné.
                        ''')
                    ),
                    Embed(
                        title='<:github:842685206095724554> Návod na GitHub',
                        description=dedent('''
                            K čemu slouží GitHub a jak si tam vyladit svůj profil? Přečti si [návod v příručce](https://junior.guru/handbook/git/). Akorát… Honza ho pořád ještě nedopsal. Šťouchni do něj, že si to chceš přečíst! Čím víc šťouchů, tím víc bude mít motivace kapitolu dokončit.
                        ''')
                    ),
                    Embed(
                        title='<:linkedin:915267970752712734> LinkedIn skupina',
                        description=dedent('''
                            Přidej se do [naší skupiny](https://www.linkedin.com/groups/13988090/), díky které se pak můžeš snadno propojit s ostatními členy (a oni s tebou). Zároveň se ti bude logo junior.guru zobrazovat na profilu v sekci „zájmy”. Nevíme, jestli ti to přidá nějaký kredit u recruiterů, ale vyloučeno to není!
                        ''')
                    ),
                ],
                view=ui.View(ui.Button(emoji='📋',
                                       label='Návod na CV',
                                       url='https://junior.guru/handbook/cv/',
                                       style=ButtonStyle.secondary),
                             ui.Button(emoji='<:github:842685206095724554>',
                                       label='Návod na GitHub',
                                       url='https://junior.guru/handbook/git/',
                                       style=ButtonStyle.secondary),
                             ui.Button(emoji='<:linkedin:915267970752712734>',
                                       label='LinkedIn skupina',
                                       url='https://www.linkedin.com/groups/13988090/',
                                       style=ButtonStyle.secondary))
            )
        else:
            logger.warning('Discord mutations not enabled')


def is_message_bot_reminder(message):
    return (message.author.id == ClubMember.BOT and
            message.content and
            emoji.is_emoji(message.content[0]))
