import textwrap

from discord import Embed
from discord.errors import Forbidden

from juniorguru.lib.timer import measure
from juniorguru.lib import loggers
from juniorguru.lib.club import discord_task, DISCORD_MUTATIONS_ENABLED
from juniorguru.models import ClubPinReaction, ClubUser, ClubMessage, db


logger = loggers.get('pins')


@measure('pins')
@discord_task
async def main(client):
    with db:
        top_members_limit = ClubUser.top_members_limit()
        pin_reactions_by_members = [pin_reaction for pin_reaction
                                    in ClubPinReaction.listing()
                                    if pin_reaction.user.is_member]

    logger.info(f'Found {len(pin_reactions_by_members)} pin reactions by people who are currently members')
    for pin_reaction in pin_reactions_by_members:
        member = await client.juniorguru_guild.fetch_member(pin_reaction.user.id)

        if member.dm_channel:
            channel = member.dm_channel
        else:
            channel = await member.create_dm()

        logger.info(f"Checking DM if already pinned for {member.display_name} #{member.id}")
        if await is_pinned(pin_reaction.message.url, channel):
            logger.info(f"Already pinned for {member.display_name} #{member.id}")
            continue

        logger.info(f"Not pinned for {member.display_name} #{member.id}, sending a message to DM")
        if DISCORD_MUTATIONS_ENABLED:
            content = (
                '📌 Vidím špendlík! Ukládám ti příspěvek sem, do soukromé zprávy. '
                f'Když bude mít ~{top_members_limit} špendlíků, připnu jej v původním kanálu pro všechny.'
            )
            embed_description = [
                f"{pin_reaction.message.author.mention} v {pin_reaction.message.channel_mention}:",
                f"> {textwrap.shorten(pin_reaction.message.content, 500, placeholder='…')}",
                f"[Hop na příspěvek]({pin_reaction.message.url})",
                "",
            ]
            try:
                await channel.send(content=content,
                                   embed=Embed(description="\n".join(embed_description)))
            except Forbidden as e:
                logger.error(str(e), exc_info=True)
        else:
            logger.warning("Skipping Discord mutations, DISCORD_MUTATIONS_ENABLED not set")

    logger.info(f"Going through messages pinned by reactions, minimum is {top_members_limit} pin reactions")
    with db:
        messages = ClubMessage.pinned_by_reactions_listing(top_members_limit)
    logger.info(f'Found {len(messages)} messages')
    for message in messages:
        logger.info(f"Message {message.url} {'PINNED' if message.is_pinned else 'NOT PINNED'}")
        if not message.is_pinned:
            logger.info(f"Pinning {message.url}")
            channel = await client.fetch_channel(message.channel_id)
            discord_message = await channel.fetch_message(message.id)
            await discord_message.pin(reason=f"The message has {message.pin_reactions_count} pin reactions, minimum is {top_members_limit}")


async def is_pinned(message_url, channel):
    async for message in channel.history(limit=None, after=None):
        starts_with_pin_emoji = message.content.startswith('📌')
        contains_message_url = any([message_url in embed.description for embed in message.embeds])
        if starts_with_pin_emoji and contains_message_url:
            return True
    return False


if __name__ == '__main__':
    main()
