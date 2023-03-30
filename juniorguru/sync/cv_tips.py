from datetime import timedelta
from textwrap import dedent

import emoji
from discord import ButtonStyle, Embed, ui

from juniorguru.cli.sync import main as cli
from juniorguru.lib import discord_sync, loggers
from juniorguru.lib.discord_club import (ClubChannelID, ClubMemberID,
                                         is_message_over_period_ago,)
from juniorguru.models.base import db
from juniorguru.models.club import ClubMessage
from juniorguru.lib.mutations import mutating_discord


logger = loggers.from_path(__file__)


@cli.sync_command(dependencies=['club-content'])
def main():
    discord_sync.run(discord_task)


@db.connection_context()
async def discord_task(client):
    last_message = ClubMessage.last_bot_message(ClubChannelID.CV_FEEDBACK, '💡')
    if is_message_over_period_ago(last_message, timedelta(days=30)):
        logger.info('Last message is more than one month old!')
        channel = await client.fetch_channel(ClubChannelID.CV_FEEDBACK)
        with mutating_discord(channel) as proxy:
            await proxy.purge(check=is_message_bot_reminder)
            await proxy.send(
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


def is_message_bot_reminder(message):
    return (message.author.id == ClubMemberID.BOT and
            message.content and
            emoji.is_emoji(message.content[0]))
