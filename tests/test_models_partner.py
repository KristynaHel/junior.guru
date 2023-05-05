import uuid
from datetime import date, datetime

import pytest
from peewee import SqliteDatabase

from juniorguru.models.club import ClubMessage, ClubUser
from juniorguru.models.course_provider import CourseProvider
from juniorguru.models.event import Event
from juniorguru.models.job import ListedJob, SubmittedJob
from juniorguru.models.partner import (Partner, Partnership, PartnershipBenefit,
                                       PartnershipPlan, PartnerStudentSubscription)
from juniorguru.models.podcast import PodcastEpisode

from testing_utils import prepare_partner_data, prepare_course_provider_data


def create_partner(id, **kwargs):
    return Partner.create(**prepare_partner_data(id, **kwargs))


def create_plan(slug, benefit_slugs=None):
    plan = PartnershipPlan.create(slug=slug,
                                  name=f"Plan '{slug}'",
                                  price=10000)
    for position, benefit_slug in enumerate(benefit_slugs or []):
        PartnershipBenefit.create(position=position,
                                  text=f"Benefit '{benefit_slug}'",
                                  icon=f'{benefit_slug}-circle',
                                  plan=plan,
                                  slug=benefit_slug)
    return plan


def setup_plan_hierarchy(plan0, plan1):
    plan0.hierarchy_rank = 0
    plan0.save()
    plan1.includes = plan0
    plan1.hierarchy_rank = 1
    plan1.save()


def create_partnership(partner, starts_on, expires_on, plan=None, benefits_registry=None):
    return Partnership.create(partner=partner,
                              plan=plan or create_plan(f'basic-{uuid.uuid4()}'),
                              starts_on=starts_on,
                              expires_on=expires_on,
                              benefits_registry=benefits_registry or [])


def create_student_subscription(partner, **kwargs):
    return PartnerStudentSubscription.create(partner=partner,
                                             account_id='123',
                                             name='Alice',
                                             email='alice@example.com',
                                             started_on=kwargs.get('started_on', date.today()),
                                             invoiced_on=kwargs.get('invoiced_on', date.today()))


@pytest.fixture
def db_connection():
    models = [Partner, PartnerStudentSubscription,
              Partnership, PartnershipPlan, PartnershipBenefit,
              ClubUser, ClubMessage,
              ListedJob, SubmittedJob,
              Event, PodcastEpisode, CourseProvider]
    db = SqliteDatabase(':memory:')
    with db:
        db.bind(models)
        db.create_tables(models)
        yield db
        db.drop_tables(models)


@pytest.fixture
def plan_basic():
    return create_plan('basic', ['food', 'drinks'])


@pytest.fixture
def plan_top():
    return create_plan('top', ['flowers', 'balloon'])


@pytest.fixture
def plan_handbook():
    return create_plan('handbook', ['logo_handbook', 'flowers', 'balloon'])


def test_partner_name_markdown_bold(db_connection):
    partner = create_partner(1, name='Banana Company')

    assert partner.name_markdown_bold == '**Banana Company**'


def test_partner_active_partnership(db_connection):
    today = date(2021, 5, 2)
    partner = create_partner(1)
    partnership1 = create_partnership(partner, date(2020, 12, 1), date(2021, 1, 1))  # noqa
    partnership2 = create_partnership(partner, date(2021, 4, 1), None)

    assert partner.active_partnership(today=today) == partnership2


def test_partner_active_partnership_no_active_partnership(db_connection):
    today = date(2021, 5, 2)
    partner = create_partner(1)
    create_partnership(partner, date(2020, 12, 1), date(2021, 1, 1))
    create_partnership(partner, date(2021, 4, 1), date(2021, 4, 15))

    assert partner.active_partnership(today=today) is None


def test_partner_active_partnership_no_partnership(db_connection):
    partner = create_partner(1)

    assert partner.active_partnership() is None


def test_partner_first_partnership(db_connection):
    partner = create_partner(1)
    partnership1 = create_partnership(partner, date(2020, 12, 1), date(2021, 1, 1))
    partnership2 = create_partnership(partner, date(2021, 4, 1), None)  # noqa

    assert partner.first_partnership() == partnership1


def test_partner_first_partnership_no_partnership(db_connection):
    partner = create_partner(1)

    assert partner.first_partnership() is None


def test_partner_expired_listing(db_connection):
    today = date(2023, 5, 2)
    partner1 = create_partner(1)
    create_partnership(partner1, date(2023, 3, 1), date(2023, 4, 1))
    partner2 = create_partner(2)
    create_partnership(partner2, date(2023, 3, 1), date(2023, 5, 1))
    partner3 = create_partner(3)
    create_partnership(partner3, date(2023, 3, 1), date(2023, 5, 2))
    partner4 = create_partner(4)
    create_partnership(partner4, date(2023, 3, 1), date(2023, 5, 3))

    assert set(Partner.expired_listing(today=today)) == {partner1, partner2}


def test_partner_expired_listing_skips_barters(db_connection):
    today = date(2023, 5, 1)
    partner1 = create_partner(1)
    create_partnership(partner1, date(2023, 3, 1), date(2023, 4, 1))
    partner2 = create_partner(2)
    create_partnership(partner2, date(2023, 3, 1), None)

    assert set(Partner.expired_listing(today=today)) == {partner1}


def test_partner_expired_listing_skips_planned(db_connection):
    today = date(2023, 5, 1)
    partner1 = create_partner(1)
    create_partnership(partner1, date(2023, 2, 1), date(2023, 4, 1))
    partner2 = create_partner(2)
    create_partnership(partner2, date(2023, 3, 1), date(2023, 4, 1))
    partner3 = create_partner(3)
    create_partnership(partner3, date(2023, 6, 1), date(2023, 7, 1))

    assert set(Partner.expired_listing(today=today)) == {partner1, partner2}


def test_partner_expired_listing_sorts_by_name(db_connection):
    today = date(2023, 6, 1)
    partner1 = create_partner(1, name='Company B')
    create_partnership(partner1, date(2023, 2, 1), date(2023, 5, 1))
    partner2 = create_partner(2, name='Company XYZ')
    create_partnership(partner2, date(2023, 3, 1), date(2023, 4, 1))
    partner3 = create_partner(3, name='Company A')
    create_partnership(partner3, date(2023, 2, 1), date(2023, 5, 1))

    assert list(Partner.expired_listing(today=today)) == [partner3, partner1, partner2]


def test_partner_expired_listing_skips_active_partners(db_connection):
    today = date(2023, 6, 1)
    partner1 = create_partner(1)
    create_partnership(partner1, date(2023, 2, 1), date(2023, 5, 1))
    create_partnership(partner1, date(2023, 5, 15), None)

    assert list(Partner.expired_listing(today=today)) == []


def test_partner_having_students_listing(db_connection):
    partner1 = create_partner(1, student_coupon='STUDENT!')
    partner2 = create_partner(2, student_coupon=None)  # noqa
    partner3 = create_partner(3, student_coupon='STUDENT!')

    assert set(Partner.having_students_listing()) == {partner1, partner3}


def test_partner_having_students_listing_sorts_by_name(db_connection):
    partner1 = create_partner(1, name='Banana', student_coupon='STUDENT!')
    partner2 = create_partner(3, name='Apple', student_coupon='STUDENT!')

    assert list(Partner.having_students_listing()) == [partner2, partner1]


def test_partner_course_provider(db_connection):
    partner = create_partner(123, name='Apple', slug='a')
    course_provider = CourseProvider.create(**prepare_course_provider_data(456, slug='a', partner=partner))

    assert partner.course_provider == course_provider


def test_partner_course_provider_is_none(db_connection):
    partner = create_partner(123, name='Xena', slug='x')
    CourseProvider.create(**prepare_course_provider_data(456, slug='a'))

    assert partner.course_provider is None


@pytest.mark.parametrize('student_coupon, expected', [
    ('STUDENT!', True),
    (None, False),
])
def test_partner_has_students(db_connection, student_coupon, expected):
    partner = create_partner(1, student_coupon=student_coupon)

    assert partner.has_students is expected


def test_partner_list_members(db_connection):
    member1 = ClubUser.create(display_name='Bob', mention='<@111>', coupon='XEROX', tag='abc#1234')
    member2 = ClubUser.create(display_name='Alice', mention='<@222>', coupon='XEROX', tag='abc#1234')
    member3 = ClubUser.create(display_name='Celine', mention='<@333>', coupon='ZALANDO', tag='abc#1234')  # noqa
    partner = create_partner(1, coupon='XEROX')

    assert list(partner.list_members) == [member2, member1]


def test_partner_list_student_members(db_connection):
    member1 = ClubUser.create(display_name='Bob', mention='<@111>', coupon='XEROXSTUDENT', tag='abc#1234')
    member2 = ClubUser.create(display_name='Alice', mention='<@222>', coupon='XEROXSTUDENT', tag='abc#1234')
    member3 = ClubUser.create(display_name='Celine', mention='<@333>', coupon='ZALANDOSTUDENT', tag='abc#1234')  # noqa
    partner = create_partner(1, student_coupon='XEROXSTUDENT')

    assert list(partner.list_student_members) == [member2, member1]


def test_partner_list_jobs(db_connection):
    def create_job(id, company_name, title='Title'):
        submitted_job = SubmittedJob.create(id=id,
                                            title=title,
                                            posted_on=date(2023, 2, 14),
                                            expires_on=date(2024, 2, 14),
                                            url=f'https://junior.guru/jobs/{id}/',
                                            company_name=company_name,
                                            company_url='https://example.com/',
                                            description_html='...',
                                            lang='cs')
        listed_job = submitted_job.to_listed()
        listed_job.save()
        return listed_job
    job1 = create_job('1', 'Harley-Davidson', title='Job XYZ')
    job2 = create_job('2', 'Harley Davidson')  # noqa
    job3 = create_job('3', 'Harley-Davidson', title='Job ABC')
    job4 = create_job('4', 'harley-davidson')  # noqa
    partner = create_partner(1, name='Harley-Davidson')

    assert list(partner.list_jobs) == [job3, job1]


def test_partner_list_events(db_connection):
    def create_event(id, partner=None):
        return Event.create(id=id,
                            partner=partner,
                            title='...',
                            start_at=datetime(2023, 1, 1),
                            description='...',
                            bio='...',
                            bio_name='...')
    partner = create_partner(1)
    event1 = create_event('1')  # noqa
    event2 = create_event('2', partner)
    event3 = create_event('3', partner)
    assert set(partner.list_events) == {event2, event3}


def test_partner_list_podcast_episodes(db_connection):
    def create_episode(id, partner=None):
        return PodcastEpisode.create(id=id,
                                     partner=partner,
                                     publish_on=date(2023, 1, int(id)),
                                     title='...',
                                     media_url='...',
                                     media_size=42,
                                     media_type='...',
                                     media_duration_s=42,
                                     description='...',
                                     avatar_path='...')
    partner = create_partner(1)
    episode1 = create_episode('1')  # noqa
    episode2 = create_episode('2', partner)
    episode3 = create_episode('3', partner)
    assert set(partner.list_podcast_episodes) == {episode2, episode3}


def test_partner_get_by_slug(db_connection):
    create_partner(1, slug='xerox')
    partner = create_partner(2, slug='zalando')

    assert Partner.get_by_slug('zalando') == partner


def test_partner_get_by_slug_doesnt_exist(db_connection):
    create_partner(1, slug='xerox')

    with pytest.raises(Partner.DoesNotExist):
        assert Partner.get_by_slug('zalando')


def test_partner_list_student_subscriptions(db_connection):
    partner = create_partner(1)
    subscription1 = create_student_subscription(partner, invoiced_on=date.today())
    subscription2 = create_student_subscription(partner, invoiced_on=None)

    assert set(partner.list_student_subscriptions) == {subscription1, subscription2}


def test_partner_list_student_subscriptions_billable(db_connection):
    partner = create_partner(1)
    subscription1 = create_student_subscription(partner, invoiced_on=date.today())  # noqa
    subscription2 = create_student_subscription(partner, invoiced_on=None)

    assert set(partner.list_student_subscriptions_billable) == {subscription2}


def test_plan_get_by_slug(db_connection, plan_basic):
    assert PartnershipPlan.get_by_slug('basic') == plan_basic


def test_plan_get_by_slug_doesnt_exist(db_connection):
    with pytest.raises(PartnershipPlan.DoesNotExist):
        assert PartnershipPlan.get_by_slug('basic')


def test_plan_hierarchy(db_connection, plan_basic, plan_top):
    setup_plan_hierarchy(plan_basic, plan_top)

    assert list(plan_top.hierarchy) == [plan_basic, plan_top]


def test_plan_benefits_all(db_connection, plan_basic, plan_top):
    setup_plan_hierarchy(plan_basic, plan_top)

    assert [benefit.slug for benefit in plan_top.benefits()] == ['food', 'drinks', 'flowers', 'balloon']


def test_plan_benefits_own(db_connection, plan_basic, plan_top):
    setup_plan_hierarchy(plan_basic, plan_top)

    assert [benefit.slug for benefit in plan_top.benefits(all=False)] == ['flowers', 'balloon']


def test_plan_benefits_slugs(db_connection, plan_basic, plan_top):
    setup_plan_hierarchy(plan_basic, plan_top)

    assert plan_top.benefits_slugs() == ['food', 'drinks', 'flowers', 'balloon']


def test_plan_benefits_slugs_all(db_connection, plan_basic, plan_top):
    setup_plan_hierarchy(plan_basic, plan_top)

    assert plan_top.benefits_slugs(all=False) == ['flowers', 'balloon']


def test_partnership_days_until_expires(db_connection):
    today = date(2022, 12, 24)
    partner = create_partner(1)
    partnership = create_partnership(partner, date(2020, 12, 1), date(2023, 1, 15))

    assert partnership.days_until_expires(today=today) == 22


def test_partnership_evaluate_benefits_registry(db_connection):
    partner = create_partner(1)
    plan = create_plan('awesome', ['foo', 'bar', 'moo', 'wow'])
    partnership = create_partnership(partner, date(2020, 12, 1), date(2023, 1, 15),
                                     plan=plan,
                                     benefits_registry=[
                                        dict(slug='foo', done=True),
                                        dict(slug='bar', done=False),
                                        dict(slug='moo'),
                                     ])

    assert partnership.evaluate_benefits() == [
        dict(slug='foo', icon='foo-circle', text="Benefit 'foo'", done=True),
        dict(slug='bar', icon='bar-circle', text="Benefit 'bar'", done=False),
        dict(slug='moo', icon='moo-circle', text="Benefit 'moo'", done=False),
        dict(slug='wow', icon='wow-circle', text="Benefit 'wow'", done=False),
    ]


def test_partnership_evaluate_benefits_registry_urls(db_connection):
    partner = create_partner(1)
    plan = create_plan('awesome', ['foo'])
    partnership = create_partnership(partner, date(2020, 12, 1), date(2023, 1, 15),
                                     plan=plan,
                                     benefits_registry=[
                                        dict(slug='foo', done='https://example.com'),
                                     ])

    assert partnership.evaluate_benefits() == [
        dict(slug='foo', icon='foo-circle', text="Benefit 'foo'", done='https://example.com'),
    ]


def test_partnership_evaluate_benefits_evaluators(db_connection):
    partner = create_partner(1)
    plan = create_plan('awesome', ['foo', 'bar', 'moo', 'wow'])
    partnership = create_partnership(partner, date(2020, 12, 1), date(2023, 1, 15),
                                     plan=plan)
    evaluators = dict(foo=lambda partnership: True,
                     wow=lambda partnership: False)

    assert partnership.evaluate_benefits(evaluators) == [
        dict(slug='foo', icon='foo-circle', text="Benefit 'foo'", done=True),
        dict(slug='bar', icon='bar-circle', text="Benefit 'bar'", done=False),
        dict(slug='moo', icon='moo-circle', text="Benefit 'moo'", done=False),
        dict(slug='wow', icon='wow-circle', text="Benefit 'wow'", done=False),
    ]


def test_partnership_evaluate_benefits_registry_overrides_evaluators(db_connection):
    partner = create_partner(1)
    plan = create_plan('awesome', ['foo', 'moo'])
    partnership = create_partnership(partner, date(2020, 12, 1), date(2023, 1, 15),
                                     plan=plan,
                                     benefits_registry=[
                                        dict(slug='foo', done=True),
                                        dict(slug='moo', done=False),
                                     ])
    evaluators = dict(foo=lambda partnership: False,
                     moo=lambda partnership: True)

    assert partnership.evaluate_benefits(evaluators) == [
        dict(slug='foo', icon='foo-circle', text="Benefit 'foo'", done=True),
        dict(slug='moo', icon='moo-circle', text="Benefit 'moo'", done=False),
    ]


def test_partnership_active_listing(db_connection):
    today = date(2021, 5, 2)
    partnership1 = create_partnership(create_partner(1), today, date(2021, 4, 1))  # noqa
    partnership2 = create_partnership(create_partner(2), today, date(2021, 5, 1))  # noqa
    partnership3 = create_partnership(create_partner(3), today, date(2021, 5, 2))
    partnership4 = create_partnership(create_partner(4), today, date(2021, 5, 3))

    assert set(Partnership.active_listing(today=today)) == {partnership3, partnership4}


def test_partnership_active_listing_with_barters(db_connection):
    today = date(2021, 5, 1)
    partnership1 = create_partnership(create_partner(1), today, date(2021, 5, 1))
    partnership2 = create_partnership(create_partner(2), today, None)

    assert set(Partnership.active_listing(today=today)) == {partnership1, partnership2}


def test_partnership_active_listing_without_barters(db_connection):
    today = date(2021, 5, 1)
    partnership1 = create_partnership(create_partner(1), today, date(2021, 5, 1))
    partnership2 = create_partnership(create_partner(2), today, None)  # noqa

    assert set(Partnership.active_listing(today=today, include_barters=False)) == {partnership1}


def test_partnership_active_listing_skips_planned(db_connection):
    today = date(2021, 5, 2)
    partnership1 = create_partnership(create_partner(1), date(2021, 5, 1), None)
    partnership2 = create_partnership(create_partner(2), date(2021, 5, 2), None)
    partnership3 = create_partnership(create_partner(3), date(2021, 5, 3), None)  # noqa

    assert set(Partnership.active_listing(today=today)) == {partnership1, partnership2}


def test_partnership_active_listing_sorts_by_hierarchy_rank_then_by_name(db_connection, plan_basic, plan_top):
    setup_plan_hierarchy(plan_basic, plan_top)
    today = date(2021, 5, 2)
    partnership1 = create_partnership(create_partner(1, name='C'), date(2021, 4, 1), None, plan=plan_basic)
    partnership2 = create_partnership(create_partner(2, name='B'), date(2021, 4, 2), None, plan=plan_top)
    partnership3 = create_partnership(create_partner(3, name='A'), date(2021, 4, 3), None, plan=plan_basic)

    assert list(Partnership.active_listing(today=today)) == [partnership2, partnership3, partnership1]


def test_partnership_active_listing_multiple_partnerships(db_connection):
    today = date(2023, 6, 1)
    partner1 = create_partner(1)
    partnership_a = create_partnership(partner1, date(2023, 2, 1), date(2023, 5, 1))  # noqa
    partnership_b = create_partnership(partner1, date(2023, 5, 15), None)

    assert list(Partnership.active_listing(today=today)) == [partnership_b]


def test_partnership_handbook_listing(db_connection, plan_basic, plan_handbook):
    partner1 = create_partner(1)
    partnership1 = create_partnership(partner1, date(2023, 1, 1), None, plan=plan_basic)  # noqa
    partner2 = create_partner(2)
    partnership2 = create_partnership(partner2, date(2023, 1, 1), None, plan=plan_handbook)
    partner3 = create_partner(3)
    partnership3 = create_partnership(partner3, date(2023, 1, 1), None, plan=plan_basic)  # noqa

    assert list(Partnership.handbook_listing()) == [partnership2]


def test_partnership_handbook_listing_sorts_by_name(db_connection, plan_handbook):
    partner1 = create_partner(1, name='Orange')
    partnership1 = create_partnership(partner1, date(2023, 1, 1), None, plan=plan_handbook)
    partner2 = create_partner(2, name='Banana')
    partnership2 = create_partnership(partner2, date(2023, 1, 1), None, plan=plan_handbook)
    partner3 = create_partner(3, name='Apple')
    partnership3 = create_partnership(partner3, date(2023, 1, 1), None, plan=plan_handbook)

    assert list(Partnership.handbook_listing()) == [partnership3, partnership2, partnership1]
