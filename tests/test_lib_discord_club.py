from collections import namedtuple
from datetime import date, datetime, timedelta

import pytest
from discord import ChannelType

from juniorguru.lib import discord_club


StubEmoji = namedtuple('Emoji', ['name'])

StubUser = namedtuple('User', ['id'])

StubMember = namedtuple('Member', ['id', 'roles'],
                        defaults=dict(roles=[]))

StubRole = namedtuple('Role', ['id'])

StubMessage = namedtuple('Message', ['author', 'content'])

StubClubMessage = namedtuple('ClubMessage', ['created_at'])


@pytest.mark.parametrize('emoji, expected', [
    ('🆗', '🆗'),
    ('AHOJ', 'AHOJ'),
    (StubEmoji('lolpain'), 'lolpain'),
    (StubEmoji('BabyYoda'), 'babyyoda'),
    ('👋🏻', '👋'),
])
def test_emoji_name(emoji, expected):
    assert discord_club.emoji_name(emoji) == expected


@pytest.mark.parametrize('text, expected', [
    pytest.param('', None, id='empty'),
    pytest.param('😀', '😀', id='emoji'),
    pytest.param('😀 blah blah blah', '😀', id='emoji with text'),
    pytest.param('👨‍👩‍👦 blah blah blah', '👨‍👩‍👦', id='multi-byte emoji with text'),
    pytest.param('     😀', '😀', id='emoji with spaces'),
    pytest.param('<:discordthread:993580255287705681>', '<:discordthread:993580255287705681>', id='custom emoji'),
    pytest.param('<:discordthread:993580255287705681> blah blah blah', '<:discordthread:993580255287705681>', id='custom emoji with text'),
    pytest.param('    <:discordthread:993580255287705681>', '<:discordthread:993580255287705681>', id='custom emoji with spaces'),
])
def test_get_starting_emoji(text, expected):
    assert discord_club.get_starting_emoji(text) == expected


@pytest.mark.parametrize('member_or_user, expected', [
    (StubUser(1), []),
    (StubMember(1, [StubRole(42), StubRole(38)]), [42, 38]),
])
def test_get_roles(member_or_user, expected):
    assert discord_club.get_roles(member_or_user) == expected


@pytest.mark.parametrize('date_, expected', [
    (date(2022, 1, 24), False),
    (date(2022, 1, 25), True),
    (date(2022, 1, 26), True),
])
def test_is_message_older_than(date_, expected):
    created_at = datetime.utcnow().replace(2022, 1, 25)
    message = StubClubMessage(created_at)

    assert discord_club.is_message_older_than(message, date_) is expected


def test_is_message_older_than_no_message():
    assert discord_club.is_message_older_than(None, date(2022, 1, 25)) is True


@pytest.mark.parametrize('today, expected', [
    (date(2022, 1, 24), False),
    (date(2022, 1, 25), True),
    (date(2022, 1, 26), True),
])
def test_is_message_over_period_ago(today, expected):
    created_at = datetime.utcnow().replace(2022, 1, 18)
    message = StubClubMessage(created_at)

    assert discord_club.is_message_over_period_ago(message, timedelta(weeks=1), today) is expected


@pytest.mark.parametrize('link_text', [
    'Celý příspěvek',
    'Hop na příspěvek',
])
def test_get_pinned_message_url(link_text):
    StubEmbed = namedtuple('Embed', ['description'])
    StubChannel = namedtuple('Channel', ['type'])
    StubMessage = namedtuple('Message', ['content', 'embeds', 'channel'])

    description = ('**Dan Srb** v kanálu „ITnetwork informační hodnota kurzů”:'
                   '\n> Zjistit se to dá z Excelového souboru tady https://www.msmt.cz/vzdelavani/dalsi-vzdelavani/databaze a '
                   'řetězec SDA se v něm vůbec nevyskytuje, takže to nevypadá, že akreditaci mají. Za loňsko byly uděleny tyto '
                   'akreditace, kde je nějaké programování. ``` Číslo jednací Vzdělávací zařízení Email žadatele Pro pracovní '
                   'činnost MSMT-16743/2022-6 b4u consulting s.r.o. t.kosina@consultant.com Programátor www aplikací '
                   'MSMT-6316/2022-2 Edu partners s.r.o. info@edu-partners.cz Programátor www aplikací…'
                   f'\n[{link_text}](https://discord.com/channels/769966886598737931/1083734944121102436/1089250472776454154)')
    message = StubMessage('📌 ...',
                          [StubEmbed(description)],
                          StubChannel(type=ChannelType.private))

    assert discord_club.get_pinned_message_url(message) == 'https://discord.com/channels/769966886598737931/1083734944121102436/1089250472776454154'


@pytest.mark.parametrize('url, expected', [
    ('https://discord.com/channels/769966886598737931/1083734944121102436/1089250472776454154',
     {'guild_id': 769966886598737931, 'channel_id': 1083734944121102436, 'message_id': 1089250472776454154}),
    ('https://discord.com/channels/@me/834779122256576522/968729020357296139',
     {'guild_id': None, 'channel_id': 834779122256576522, 'message_id': 968729020357296139}),
])
def test_parse_message_url(url, expected):
    assert discord_club.parse_message_url(url) == expected
