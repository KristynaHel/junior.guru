from datetime import date, timedelta

import discord
from slugify import slugify

from juniorguru.lib import loggers
from juniorguru.lib.discord_club import ClubClient, ClubMemberID
from juniorguru.lib.mutations import MutationsNotAllowedError, mutating_discord
from juniorguru.models.club import ClubMessage
from juniorguru.sync.onboarding.categories import manage_category


TODAY = date.today()

CHANNELS_OPERATIONS = {}

CHANNEL_DELETE_TIMEOUT = timedelta(days=30)

ONBOARDING_ROLE = 1062768651188580494


logger = loggers.from_path(__file__)


def channels_operation(operation_name):
    def decorator(operation):
        CHANNELS_OPERATIONS[operation_name] = operation

    return decorator


@channels_operation("update")
async def update_onboarding_channel(client: ClubClient, member, channel):
    logger_c = logger[f"channels.{channel.id}"]
    logger_c.info(f"Updating (member #{member.id})")
    channel_data = await prepare_onboarding_channel_data(client, member)
    with mutating_discord(channel) as proxy:
        await proxy.edit(**channel_data)
    member.onboarding_channel_id = channel.id
    member.save()


@channels_operation("create")
async def create_onboarding_channel(client: ClubClient, member):
    logger_c = logger["channels"]
    logger_c.info(f"Creating (member #{member.id})")
    channel_data = await prepare_onboarding_channel_data(client, member)

    async def create_channel(category):
        try:
            with mutating_discord(client.club_guild, raises=True) as proxy:
                channel = await proxy.create_text_channel(
                    category=category, **channel_data
                )
        except MutationsNotAllowedError:
            pass
        else:
            member.onboarding_channel_id = channel.id
            member.save()

    await manage_category(client.club_guild, create_channel)


@channels_operation("delete")
async def delete_onboarding_channel(client: ClubClient, channel):
    logger_c = logger[f"channels.{channel.id}"]
    logger_c.info("Deleting")
    with mutating_discord(channel) as proxy:
        await proxy.delete()


@channels_operation("close")
async def close_onboarding_channel(client: ClubClient, channel):
    logger_c = logger[f"channels.{channel.id}"]
    logger_c.info("Closing")
    last_message_on = ClubMessage.last_message(channel.id).created_at.date()
    current_period = TODAY - last_message_on
    if current_period < CHANNEL_DELETE_TIMEOUT:
        logger_c.warning(
            f"Waiting before deleting. Last message {last_message_on}, currently {current_period.days} days, timeout {CHANNEL_DELETE_TIMEOUT.days} days"
        )
    else:
        with mutating_discord(channel) as proxy:
            await proxy.delete()


async def prepare_onboarding_channel_data(client: ClubClient, member):
    name = f"{slugify(member.display_name, allow_unicode=True)}-tipy"
    topic = f"Soukromý kanál s tipy jen pro tebe! 🦸 {member.display_name} #{member.id}"
    onboarding_role = [
        role for role in client.club_guild.roles if role.id == ONBOARDING_ROLE
    ][0]
    overwrites = {
        # don't have access: @everyone
        client.club_guild.default_role: discord.PermissionOverwrite(
            read_messages=False
        ),
        # have access: onboarded member, people who onboard members, bot
        (await client.get_or_fetch_user(member.id)): discord.PermissionOverwrite(
            read_messages=True
        ),
        onboarding_role: discord.PermissionOverwrite(read_messages=True),
        (await client.get_or_fetch_user(ClubMemberID.BOT)): discord.PermissionOverwrite(
            read_messages=True
        ),
    }
    return dict(name=name, topic=topic, overwrites=overwrites)
