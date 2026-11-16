from datetime import timedelta
from decimal import Decimal
from itertools import count

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.utils import timezone

from apps import dev5_adapter as ad
from apps.dashboard import board, board_views

D = Decimal
_ref = count(1)


@pytest.fixture
def customer(db):
    return get_user_model().objects.create_user(username="ama", password="x", first_name="Ama", last_name="Mensah")


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_user(username="kofi", password="x", is_staff=True)


@pytest.fixture
def make_order(customer):
    from tests.stubs.orders.models import Order

    def make(status="PENDING", minutes_ago=0, total="80", **kw):
        return Order.objects.create(reference=f"ORD-B{next(_ref)}", customer=customer, status=status,
                                    total=D(total), placed_at=timezone.now() - timedelta(minutes=minutes_ago), **kw)
    return make


def column(snapshot, status):
    return next(c for c in snapshot["columns"] if c["status"] == status)["orders"]


# --- snapshot ----------------------------------------------------------------
def test_orders_are_grouped_by_status_and_terminal_ones_hidden(make_order):
    make_order("PENDING"); make_order("PREPARING"); make_order("DELIVERED"); make_order("CANCELLED")
    snap = board.board_snapshot()
    assert [c["status"] for c in snap["columns"]] == list(ad.BOARD_STATUSES)
    assert len(column(snap, "PENDING")) == 1 and len(column(snap, "PREPARING")) == 1
    assert sum(len(c["orders"]) for c in snap["columns"]) == 2
    assert snap["today"] == {"delivered": 1, "cancelled": 1}


def test_card_fields_and_customer_name(make_order):
    make_order(delivery_city="Accra")
    card = column(board.board_snapshot(), "PENDING")[0]
    assert card["customer"] == "Ama Mensah" and card["city"] == "Accra"
    assert card["next_label"] == "Confirm order" and card["total"] == D("80")


def test_time_in_status_uses_history_not_placed_time(make_order):
    from tests.stubs.orders.models import OrderStatusHistory
    order = make_order("PREPARING", minutes_ago=60)
    OrderStatusHistory.objects.create(order=order, status="PENDING", created_at=timezone.now() - timedelta(minutes=60))
    OrderStatusHistory.objects.create(order=order, status="PREPARING", created_at=timezone.now() - timedelta(minutes=7))
    card = column(board.board_snapshot(), "PREPARING")[0]
    assert 6 * 60 <= card["age_seconds"] <= 8 * 60
    assert card["late_after_minutes"] == ad.LATE_AFTER_MINUTES["PREPARING"]


def test_age_falls_back_to_placed_time_without_history(make_order):
    make_order("PENDING", minutes_ago=3)
    card = column(board.board_snapshot(), "PENDING")[0]
    assert 2 * 60 <= card["age_seconds"] <= 4 * 60


def test_items_are_summarised(make_order):
    from tests.stubs.orders.models import OrderItem
    order = make_order()
    for n in range(5):
        OrderItem.objects.create(order=order, name_snapshot=f"Dish {n}", unit_price=D("10"), quantity=n + 1, line_total=D("10"))
    card = column(board.board_snapshot(), "PENDING")[0]
    assert card["items"] == ["1 x Dish 0", "2 x Dish 1", "3 x Dish 2"] and card["more_items"] == 2


def test_oldest_order_comes_first(make_order):
    make_order(minutes_ago=1); make_order(minutes_ago=9)
    ages = [o["age_seconds"] for o in column(board.board_snapshot(), "PENDING")]
    assert ages == sorted(ages, reverse=True)


# --- access --------------------------------------------------------------------
def call(view, user, method="get", **kw):
    request = getattr(RequestFactory(), method)("/x/", kw.pop("data", None))
    request.user = user
    return view(request, **kw)


def test_feed_requires_login_and_staff(customer, staff):
    assert call(board_views.board_feed, AnonymousUser()).status_code == 401
    assert call(board_views.board_feed, customer).status_code == 403
    assert call(board_views.board_feed, staff).status_code == 200


def test_page_redirects_anonymous_blocks_customers_and_renders_for_staff(customer, staff):
    assert call(board_views.board_page, AnonymousUser()).status_code == 302
    assert call(board_views.board_page, customer).status_code == 403
    response = call(board_views.board_page, staff)
    assert response.status_code == 200 and b'id="board"' in response.content
    assert b"/api/orders/__ref__/advance/" in response.content


# --- advance -------------------------------------------------------------------
@pytest.fixture
def fake_service(monkeypatch):
    calls = []

    def update(*, order, new_status, actor, note=""):
        calls.append((order.reference, new_status, actor.pk))
        order.status = new_status
        order.save()
    monkeypatch.setattr(ad, "update_order_status", update)
    return calls


def advance(user, reference, from_status=None):
    data = {"from_status": from_status} if from_status else {}
    return call(board_views.advance_order, user, "post", data=data, reference=reference)


def test_advance_moves_to_next_kitchen_status(staff, make_order, fake_service):
    order = make_order("PENDING")
    response = advance(staff, order.reference, "PENDING")
    assert response.status_code == 200 and fake_service == [(order.reference, "CONFIRMED", staff.pk)]


def test_advance_ignores_any_client_supplied_target(staff, make_order, fake_service):
    order = make_order("CONFIRMED")
    request = RequestFactory().post("/x/", {"from_status": "CONFIRMED", "status": "DELIVERED"})
    request.user = staff
    board_views.advance_order(request, reference=order.reference)
    assert fake_service[0][1] == "PREPARING"


def test_stale_from_status_is_rejected_so_double_clicks_cannot_skip_steps(staff, make_order, fake_service):
    order = make_order("CONFIRMED")
    assert advance(staff, order.reference, "PENDING").status_code == 409 and fake_service == []


@pytest.mark.parametrize("status", ["READY_FOR_PICKUP", "OUT_FOR_DELIVERY"])
def test_later_statuses_cannot_be_advanced_by_staff(staff, make_order, fake_service, status):
    assert advance(staff, make_order(status).reference).status_code == 400


def test_unknown_order_is_404(staff, fake_service):
    assert advance(staff, "NOPE").status_code == 404


def test_customers_cannot_advance(customer, make_order, fake_service):
    assert advance(customer, make_order().reference).status_code == 403 and fake_service == []


def test_advance_get_is_405(staff, make_order):
    assert call(board_views.advance_order, staff, "get", reference=make_order().reference).status_code == 405


def test_service_missing_returns_503(staff, make_order):
    assert advance(staff, make_order().reference).status_code == 503


def test_service_permission_denied_returns_403(staff, make_order, monkeypatch):
    def deny(**kw):
        raise PermissionDenied()
    monkeypatch.setattr(ad, "update_order_status", deny)
    assert advance(staff, make_order().reference).status_code == 403


def test_invalid_transition_returns_409_with_message(staff, make_order, monkeypatch):
    from django.core.exceptions import ValidationError

    def reject(**kw):
        raise ValidationError("Cannot confirm an unpaid card order.")
    monkeypatch.setattr(ad, "update_order_status", reject)
    response = advance(staff, make_order().reference)
    assert response.status_code == 409 and b"unpaid" in response.content