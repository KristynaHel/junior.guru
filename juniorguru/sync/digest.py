import textwrap
from datetime import timedelta, date

from discord import Embed

from juniorguru.lib.timer import measure
from juniorguru.lib import loggers
from juniorguru.lib.club import run_discord_task, is_discord_mutable, is_message_older_than
from juniorguru.models import ClubMessage, db


logger = loggers.get(__name__)


DIGEST_CHANNEL = 789046675247333397
DIGEST_LIMIT = 5


@measure()
def main():
    run_discord_task('juniorguru.sync.digest.discord_task')


@db.connection_context()
async def discord_task(client):
    since_date = date.today() - timedelta(weeks=1)
    message = ClubMessage.last_bot_message(DIGEST_CHANNEL, '🔥')
    if is_message_older_than(message, since_date):
        if message:
            since_date = message.created_at.date()
        logger.info(f"Analyzing since {since_date}")

        channel = await client.fetch_channel(DIGEST_CHANNEL)
        messages = ClubMessage.digest_listing(since_date, limit=DIGEST_LIMIT)

        for n, message in enumerate(messages, start=1):
            logger.info(f"Digest #{n}: {message.upvotes_count} votes for {message.author.display_name} in #{message.channel_name}, {message.url}")

        if is_discord_mutable():
            content = [
                f"🔥 **{DIGEST_LIMIT} nej příspěvků za uplynulý týden (od {since_date.day}.{since_date.month}.)**",
                "",
                "Pokud je něco zajímavé nebo ti to pomohlo, dej tomu palec 👍, srdíčko ❤️, očička 👀, apod. Oceníš autory a pomůžeš tomu, aby se příspěvek mohl objevit i tady. Někomu, kdo nemá čas procházet všechno, co se v klubu napíše, se může tento přehled hodit.",
            ]
            embed_description = []
            for message in messages:
                embed_description += [
                    f"{message.upvotes_count}× láska pro {message.author.mention} v {message.channel_mention}:",
                    f"> {textwrap.shorten(message.content, 200, placeholder='…')}",
                    f"[Hop na příspěvek]({message.url})",
                    "",
                ]
            await channel.send(content="\n".join(content),
                                embed=Embed(description="\n".join(embed_description)))


if __name__ == '__main__':
    main()
