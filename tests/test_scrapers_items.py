from datetime import date

import pytest

from juniorguru.scrapers import items


@pytest.mark.parametrize('string,expected', [
    ('', []),
    ('       , ', []),
    ('a,b,,c,', ['a', 'b', 'c']),
    ('  a,     b ,  ', ['a', 'b']),
])
def test_split(string, expected):
    assert items.split(string) == expected


def test_split_by():
    assert items.split('a-b , -  - c-', by='-') == ['a', 'b ,', 'c']


@pytest.mark.parametrize('time,expected', [
    # StackOverflow
    (' Posted 13 days ago', date(2020, 4, 7)),
    (' Posted 4 hours ago', date(2020, 4, 20)),
    (' Posted < 1 hour ago', date(2020, 4, 20)),
    (' Posted yesterday', date(2020, 4, 19)),

    # LinkedIn
    ('3 weeks ago', date(2020, 3, 30)),
    ('28 minutes ago', date(2020, 4, 20)),
    ('1 month ago', date(2020, 3, 21)),
    ('2 months ago', date(2020, 2, 20)),
])
def test_parse_relative_date(time, expected):
    assert items.parse_relative_date(time, today=date(2020, 4, 20)) == expected


def test_parse_relative_date_raises_on_uncrecognized_value():
    with pytest.raises(ValueError):
        items.parse_relative_date('gargamel')


@pytest.mark.parametrize('iterable,expected', [
    ([], None),
    ([1], 1),
    ([1, 2], 1),
    ([None, None, 3], 3),
])
def test_first(iterable, expected):
    assert items.first(iterable) == expected
