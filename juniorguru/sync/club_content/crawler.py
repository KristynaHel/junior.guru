import asyncio
import itertools
from datetime import timedelta

import arrow

from juniorguru.lib import loggers
from juniorguru.lib.discord_club import (DEFAULT_CHANNELS_HISTORY_SINCE, ClubChannel,
                                         ClubEmoji, emoji_name, fetch_threads,
                                         get_parent_channel_id, is_member,
                                         is_thread_after)
from juniorguru.sync.club_content.store import store_member, store_message, store_pin


logger = loggers.from_path(__file__)


WORKERS_COUNT = 5

CHANNELS_HISTORY_SINCE = {
    ClubChannel.FUN: timedelta(days=30),  # volná-zábava
    ClubChannel.FUN_TOPICS: timedelta(days=30),  # volná-témata

    # take all history since ever
    ClubChannel.INTRO: None,

    # skip channels
    ClubChannel.BOT: timedelta(0),
    ClubChannel.JOBS: timedelta(0),
    834443926655598592: timedelta(0),  # práce-bot (archived)
}


async def crawl(client):
    logger.info("Crawling members")
    async with asyncio.TaskGroup() as tasks:
        async for member in client.club_guild.fetch_members(limit=None):
            tasks.create_task(store_member(member))

    logger.info("Crawling channels")
    channels = (channel for channel  # or just club_guild.channels ???
                in itertools.chain(client.club_guild.text_channels,
                                   client.club_guild.voice_channels,
                                   # TODO client.club_guild.stage_channels,
                                   client.club_guild.forum_channels)
                if channel.permissions_for(client.club_guild.me).read_messages)
    await run_channel_queue(channels)


async def run_channel_queue(channels):
    queue = asyncio.Queue()
    for channel in channels:
        queue.put_nowait(channel)

    workers = [asyncio.create_task(channel_worker(worker_no, queue))
               for worker_no in range(WORKERS_COUNT)]

    # trick to prevent hangs if workers raise, see https://stackoverflow.com/a/60710981/325365
    queue_completed = asyncio.create_task(queue.join())
    await asyncio.wait([queue_completed, *workers], return_when=asyncio.FIRST_COMPLETED)

    # if there's a worker which raised
    if not queue_completed.done():
        workers_done = [worker for worker in workers if worker.done()]
        logger.warning(f'Some workers ({len(workers_done)} of {WORKERS_COUNT}) finished before the queue is done!')
        workers_done[0].result()  # raises

    # cancel workers which are still runnning
    for worker in workers:
        worker.cancel()

    # return_exceptions=True silently collects CancelledError() exceptions
    await asyncio.gather(*workers, return_exceptions=True)


async def channel_worker(worker_no, queue):
    logger_cw = logger[worker_no]['channels']
    while True:
        channel = await queue.get()
        logger_c = get_channel_logger(logger_cw, channel)
        logger_c.info(f'Crawling {channel.name!r}')

        history_since = CHANNELS_HISTORY_SINCE.get(get_parent_channel_id(channel),
                                                   DEFAULT_CHANNELS_HISTORY_SINCE)
        if history_since is None:
            history_after = None
            logger_c.debug("Crawling all channel history")
        else:
            history_after = (arrow.utcnow() - history_since).datetime
            logger_c.debug(f"Crawling history after {history_after:%Y-%m-%d} ({history_since.days} days ago)")

        threads = [thread async for thread in fetch_threads(channel)
                   if is_thread_after(thread, after=history_after)]
        if threads:
            logger_c.info(f"Adding {len(threads)} threads")
        for thread in threads:
            logger_c.debug(f"Adding thread '{thread.name}' #{thread.id} {thread.jump_url}")
            queue.put_nowait(thread)

        async with asyncio.TaskGroup() as tasks:
            async for message in fetch_messages(channel, after=history_after):
                tasks.create_task(store_message(message, channel))
                async for reacting_member in fetch_members_reacting_by_pin(message.reactions):
                    tasks.create_task(store_pin(message, reacting_member))

        logger_c.debug(f'Done crawling {channel.name!r}')
        queue.task_done()


def get_channel_logger(logger, channel):
    parent_channel_id = get_parent_channel_id(channel)
    logger = logger[parent_channel_id]
    if parent_channel_id != channel.id:
        logger = logger[channel.id]
    return logger


async def fetch_messages(channel, after=None):
    try:
        channel_history = channel.history
    except AttributeError:
        return  # channel type doesn't support history (e.g. forum)
    async for message in channel_history(limit=None, after=after):
        yield message


async def fetch_members_reacting_by_pin(reactions):
    for reaction in reactions:
        if emoji_name(reaction.emoji) == ClubEmoji.PIN:
            async for user in reaction.users():
                if is_member(user):
                    yield user
            break
