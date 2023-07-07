from datetime import date
from typing import Iterable

from peewee import CharField, ForeignKeyField, fn, IntegerField

from juniorguru.models.base import BaseModel
from juniorguru.models.partner import Partner, Partnership


class CourseProvider(BaseModel):
    name = CharField()
    slug = CharField(unique=True)
    url = CharField()
    cz_business_id = IntegerField(null=True)
    edit_url = CharField()
    page_title = CharField()
    page_description = CharField()
    page_lead = CharField()
    partner = ForeignKeyField(Partner, backref='_course_provider', null=True, unique=True)

    @property
    def page_url(self) -> str:
        return f'courses/{self.slug}.md'

    def active_partnership(self, today: date=None) -> Partnership | None:
        return self.partner.active_partnership(today=today) if self.partner else None

    @classmethod
    def listing(cls, today: date=None) -> Iterable['CourseProvider']:
        priority = [partner.course_provider for partner in Partner.active_listing(today=today)
                    if partner.course_provider]
        priority_slugs = [course_provider.slug for course_provider in priority]
        query = cls.select() \
            .where(cls.slug.not_in(priority_slugs)) \
            .order_by(fn.lower(cls.name))
        return priority + list(query)

    @classmethod
    def get_by_slug(cls, slug) -> 'CourseProvider':
        return cls.get(cls.slug == slug)

    def __str__(self) -> str:
        return self.name
