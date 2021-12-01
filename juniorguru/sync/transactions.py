import os
from datetime import date

from fiobank import FioBank

from juniorguru.lib.timer import measure
from juniorguru.lib import google_sheets


FIOBANK_API_KEY = os.getenv('FIOBANK_API_KEY')
SIDELINE_JOBS = ['15']
CATEGORIES = [
    lambda t: 'memberships' if t['variable_symbol'] == '21' else None,
    lambda t: 'salary' if 'výplata' in t['message'] else None,
    lambda t: 'sideline' if t['variable_symbol'] in SIDELINE_JOBS else None,
    lambda t: 'lawyer' if 'ADVOKATKA' in t['message'] else None,
    lambda t: 'discord' if 'DISCORD' in t['message'] and t['amount'] < 0 else None,
    lambda t: 'partnerships' if 'RED HAT' in t['message'] and t['amount'] >= 8000 else None,
    lambda t: 'tax' if ('ČSSZ' in t['message'] or 'PSSZ' in t['message'] or 'MSSZ' in t['message']) else None,
    lambda t: 'tax' if 'VZP' in t['message'] else None,
    lambda t: 'marketing' if 'PrintAll' in t['message'] and t['amount'] < 0 else None,
    lambda t: 'donations' if 'GITHUB SPONSORS' in t['message'] and t['amount'] > 0 else None,
    lambda t: 'memberships' if 'STRIPE' in t['message'] and t['amount'] > 0 else None,
    lambda t: 'donations' if 'PAYPAL' in t['message'] and t['amount'] > 0 else None,
    lambda t: 'donations' if not t['variable_symbol'] and t['amount'] > 0 else None,
    lambda t: 'donations' if t['variable_symbol'] == '444222' and t['amount'] > 0 else None,
    lambda t: 'partnerships' if t['variable_symbol'] and t['amount'] >= 8000 else None,
    lambda t: 'jobs' if t['variable_symbol'] and t['amount'] > 0 else None,
    lambda t: 'donations' if t['amount'] > 0 else 'overheads',
]


@measure('transactions')
def main():
    doc_key = '1TO5Yzk0-4V_RzRK5Jr9I_pF5knZsEZrNn2HKTXrHgls'

    client = FioBank(token=FIOBANK_API_KEY)
    to_date = date.today().strftime('%Y-%m-%d')

    records = []
    for transaction in client.period(from_date='2020-01-01', to_date=to_date):
        transaction['message'] = ', '.join(filter(None, [
            transaction.get('comment'),
            transaction.get('user_identification'),
            transaction.get('recipient_message'),
        ]))

        for category_fn in CATEGORIES:
            category = category_fn(transaction)
            if category:
                transaction['category'] = category
                break

        records.append({
            'Date': transaction['date'].strftime('%Y-%m-%d'),
            'Category': transaction['category'],
            'Amount': transaction['amount'],
            'Currency': transaction['currency'],
            'Message': transaction['message'],
            'Variable Symbol': transaction['variable_symbol'],
        })
    google_sheets.upload(google_sheets.get(doc_key, 'transactions'), records)


if __name__ == '__main__':
    main()
