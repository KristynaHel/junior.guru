import asyncio
from functools import partial, wraps

import arrow
import peewee
from discord import ChannelType, DMChannel, Member, User, Message
from discord.abc import GuildChannel

from juniorguru.lib import loggers
from juniorguru.lib.discord_club import (ClubMember, emoji_name, get_channel_name, get_parent_channel_id,
                                         get_roles)
from juniorguru.lib.discord_votes import count_downvotes, count_upvotes
from juniorguru.models.base import db
from juniorguru.models.club import ClubMessage, ClubPinReaction, ClubUser


logger = loggers.from_path(__file__)


def make_async(fn):
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))
    return wrapper


@make_async
@db.connection_context()
def store_member(member: Member) -> ClubUser:
    """Stores in database given Discord Member object"""
    logger['users'][member.id].debug(f'Saving {member.display_name!r}')
    return ClubUser.create(id=member.id,
                           is_bot=member.bot,
                           is_member=True,
                           has_avatar=bool(member.avatar),
                           display_name=member.display_name,
                           mention=member.mention,
                           tag=f'{member.name}#{member.discriminator}',
                           joined_at=arrow.get(member.joined_at).naive,
                           initial_roles=get_roles(member))


@db.connection_context()
def _store_user(user: User) -> ClubUser:
    """
    Stores in database given Discord User object

    If given user is already stored, it silently returns the existing database object.

    The message.author can be an instance of Member, but it can also be an instance of User,
    if the author isn't a member of the Discord guild/server anymore. User instances don't
    have certain properties, hence the getattr() calls.
    """
    logger['users'][user.id].debug(f'Saving {user.display_name!r}')
    try:
        obj = ClubUser.create(id=user.id,
                              is_bot=user.bot,
                              is_member=bool(getattr(user, 'joined_at', False)),
                              has_avatar=bool(user.avatar),
                              display_name=user.display_name,
                              mention=user.mention,
                              tag=f'{user.name}#{user.discriminator}',
                              joined_at=(arrow.get(user.joined_at).naive if hasattr(user, 'joined_at') else None),
                              initial_roles=get_roles(user))
        logger['users'][user.id].debug(f'Saved {user.display_name!r} as {obj!r}')
        return obj
    except peewee.IntegrityError:
        obj = ClubUser.get(id=user.id)
        logger['users'][user.id].debug(f'Found {user.display_name!r} as {obj!r}')
        return obj


@make_async
@db.connection_context()
def store_message(message: Message, channel: GuildChannel | DMChannel) -> ClubMessage:
    """Stores in database given Discord Message object"""
    return ClubMessage.create(id=message.id,
                              url=message.jump_url,
                              content=message.content,
                              content_size=len(message.content or ''),
                              reactions={emoji_name(reaction.emoji): reaction.count for reaction in message.reactions},
                              upvotes_count=count_upvotes(message.reactions),
                              downvotes_count=count_downvotes(message.reactions),
                              created_at=arrow.get(message.created_at).naive,
                              created_month=f'{message.created_at:%Y-%m}',
                              edited_at=(arrow.get(message.edited_at).naive if message.edited_at else None),
                              author=_store_user(message.author),
                              author_is_bot=message.author.id == ClubMember.BOT,
                              channel_id=channel.id,
                              channel_name=get_channel_name(channel),
                              parent_channel_id=get_parent_channel_id(channel),
                              category_id=getattr(channel, 'category_id', None),
                              type=message.type.name,
                              is_dm=channel.type == ChannelType.private)


@make_async
@db.connection_context()
def store_pin(message: Message, member: Member) -> ClubPinReaction:
    """Stores in database the information about given Discord Member pinning given Discord Message"""
    logger['pins'].debug(f"Message {message.jump_url} is pinned by member '{member.display_name}' #{member.id}")
    return ClubPinReaction.create(message=message.id,
                                  member=_store_user(member))


@make_async
@db.connection_context()
def store_dm_channel(channel: DMChannel, member: Member) -> None:
    """Stores in database the information about given Discord DM channel"""
    logger['dm'].debug(f"Channel {channel.id} belongs to member '{member.display_name}' #{member.id}")
    rows_count = ClubUser \
        .update({ClubUser.dm_channel_id: channel.id}) \
        .where(ClubUser.id == member.id) \
        .execute()
    if rows_count != 1:
        raise RuntimeError(f"Unexpected number of rows updated ({rows_count}) when recording DM channel #{channel.id} to member #{member.id}")