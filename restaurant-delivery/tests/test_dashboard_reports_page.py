import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from apps.dashboard.report_page_views import reports_page


def call(user, method="get"):
    request = getattr(RequestFactory(), method)("/dashboard/reports/")
    request.user = user
    return reports_page(request)


@pytest.fixture
def customer(db):
    return get_user_model().objects.create_user(username="ama", password="x")


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_user(username="kofi", password="x", is_staff=True)


def test_anonymous_is_redirected_to_login():
    assert call(AnonymousUser()).status_code == 302


def test_customer_is_forbidden(customer):
    assert call(customer).status_code == 403


def test_staff_sees_page_with_feed_url_and_status_list(staff):
    response = call(staff)
    assert response.status_code == 200
    assert b"/api/reports/summary/" in response.content and b'id="statuses"' in response.content
    assert b"READY_FOR_PICKUP" in response.content


def test_post_is_rejected(staff):
    assert call(staff, "post").status_code == 405