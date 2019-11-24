import os
import json
import pickle
import datetime
from pathlib import Path
from operator import itemgetter

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from .sheets import coerce_record


# This function looks like an SQL query. Coincidence? Nope.
# See also https://github.com/honzajavorek/junior.guru/issues/137
def select_jobs(jobs):
    jobs = filter(itemgetter('is_approved'), jobs)
    return sorted(jobs, key=itemgetter('timestamp'), reverse=True)


google_service_account_path = Path(__file__).parent / 'google_service_account.json'
google_service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT') or google_service_account_path.read_text()
google_service_account = json.loads(google_service_account_json)
google_scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(google_service_account, google_scope)

doc_key = '1TO5Yzk0-4V_RzRK5Jr9I_pF5knZsEZrNn2HKTXrHgls'
doc = gspread.authorize(credentials).open_by_key(doc_key)
records = doc.worksheet('jobs').get_all_records(default_blank=None)

jobs = select_jobs(map(coerce_record, records))

data_path = Path(__file__).parent / '..' / 'data'
data_path.mkdir(parents=True, exist_ok=True)
data_path.joinpath('jobs.pickle').write_bytes(pickle.dumps(jobs))
