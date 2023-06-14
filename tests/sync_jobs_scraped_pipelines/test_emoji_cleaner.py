import pytest

from juniorguru.sync.jobs_scraped.pipelines.emoji_cleaner import process


def test_emoji_cleaner():
    item = process(dict(title='🦸🏻 Junior projekťák 🦸🏻'))

    assert item['title'] == 'Junior projekťák'


@pytest.mark.parametrize('title', [
    '\u200dQA Engineer/Tester',
    '  \u200dQA Engineer/Tester',
    '\u200d  QA Engineer/Tester',
])
def test_emoji_cleaner_zero_width_joiner(title):
    item = process(dict(title=title))

    assert item['title'] == 'QA Engineer/Tester'
