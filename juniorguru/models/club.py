import math
from collections import Counter
from datetime import date, timedelta
from enum import StrEnum, unique

from emoji import is_emoji
from peewee import (BooleanField, CharField, DateField, DateTimeField, ForeignKeyField,
                    IntegerField, TextField, fn)

from juniorguru.lib.charts import month_range
from juniorguru.lib.coupons import parse_coupon
from juniorguru.lib.discord_club import ClubChannel
from juniorguru.models.base import BaseModel, JSONField, check_enum


TOP_MEMBERS_PERCENT = 0.05

RECENT_PERIOD_DAYS = 30

IS_NEW_PERIOD_DAYS = 15

UPVOTES_EXCLUDE_CHANNELS = [
    ClubChannel.INTRO,
    ClubChannel.ANNOUNCEMENTS,
    ClubChannel.BOT,
    ClubChannel.DASHBOARD,
    ClubChannel.FUN,
    ClubChannel.FUN_TOPICS,
]

STATS_EXCLUDE_CHANNELS = [
    ClubChannel.ANNOUNCEMENTS,
    ClubChannel.JOBS,
    ClubChannel.BOT,
    ClubChannel.DASHBOARD,
    ClubChannel.FUN,
    ClubChannel.FUN_TOPICS,
    834443926655598592,  # práce-bot (archived)
]


class ClubUser(BaseModel):
    id = IntegerField(primary_key=True)
    subscription_id = CharField(null=True)
    joined_at = DateTimeField(null=True)
    subscribed_at = DateTimeField(null=True)
    expires_at = DateTimeField(null=True)
    is_bot = BooleanField(default=False)
    is_member = BooleanField(default=True)
    has_avatar = BooleanField(default=True)
    avatar_path = CharField(null=True)
    display_name = CharField()
    has_feminine_name = BooleanField(null=True)
    mention = CharField(unique=True)
    tag = CharField()
    coupon = CharField(null=True, index=True)
    initial_roles = JSONField(default=list)
    updated_roles = JSONField(null=True)
    dm_channel_id = IntegerField(null=True, unique=True)
    onboarding_channel_id = IntegerField(null=True, unique=True)

    @property
    def joined_on(self):
        return self.joined_at.date() if self.joined_at else None

    @property
    def subscribed_on(self):
        return self.subscribed_at.date() if self.subscribed_at else None

    @property
    def intro(self):
        return self.list_public_messages \
            .where(ClubMessage.channel_id == ClubChannel.INTRO,
                   ClubMessage.type == 'default') \
            .order_by(ClubMessage.created_at.desc()) \
            .first()

    @property
    def list_public_messages(self):
        return self.list_messages \
            .where(ClubMessage.is_private == False) \
            .order_by(ClubMessage.created_at.desc())

    @property
    def intro_thread_id(self):
        intro = self.intro
        return intro.id if intro else None

    def update_subscribed_at(self, subscribed_at):
        self.subscribed_at = non_empty_min([self.subscribed_at, subscribed_at])

    def update_expires_at(self, expires_at):
        self.expires_at = non_empty_max([self.expires_at, expires_at])

    def messages_count(self, private=False):
        list_messages = self.list_messages if private else self.list_public_messages
        return list_messages.count()

    def recent_messages_count(self, today=None, private=False):
        return self.list_recent_messages(today, private).count()

    def upvotes_count(self, private=False):
        list_messages = self.list_messages if private else self.list_public_messages
        messages = list_messages \
            .where(ClubMessage.parent_channel_id.not_in(UPVOTES_EXCLUDE_CHANNELS))
        return sum([message.upvotes_count for message in messages])

    def recent_upvotes_count(self, today=None, private=False):
        messages = self.list_recent_messages(today, private) \
            .where(ClubMessage.parent_channel_id.not_in(UPVOTES_EXCLUDE_CHANNELS))
        return sum([message.upvotes_count for message in messages])

    def first_seen_on(self):
        first_message = self.list_messages \
            .order_by(ClubMessage.created_at) \
            .first()
        if not first_message:
            first_pin = self.list_pins \
                .join(ClubMessage) \
                .order_by(ClubMessage.created_at) \
                .first()
            first_message = first_pin.message if first_pin else None
        return first_message.created_at.date() if first_message else self.joined_on

    def list_recent_messages(self, today=None, private=False):
        list_messages = self.list_messages if private else self.list_public_messages
        recent_period_start_at = (today or date.today()) - timedelta(days=RECENT_PERIOD_DAYS)
        return list_messages.where(ClubMessage.created_at >= recent_period_start_at)

    def is_new(self, today=None):
        return (self.first_seen_on() + timedelta(days=IS_NEW_PERIOD_DAYS)) >= (today or date.today())

    def is_year_old(self, today=None):
        joined_on = non_empty_min([self.joined_on, self.subscribed_on, self.first_seen_on()])
        return joined_on.replace(year=joined_on.year + 1) <= (today or date.today())

    def is_founder(self):
        return bool(self.coupon and parse_coupon(self.coupon)['name'] == 'FOUNDERS')

    @classmethod
    def count(cls):
        return cls.listing().count()

    @classmethod
    def members_count(cls):
        return cls.members_listing().count()

    @classmethod
    def avatars_count(cls):
        return cls.avatars_listing().count()

    @classmethod
    def top_members_limit(cls):
        return math.ceil(cls.members_count() * TOP_MEMBERS_PERCENT)

    @classmethod
    def listing(cls):
        return cls.select()

    @classmethod
    def members_listing(cls, shuffle=False):
        members = cls.listing() \
            .where(cls.is_bot == False,
                   cls.is_member == True)
        if shuffle:
            members = members.order_by(fn.random())
        return members

    @classmethod
    def onboarding_listing(cls):
        return cls.members_listing().where(cls.onboarding_channel_id.is_null(False))

    @classmethod
    def avatars_listing(cls):
        return cls.members_listing().where(cls.avatar_path.is_null(False))


class ClubMessage(BaseModel):
    id = IntegerField(primary_key=True)
    url = CharField()
    content = TextField()
    content_size = IntegerField()
    reactions = JSONField(default=dict)
    upvotes_count = IntegerField(default=0)
    downvotes_count = IntegerField(default=0)
    created_at = DateTimeField(index=True)
    created_month = CharField(index=True)
    author = ForeignKeyField(ClubUser, backref='list_messages')
    author_is_bot = BooleanField()
    channel_id = IntegerField()
    channel_name = CharField()
    parent_channel_id = IntegerField(index=True, null=True)
    category_id = IntegerField(index=True, null=True)
    type = CharField(default='default')
    is_private = BooleanField(default=False)

    @property
    def emoji_prefix(self):
        try:
            emoji = self.content.split(maxsplit=1)[0]
        except IndexError:
            return None
        if is_emoji(emoji):
            return emoji
        return None

    @property
    def is_intro(self):
        return self.author.intro.id == self.id

    @classmethod
    def count(cls):
        return cls.select().count()

    @classmethod
    def content_size_by_month(cls, date):
        messages = cls.select() \
            .where(cls.created_month == f'{date:%Y-%m}') \
            .where(cls.author_is_bot == False) \
            .where(cls.is_private == False) \
            .where(cls.channel_id.not_in(STATS_EXCLUDE_CHANNELS))
        return sum(message.content_size for message in messages)

    @classmethod
    def listing(cls):
        return cls.select() \
            .where(cls.is_private == False) \
            .order_by(cls.created_at)

    @classmethod
    def channel_listing(cls, channel_id):
        return cls.select() \
            .where(cls.channel_id == channel_id) \
            .order_by(cls.created_at)

    @classmethod
    def channel_listing_bot(cls, channel_id):
        return cls.channel_listing(channel_id) \
            .where(cls.author_is_bot == True)

    @classmethod
    def channel_listing_since(cls, channel_id, since_at):
        return cls.select() \
            .where((cls.channel_id == channel_id)
                   & (cls.created_at >= since_at)) \
            .order_by(cls.created_at)

    @classmethod
    def digest_listing(cls, since_dt, limit=5):
        return cls.select() \
            .where(cls.is_private == False,
                   ClubMessage.parent_channel_id.not_in(UPVOTES_EXCLUDE_CHANNELS),
                   cls.created_at >= since_dt) \
            .order_by(cls.upvotes_count.desc()) \
            .limit(limit)

    @classmethod
    def last_message(cls, channel_id=None):
        query = cls.select()
        if channel_id is not None:
            query = query.where(cls.channel_id == channel_id)
        return query.order_by(cls.created_at.desc()).first()

    @classmethod
    def last_bot_message(cls, channel_id, startswith_emoji=None, contains_text=None):
        query = cls.select() \
            .where(cls.author_is_bot == True,
                   cls.channel_id == channel_id) \
            .order_by(cls.created_at.desc())
        if startswith_emoji:
            query = query.where(cls.content.startswith(startswith_emoji))
        if contains_text:
            query = query.where(cls.content.contains(contains_text))
        return query.first()


class ClubPinReaction(BaseModel):
    member = ForeignKeyField(ClubUser, backref='list_pins')
    message = ForeignKeyField(ClubMessage, backref='list_pins')

    @classmethod
    def count(cls):
        return cls.select().count()

    @classmethod
    def listing(cls):
        return cls.select()

    @classmethod
    def members_listing(cls):
        return cls.select() \
            .join(ClubUser) \
            .where(ClubUser.is_member == True)


@unique
class ClubSubscribedPeriodIntervalUnit(StrEnum):
    MONTHLY = 'month'
    YEARLY = 'year'


@unique
class ClubSubscribedPeriodCategory(StrEnum):
    FREE = 'free'
    TEAM = 'team'
    FINAID = 'finaid'
    CORESKILL = 'coreskill'
    INDIVIDUALS = 'individuals'
    TRIAL = 'trial'
    PARTNER = 'partner'
    STUDENT = 'students'


class ClubSubscribedPeriod(BaseModel):
    account_id = CharField()
    start_on = DateField()
    end_on = DateField()
    interval_unit = CharField(constraints=[check_enum('interval_unit', ClubSubscribedPeriodIntervalUnit)])
    category = CharField(null=True, constraints=[check_enum('category', ClubSubscribedPeriodCategory)])
    has_feminine_name = BooleanField()

    @classmethod
    def listing(cls, date):
        return cls.select(cls, fn.max(cls.start_on)) \
            .where(cls.start_on <= date, cls.end_on >= date) \
            .group_by(cls.account_id) \
            .order_by(cls.start_on)

    @classmethod
    def count(cls, date):
        return cls.listing(date).count()

    @classmethod
    def count_breakdown(cls, date):
        counter = Counter([subscribed_period.category
                           for subscribed_period
                           in cls.listing(date)])
        return {category.value: counter[category] for category
                in ClubSubscribedPeriodCategory}

    @classmethod
    def women_count(cls, date):
        return cls.listing(date) \
            .where(cls.has_feminine_name == True) \
            .count()

    @classmethod
    def women_ptc(cls, date):
        count = cls.count(date)
        if count:
            return math.ceil((cls.women_count(date) / count) * 100)
        return 0

    @classmethod
    def individuals(cls, date):
        return cls.listing(date) \
            .where(cls.category == ClubSubscribedPeriodCategory.INDIVIDUALS)

    @classmethod
    def individuals_count(cls, date):
        return cls.individuals(date).count()

    @classmethod
    def individuals_yearly_count(cls, date):
        return cls.individuals(date) \
            .where(cls.interval_unit == ClubSubscribedPeriodIntervalUnit.YEARLY) \
            .count()

    @classmethod
    def signups(cls, date):
        from_date, to_date = month_range(date)
        return cls.select(cls, fn.min(cls.start_on)) \
            .group_by(cls.account_id) \
            .having(cls.start_on >= from_date, cls.start_on <= to_date) \
            .order_by(cls.start_on)

    @classmethod
    def signups_count(cls, date):
        return cls.signups(date).count()

    @classmethod
    def individuals_signups(cls, date):
        return cls.signups(date).where(cls.category == ClubSubscribedPeriodCategory.INDIVIDUALS)

    @classmethod
    def individuals_signups_count(cls, date):
        return cls.individuals_signups(date).count()

    @classmethod
    def quits(cls, date):
        from_date, to_date = month_range(date)
        return cls.select(cls, fn.max(cls.end_on)) \
            .group_by(cls.account_id) \
            .having(cls.end_on >= from_date, cls.end_on <= to_date) \
            .order_by(cls.end_on)

    @classmethod
    def quits_count(cls, date):
        return cls.quits(date).count()

    @classmethod
    def individuals_quits(cls, date):
        return cls.quits(date).where(cls.category == ClubSubscribedPeriodCategory.INDIVIDUALS)

    @classmethod
    def individuals_quits_count(cls, date):
        return cls.individuals_quits(date).count()

    @classmethod
    def churn_ptc(cls, date):
        from_date = month_range(date)[0]
        churn = cls.quits_count(date) / (cls.count(from_date) + cls.signups_count(date))
        return churn * 100

    @classmethod
    def individuals_churn_ptc(cls, date):
        from_date = month_range(date)[0]
        churn = cls.individuals_quits_count(date) / (cls.individuals_count(from_date) + cls.individuals_signups_count(date))
        return churn * 100

    @classmethod
    def individuals_duration_avg(cls, date):
        from_date, to_date = month_range(date)
        results = cls.select(cls.account_id, fn.min(cls.start_on), fn.max(cls.end_on)) \
            .where(cls.category == ClubSubscribedPeriodCategory.INDIVIDUALS) \
            .group_by(cls.account_id) \
            .having(fn.min(cls.start_on) <= from_date)
        if not results:
            return 0
        durations = [((min(to_date, result.end_on) - result.start_on).days / 30) for result in results]
        return sum(durations) / len(durations)

    def __str__(self):
        return f'#{self.account_id} {self.start_on}…{self.end_on} {self.category}'


class ClubDocumentedRole(BaseModel):
    id = IntegerField(primary_key=True)
    name = CharField(unique=True)
    mention = CharField(unique=True)
    slug = CharField(unique=True)
    description = TextField()
    position = IntegerField(unique=True)
    emoji = CharField(null=True)

    @classmethod
    def get_by_slug(cls, slug):
        if not slug:
            raise ValueError(repr(slug))
        return cls.select() \
            .where(cls.slug == slug) \
            .get()

    @classmethod
    def listing(cls):
        return cls.select() \
            .order_by(cls.position)


def non_empty_min(values):
    values = list(filter(None, values))
    if values:
        return min(values)
    return None


def non_empty_max(values):
    values = list(filter(None, values))
    if values:
        return max(values)
    return None
