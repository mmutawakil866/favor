from datetime import date, datetime, timedelta
from decimal import Decimal
from itertools import count
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.dashboard import reports
from apps.dashboard.reports import ReportFilter
from apps.reviews.models import Review

D = Decimal
_ref = count(1)


def at(day, hour=12):
    return timezone.make_aware(datetime(2026, 11, day, hour, 0))


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="ama", password="x")


@pytest.fixture
def make_order(user):
    from tests.stubs.orders.models import Order

    def make(status="DELIVERED", total="100", day=10, hour=12, method="CARD", discount="0", fee="10", **kw):
        return Order.objects.create(
            reference=f"ORD-{next(_ref)}", customer=user, status=status, payment_method=method,
            subtotal=D(total) - D(fee), discount_total=D(discount), delivery_fee=D(fee), total=D(total),
            placed_at=at(day, hour), **kw)
    return make


@pytest.fixture
def add_item(db):
    from tests.stubs.menu.models import FoodItem
    from tests.stubs.orders.models import OrderItem

    def add(order, name, qty, price="20"):
        food, _ = FoodItem.objects.get_or_create(name=name, defaults={"price": D(price)})
        return OrderItem.objects.create(order=order, fooditem=food, name_snapshot=name,
                                        unit_price=D(price), quantity=qty, line_total=D(price) * qty)
    return add


ALL = ReportFilter(date(2026, 11, 1), date(2026, 11, 30))


# --- filter ----------------------------------------------------------------
def test_filter_rejects_reversed_dates():
    with pytest.raises(ValueError):
        ReportFilter(date(2026, 11, 5), date(2026, 11, 1))


def test_filter_rejects_unknown_status():
    with pytest.raises(ValueError):
        ReportFilter(statuses=("SHIPPED",))


# --- sales summary ---------------------------------------------------------
def test_revenue_counts_only_delivered_orders(make_order):
    make_order("DELIVERED", total="100", discount="5")
    make_order("DELIVERED", total="50")
    make_order("PENDING", total="999")
    make_order("CANCELLED", total="999")
    s = reports.sales_summary(ALL)
    assert s["revenue"] == D("150.00")
    assert s["delivered_count"] == 2
    assert s["orders_count"] == 3          # cancelled orders are not in orders_count
    assert s["cancelled_count"] == 1
    assert s["average_order_value"] == D("75.00")
    assert s["discounts_total"] == D("5.00")
    assert s["delivery_fees_total"] == D("20.00")
    assert s["currency"] == "GHS"


def test_empty_period_is_all_zero(db):
    s = reports.sales_summary(ALL)
    assert s["revenue"] == D("0.00") and s["average_order_value"] == D("0.00") and s["orders_count"] == 0


def test_date_range_is_inclusive_of_last_day_and_excludes_next(make_order):
    make_order(day=5, hour=23)     # last day, late evening: included
    make_order(day=6, hour=0)      # next day: excluded
    make_order(day=4, hour=23)     # day before: excluded
    flt = ReportFilter(date(2026, 11, 5), date(2026, 11, 5))
    assert reports.sales_summary(flt)["delivered_count"] == 1


def test_open_ended_range_returns_everything(make_order):
    make_order(day=1)
    make_order(day=28)
    assert reports.sales_summary(ReportFilter())["delivered_count"] == 2


def test_status_filter_limits_counts(make_order):
    make_order("DELIVERED")
    make_order("PREPARING")
    flt = ReportFilter(date(2026, 11, 1), date(2026, 11, 30), statuses=("PREPARING",))
    s = reports.sales_summary(flt)
    assert s["orders_count"] == 1 and s["revenue"] == D("0.00")


# --- daily / status / payment method --------------------------------------
def test_daily_sales_groups_by_day(make_order):
    make_order("DELIVERED", total="100", day=3)
    make_order("DELIVERED", total="40", day=3, hour=18)
    make_order("CANCELLED", day=3)
    make_order("DELIVERED", total="60", day=4)
    rows = reports.daily_sales(ALL)
    assert [r["day"] for r in rows] == [date(2026, 11, 3), date(2026, 11, 4)]
    assert rows[0] == {"day": date(2026, 11, 3), "orders_count": 2, "cancelled_count": 1, "revenue": D("140.00")}
    assert rows[1]["revenue"] == D("60.00")


def test_orders_by_status_includes_zero_counts(make_order):
    make_order("DELIVERED")
    make_order("DELIVERED")
    make_order("CANCELLED")
    out = reports.orders_by_status(ALL)
    assert out["DELIVERED"] == 2 and out["CANCELLED"] == 1 and out["PENDING"] == 0
    assert list(out) == list(reports.ad.ORDER_STATUSES)


def test_revenue_by_payment_method_includes_cash_on_delivery(make_order):
    make_order("DELIVERED", total="120", method="CARD")
    make_order("DELIVERED", total="70", method="CASH")
    make_order("DELIVERED", total="30", method="CASH")
    make_order("PENDING", total="500", method="CASH")
    rows = reports.revenue_by_payment_method(ALL)
    assert rows == [{"payment_method": "CARD", "orders": 1, "revenue": D("120.00")},
                    {"payment_method": "CASH", "orders": 2, "revenue": D("100.00")}]


# --- popular items ---------------------------------------------------------
def test_popular_items_rank_by_units_and_skip_cancelled(make_order, add_item):
    o1, o2, o3 = make_order(), make_order("PENDING"), make_order("CANCELLED")
    add_item(o1, "Jollof and chicken", 2, "65")
    add_item(o2, "Jollof and chicken", 3, "65")
    add_item(o1, "Waakye", 4, "40")
    add_item(o3, "Banku", 50, "30")            # cancelled: must not count
    rows = reports.popular_items(ALL)
    assert [r["name"] for r in rows] == ["Jollof and chicken", "Waakye"]
    assert rows[0]["units"] == 5 and rows[0]["revenue"] == D("325.00")
    assert rows[1]["units"] == 4


def test_popular_items_limit_and_date_range(make_order, add_item):
    old = make_order(day=2)
    add_item(old, "Kelewele", 9)
    new = make_order(day=20)
    add_item(new, "Waakye", 1)
    add_item(new, "Banku", 2)
    flt = ReportFilter(date(2026, 11, 10), date(2026, 11, 30))
    rows = reports.popular_items(flt, limit=1)
    assert [r["name"] for r in rows] == ["Banku"]


# --- delivery --------------------------------------------------------------
def test_delivery_performance_averages(make_order):
    from tests.stubs.delivery.models import Delivery
    o1, o2, o3 = make_order(), make_order(), make_order("CANCELLED")
    t = at(10, 12)
    Delivery.objects.create(order=o1, status="DELIVERED", assigned_at=t,
                            picked_up_at=t + timedelta(minutes=10), delivered_at=t + timedelta(minutes=30))
    Delivery.objects.create(order=o2, status="DELIVERED", assigned_at=t,
                            picked_up_at=t + timedelta(minutes=20), delivered_at=t + timedelta(minutes=50))
    Delivery.objects.create(order=o3, status="FAILED", assigned_at=t)
    d = reports.delivery_performance(ALL)
    assert d["deliveries_count"] == 3 and d["delivered_count"] == 2 and d["failed_count"] == 1
    assert d["avg_assign_to_delivered_min"] == 40.0
    assert d["avg_pickup_to_delivered_min"] == 25.0


def test_delivery_performance_with_no_data(db):
    d = reports.delivery_performance(ALL)
    assert d["deliveries_count"] == 0 and d["avg_assign_to_delivered_min"] is None


# --- reviews ---------------------------------------------------------------
def _review(user, order_id, rating, visible=True, created=None):
    r = Review.objects.create(order_id=order_id, customer=user, overall_rating=rating, food_rating=rating,
                              service_rating=rating, is_visible=visible)
    if created:
        Review.objects.filter(pk=r.pk).update(created_at=created)
    return r


def test_review_summary_uses_visible_reviews_only(user):
    _review(user, 1, "EXCELLENT", created=at(10))
    _review(user, 2, "OKAY", created=at(11))
    _review(user, 3, "VERY_BAD", visible=False, created=at(12))
    s = reports.review_summary(ALL)
    assert s["count"] == 2 and s["overall"] == 4.0 and s["hidden_count"] == 1


def test_review_summary_respects_date_range(user):
    _review(user, 1, "EXCELLENT", created=at(2))
    _review(user, 2, "BAD", created=at(20))
    s = reports.review_summary(ReportFilter(date(2026, 11, 10), date(2026, 11, 30)))
    assert s["count"] == 1 and s["overall"] == 2.0


# --- bundle ----------------------------------------------------------------
def test_report_bundle_has_every_section(make_order):
    make_order()
    b = reports.report_bundle(ALL)
    assert set(b) == {"range", "sales", "daily", "by_status", "by_payment_method",
                      "popular_items", "delivery", "reviews"}

def test_delivery_performance_counts_cancelled_and_new_statuses(make_order):
    from tests.stubs.delivery.models import Delivery
    Delivery.objects.create(order=make_order(), status="CANCELLED")
    Delivery.objects.create(order=make_order(), status="ACCEPTED")
    Delivery.objects.create(order=make_order(), status="PICKED_UP")
    d = reports.delivery_performance(ALL)
    assert d["deliveries_count"] == 3 and d["cancelled_count"] == 1
    assert d["delivered_count"] == 0 and d["failed_count"] == 0
    assert set(reports.ad.DELIVERY_STATUSES) >= {"ACCEPTED", "PICKED_UP"}

def test_delivery_performance_avg_time_to_accept(make_order):
    from tests.stubs.delivery.models import Delivery
    t = at(10, 12)
    Delivery.objects.create(order=make_order(), status="ACCEPTED", assigned_at=t, accepted_at=t + timedelta(minutes=2))
    Delivery.objects.create(order=make_order(), status="PICKED_UP", assigned_at=t, accepted_at=t + timedelta(minutes=4))
    Delivery.objects.create(order=make_order(), status="ASSIGNED", assigned_at=t)   # not accepted yet: ignored
    assert reports.delivery_performance(ALL)["avg_assign_to_accepted_min"] == 3.0