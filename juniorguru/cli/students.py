import csv
import io
import itertools
from datetime import date
from pathlib import Path

import click
from playhouse.shortcuts import model_to_dict

from juniorguru.lib.mutations import mutations
from juniorguru.lib import loggers
from juniorguru.lib.memberful import (Memberful,
                                      serialize_metadata)
from juniorguru.models.partner import Partner


logger = loggers.from_path(__file__)


@click.command()
@click.argument('partner_slug')
@click.option('--all/--no-all', default=False)
@click.option('--invoice/--no-invoice', default=False)
def main(partner_slug, all, invoice):
    if all and invoice:
        logger.error("Can invoice only billable subscriptions, unexpected combination of arguments")
        raise click.Abort()

    try:
        partner = Partner.get_by_slug(partner_slug)
    except Partner.DoesNotExist:
        slugs = [partner.slug for partner in Partner.schools_listing()]
        logger.error(f"Partner must be one of: {', '.join(slugs)}")
        raise click.Abort()
    logger.debug(f"Partner identified as {partner!r}")

    if all:
        logger.info("All subscriptions")
        subscriptions = list(partner.list_student_subscriptions)
    else:
        logger.info("Billable subscriptions")
        subscriptions = list(partner.list_student_subscriptions_billable)

    if subscriptions:
        rows = [subscription_to_row(subscription) for subscription in subscriptions]
        csv_content = to_csv(rows)
        print(csv_content.strip())
        path = Path.home() / 'Downloads' / f"{partner.slug}-{'all' if all else 'billable'}.csv"
        logger.info(f'Saving to {path}')
        path.write_text(csv_content)
    else:
        logger.warning("Didn't find any subscriptions!")
        return

    if invoice:
        if input('Are you sure you want to mark the above as invoiced? (type YES!) ') != 'YES!':
            logger.error("You're not sure")
            raise click.Abort()

        if not mutations.is_allowed('memberful'):
            logger.error('Memberful mutations not allowed!')
            raise click.Abort()

        memberful = Memberful()
        query = '''
            query getMembers($cursor: String!) {
                members(after: $cursor) {
                    totalCount
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                    edges {
                        node {
                            id
                            metadata
                        }
                    }
                }
            }
        '''
        results = memberful.query(query, lambda result: result['members']['pageInfo'])
        edges = itertools.chain.from_iterable(result['members']['edges']
                                              for result in results)
        members = (edge['node'] for edge in edges)
        members_mapping = {member['id']: member['metadata'] for member in members}

        for subscription in subscriptions:
            logger.info(f'Marking {subscription!r} as invoiced')
            mutation = '''
                mutation ($id: ID!, $metadata: Metadata!) {
                    memberUpdate(id: $id, metadata: $metadata) {
                        member {
                            id
                            metadata
                        }
                    }
                }
            '''
            metadata = members_mapping[subscription.account_id]
            logger.debug(f"Previous metadata: {metadata!r}")
            metadata.setdefault(f'{partner.slug}InvoicedOn', date.today().isoformat())
            logger.debug(f"Future metadata: {metadata!r}")
            mark_as_invoiced(memberful, mutation, subscription.account_id, metadata)


@mutations.mutates('memberful')
def mark_as_invoiced(memberful, mutation, account_id, metadata):
    memberful.mutate(mutation, dict(id=account_id,
                                    metadata=serialize_metadata(metadata)))


def to_csv(rows):
    if not rows:
        raise ValueError('No rows')
    f = io.StringIO()
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return f.getvalue()


def subscription_to_row(subscription):
    return {field_name: value for field_name, value
            in model_to_dict(subscription).items()
            if field_name in ['name', 'email', 'started_on', 'invoiced_on']}
