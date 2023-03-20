import asyncio
import json
from collections.abc import Set
from functools import wraps
from pathlib import Path

import scrapy
from peewee import (Check, ConnectionContext as BaseConnectionContext, Model,
                    SqliteDatabase as BaseSqliteDatabase)
from playhouse.sqlite_ext import JSONField as BaseJSONField

from juniorguru.lib import loggers


DB_FILE = Path(__file__).parent / '..' / 'data' / 'data.db'


logger = loggers.from_path(__file__)


class ConnectionContext(BaseConnectionContext):
    """Supports async functions when used as decorator"""
    def __call__(self, fn):
        if asyncio.iscoroutinefunction(fn):
            @wraps(fn)
            async def wrapper(*args, **kwargs):
                with self:
                    return (await fn(*args, **kwargs))
            return wrapper
        return super().__call__(fn)


class SqliteDatabase(BaseSqliteDatabase):
    def connection_context(self):
        return ConnectionContext(self)


db = SqliteDatabase(DB_FILE, pragmas={'journal_mode': 'wal'})


class BaseModel(Model):
    class Meta:
        database = db

    def clear_dirty_fields(self):
        self._dirty = set()


class JSONField(BaseJSONField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('json_dumps', json_dumps)
        super().__init__(*args, **kwargs)


def json_dumps(value):
    def default(o):
        if isinstance(o, scrapy.Item):
            return dict(o)
        if isinstance(o, Set):
            return list(o)
        try:
            return o.isoformat()
        except AttributeError:
            raise TypeError(f'Object of type {o.__class__.__name__} is not JSON serializable')

    return json.dumps(value, ensure_ascii=False, default=default)


def check_enum(field_name, enum_cls):
    values = tuple(member.value for member in enum_cls)
    sql = f"{field_name} in {values!r}"
    return Check(sql)
