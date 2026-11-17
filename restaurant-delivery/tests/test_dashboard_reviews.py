from datetime import date, datetime, timedelta
from itertools import count

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.utils import timezone

from apps import dev5_adapter as ad
from apps.dashboard import review_moderation as rm
from apps.dashboard import review_views as rv
from apps.dashboard.reports import ReportFilter
from apps.reviews.models import Review

_n = count(1)


@pytest.fixture
def customer(db):
    return get_user_model().objects.create_user(username="ama", password="x", first_name="Ama", last_name="Mensah")


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_user(username="kofi", password="x", is_staff=True)


@pytest.fixture
def admin(db):
    return get_user_model().objects.create_user(username="boss", password="x", is_staff=True, is_superuser=True,
                                                first_name="Efua", last_name="Boateng")


@pytest.fixture
def make_review(customer):
    from tests.stubs.orders.models import Order

    def make(rating="GOOD", comment="Nice", visible=True, created=None, order_ref=None):
        i = next(_n)
        order = Order.objects.create(reference=order_ref or f"ORD-R{i}", customer=customer, status="DELIVERED")
        r = Review.objects.create(order_id=order.pk, customer=customer, overall_rating=rating, food_rating=rating,
                                  service_rating=rating, comment=comment, is_visible=visible)
        if created:
            Review.objects.filter(pk=r.pk).update(created_at=created)
        return r
    return make


# --- read side -------------------------------------------------------------
def test_page_serializes_reviews_with_order_reference_and_names(make_review):
    make_review("EXCELLENT", "Great jollof", order_ref="ORD-77")
    data = rm.review_page(rm.review_queryset())
    row = data["results"][0]
    assert row["order_reference"] == "ORD-77" and row["customer"] == "Ama Mensah"
    assert row["overall"] == {"value": "EXCELLENT", "label": "Excellent", "score": 5}


def test_visibility_filter(make_review):
    make_review(visible=True); make_review(visible=False)
    assert rm.review_page(rm.review_queryset("visible"))["count"] == 1
    assert rm.review_page(rm.review_queryset("hidden"))["count"] == 1
    assert rm.review_page(rm.review_queryset("all"))["count"] == 2


def test_rating_and_search_filters(make_review):
    make_review("VERY_BAD", "Food was cold"); make_review("GOOD", "Hot and fresh"); make_review("BAD", "Cold rice")
    assert rm.review_page(rm.review_queryset(ratings=("VERY_BAD", "BAD")))["count"] == 2
    assert rm.review_page(rm.review_queryset(q="cold"))["count"] == 2
    assert rm.review_page(rm.review_queryset(ratings=("BAD",), q="cold"))["count"] == 1


def test_date_range_filter(make_review):
    tz = timezone.get_current_timezone()
    make_review(created=timezone.make_aware(datetime(2026, 11, 2, 12), tz))
    make_review(created=timezone.make_aware(datetime(2026, 11, 20, 12), tz))
    flt = ReportFilter(date(2026, 11, 10), date(2026, 11, 30))
    assert rm.review_page(rm.review_queryset(flt=flt))["count"] == 1


def test_pagination(make_review):
    for _ in range(25):
        make_review()
    first = rm.review_page(rm.review_queryset(), 1)
    second = rm.review_page(rm.review_queryset(), 2)
    assert first["pages"] == 2 and len(first["results"]) == 20 and len(second["results"]) == 5
    assert rm.review_page(rm.review_queryset(), 99)["page"] == 2     # out-of-range page falls back to the last


def test_summary_counts_visible_only_and_reports_hidden(make_review):
    make_review("EXCELLENT"); make_review("OKAY"); make_review("VERY_BAD", visible=False)
    data = rm.review_page(rm.review_queryset())
    assert data["summary"]["overall"] == 4.0 and data["hidden_count"] == 1


# --- access ----------------------------------------------------------------
def call(view, user, method="get", data=None, **kw):
    request = getattr(RequestFactory(), method)("/x/", data)
    request.user = user
    return view(request, **kw)


def test_feed_access(customer, staff):
    assert call(rv.reviews_feed, AnonymousUser()).status_code == 401
    assert call(rv.reviews_feed, customer).status_code == 403
    assert call(rv.reviews_feed, staff).status_code == 200


def test_feed_flags_who_can_moderate(staff, admin):
    import json
    assert json.loads(call(rv.reviews_feed, staff).content)["can_moderate"] is False
    assert json.loads(call(rv.reviews_feed, admin).content)["can_moderate"] is True


@pytest.mark.parametrize("query", [{"visibility": "secret"}, {"rating": "AMAZING"}, {"date_from": "nope"},
                                   {"date_from": "2026-12-01", "date_to": "2026-11-01"}])
def test_feed_rejects_bad_filters(staff, query):
    assert call(rv.reviews_feed, staff, data=query).status_code == 400


def test_page_access_and_moderation_flag(customer, staff, admin):
    assert call(rv.reviews_page, AnonymousUser()).status_code == 302
    assert call(rv.reviews_page, customer).status_code == 403
    assert b'id="can-moderate"' in call(rv.reviews_page, staff).content
    assert b">true<" in call(rv.reviews_page, admin).content and b">false<" in call(rv.reviews_page, staff).content


# --- hide / restore --------------------------------------------------------
def hide(user, pk, reason="Abusive language"):
    return call(rv.hide_review, user, "post", {"reason": reason}, pk=pk)


def test_admin_can_hide_and_audit_trail_is_kept(admin, make_review):
    review = make_review()
    assert hide(admin, review.pk).status_code == 200
    review.refresh_from_db()
    assert not review.is_visible and review.hidden_reason == "Abusive language"
    assert review.hidden_by_id == admin.pk and review.hidden_at
    assert Review.objects.count() == 1                       # soft hide: the row stays


def test_staff_cannot_moderate(staff, make_review):
    review = make_review()
    assert hide(staff, review.pk).status_code == 403
    review.refresh_from_db()
    assert review.is_visible


def test_customer_and_anonymous_cannot_moderate(customer, make_review):
    review = make_review()
    assert hide(customer, review.pk).status_code == 403
    assert hide(AnonymousUser(), review.pk).status_code == 401


def test_reason_is_required_and_limited(admin, make_review):
    review = make_review()
    assert hide(admin, review.pk, reason="   ").status_code == 400
    assert hide(admin, review.pk, reason="x" * 201).status_code == 400
    assert hide(admin, review.pk, reason="x" * 200).status_code == 200


def test_hiding_twice_is_409_and_keeps_first_reason(admin, make_review):
    review = make_review()
    hide(admin, review.pk, "First reason")
    assert hide(admin, review.pk, "Second reason").status_code == 409
    review.refresh_from_db()
    assert review.hidden_reason == "First reason"


def test_restore(admin, make_review):
    review = make_review(visible=False)
    assert call(rv.restore_review, admin, "post", pk=review.pk).status_code == 200
    review.refresh_from_db()
    assert review.is_visible and review.hidden_by is None and review.hidden_reason == ""


def test_restore_visible_review_is_409(admin, make_review):
    assert call(rv.restore_review, admin, "post", pk=make_review().pk).status_code == 409


def test_unknown_review_is_404(admin):
    assert hide(admin, 9999).status_code == 404


def test_moderation_requires_post(admin, make_review):
    assert call(rv.hide_review, admin, "get", pk=make_review().pk).status_code == 405


def test_adapter_admin_rule(staff, admin, customer):
    assert ad.is_admin_user(admin) and not ad.is_admin_user(staff) and not ad.is_admin_user(customer)