from urllib.parse import urlparse

import pytest
from django.conf import settings
from django.contrib.sites.models import Site
from post_office.models import EmailTemplate
from pytest_django.lazy_django import skip_if_no_django

from admission.constants import INTERVIEW_REMINDER_TEMPLATE, \
    INTERVIEW_FEEDBACK_TEMPLATE, APPOINTMENT_INVITATION_TEMPLATE
from core.models import City
from core.tests.utils import TestClient, TEST_DOMAIN, CSCTestCase
from learning.models import Branch
from learning.settings import Branches
from notifications.models import Type
from users.tests.factories import UserFactory


@pytest.fixture()
def client():
    """Customize login method for Django test client."""
    skip_if_no_django()
    return TestClient()


@pytest.fixture(scope="session")
def assert_redirect():
    """Uses customized TestCase.assertRedirects as a comparing tool."""
    _TC = CSCTestCase()

    def wrapper(*args, **kwargs):
        return _TC.assertRedirects(*args, **kwargs)

    return wrapper


@pytest.fixture(scope="function")
def assert_login_redirect(client, settings, assert_redirect):
    def wrapper(url, form=None, **kwargs):
        method_name = kwargs.pop("method", "get")
        client_method = getattr(client, method_name)
        # Cast `next` value to the relative path since
        # after successful login we redirect to the same domain.
        path = urlparse(url).path
        expected_path = "{}?next={}".format(settings.LOGIN_URL, path)
        assert_redirect(client_method(url, form, **kwargs), expected_path)
    return wrapper


@pytest.fixture(scope="function")
def curator():
    return UserFactory.create(is_superuser=True, is_staff=True)


@pytest.fixture(scope="session", autouse=True)
def _prepopulate_db_with_data(django_db_setup, django_db_blocker):
    """
    Populates test database with missing data required for tests.

    To simplify db management migrations could be recreated from the scratch
    without already applied data migrations. Restore these data in one place
    since some tests rely on it.
    """
    with django_db_blocker.unblock():
        # Create sites
        Site.objects.update_or_create(
            id=settings.CENTER_SITE_ID,
            defaults={
                "domain": TEST_DOMAIN,
                "name": TEST_DOMAIN
            }
        )
        Site.objects.update_or_create(
            id=settings.CLUB_SITE_ID,
            defaults={
                "domain": "compsciclub.ru",
                "name": "compsciclub.ru"
            }
        )

        # Create cities
        City.objects.update_or_create(
            code="spb",
            defaults={
                "name": "Saint Petersburg",
                "abbr": "spb"
            }
        )

        City.objects.update_or_create(
            code="kzn",
            defaults={
                "name": "Kazan",
                "abbr": "kzn"
            }
        )

        City.objects.update_or_create(
            code="nsk",
            defaults={
                "name": "Novosibirsk",
                "abbr": "nsk"
            }
        )

        branch, _ = Branch.objects.update_or_create(
            code=Branches.SPB,
            defaults={
                "name": 'Санкт-Петербург',
                "is_remote": False,
            }
        )

        branch, _ = Branch.objects.update_or_create(
            code=Branches.NSK,
            defaults={
                "name": 'Новосибирск',
                "is_remote": False,
            }
        )

        branch, _ = Branch.objects.update_or_create(
            code=Branches.DISTANCE,
            defaults={
                "name": 'Заочное',
                "is_remote": True,
            }
        )

        from notifications import NotificationTypes
        for t in NotificationTypes:
            Type.objects.update_or_create(
                id=t.value,
                defaults={
                    "code": t.name
                }
            )

        # Create email templates

        template_names = (
            APPOINTMENT_INVITATION_TEMPLATE,
            INTERVIEW_FEEDBACK_TEMPLATE,
            INTERVIEW_REMINDER_TEMPLATE,
        )
        for template_name in template_names:
            EmailTemplate.objects.update_or_create(
                name=template_name
            )
