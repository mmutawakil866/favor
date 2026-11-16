import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.utils import timezone

from apps.dashboard.views import report_summary


def call(user, query=""):
    request = RequestFactory().get("/api/reports/summary/" + query)
    request.user = user
    return report_summary(request)


@pytest.fixture
def customer(db):
    return get_user_model().objects.create_user(username="ama", password="x")


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_user(username="kofi", password="x", is_staff=True)


def test_anonymous_gets_401():
    assert call(AnonymousUser()).status_code == 401


def test_customer_gets_403(customer):
    assert call(customer).status_code == 403


def test_staff_gets_report_json(staff, customer):
    from tests.stubs.orders.models import Order
    Order.objects.create(reference="ORD-V1", customer=customer, status="DELIVERED", total=Decimal("80"),
                         placed_at=timezone.now() - timedelta(days=1))
    response = call(staff)
    body = json.loads(response.content)
    assert response.status_code == 200
    assert body["sales"]["revenue"] == "80.00" and body["sales"]["delivered_count"] == 1


def test_bad_date_returns_400(staff):
    assert call(staff, "?date_from=not-a-date").status_code == 400


def test_reversed_range_returns_400(staff):
    assert call(staff, "?date_from=2026-11-10&date_to=2026-11-01").status_code == 400


def test_unknown_status_returns_400(staff):
    assert call(staff, "?status=SHIPPED").status_code == 400


def test_post_is_rejected(staff):
    request = RequestFactory().post("/api/reports/summary/")
    request.user = staff
    assert report_summary(request).status_code == 405