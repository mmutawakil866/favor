"""
The ONLY place Dev 5 code touches other developers' models and field names.

Everything below is a placeholder until Dev 1 (User, menu) and Dev 3 (orders,
payments) finalise their models. When they do, edit this file and nothing else.
"""
from decimal import Decimal

from django.apps import apps
from django.conf import settings

# --- Dev 3: orders. Names below are taken from docs/schema.sql ---------------
ORDER_STATUSES = ("PENDING", "CONFIRMED", "PREPARING", "READY_FOR_PICKUP",
                  "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED")
PAYMENT_STATUSES = ("PENDING", "SUCCESS", "FAILED", "REFUNDED")  # note SUCCESS, not PAID
ORDER_DELIVERED_STATUS = "DELIVERED"
ORDER_CANCELLED_STATUS = "CANCELLED"
ORDER_OWNER_FIELD = "customer_id"      # attribute holding the ordering user's pk
ORDER_STATUS_FIELD = "status"
ORDER_SUBTOTAL_FIELD = "subtotal"
ORDER_DELIVERY_FEE_FIELD = "delivery_fee"


def order_owner_id(order):
    return getattr(order, ORDER_OWNER_FIELD)


def order_status(order):
    return getattr(order, ORDER_STATUS_FIELD)


def order_is_delivered(order):
    return order_status(order) == ORDER_DELIVERED_STATUS


def order_subtotal(order):
    return Decimal(str(getattr(order, ORDER_SUBTOTAL_FIELD)))


def order_delivery_fee(order):
    return Decimal(str(getattr(order, ORDER_DELIVERY_FEE_FIELD)))


# --- Team decision pending: Ghana/GHS vs the schema's Nigeria/NGN -----------
def currency_code():
    return getattr(settings, "CURRENCY_CODE", "GHS")


# =============================================================================
# Reporting (apps.dashboard). Models are looked up lazily by (app label, name).
# Field names are Django field names; the schema columns are in the comments.
# =============================================================================
ORDER_MODEL = ("orders", "Order")
ORDER_ITEM_MODEL = ("orders", "OrderItem")
DELIVERY_MODEL = ("delivery", "Delivery")


def order_model():
    return apps.get_model(*ORDER_MODEL)


def order_item_model():
    return apps.get_model(*ORDER_ITEM_MODEL)


def delivery_model():
    return apps.get_model(*DELIVERY_MODEL)


# orders_order
ORDER_PLACED_AT = "placed_at"
ORDER_TOTAL = "total"
ORDER_DISCOUNT = "discount_total"
ORDER_PAYMENT_METHOD = "payment_method"
# orders_orderitem
ITEM_ORDER = "order"                   # order_id
ITEM_FOOD = "fooditem"                 # fooditem_id (nullable: item may be deleted later)
ITEM_NAME = "name_snapshot"
ITEM_QUANTITY = "quantity"
ITEM_LINE_TOTAL = "line_total"
# delivery_delivery
DELIVERY_ORDER = "order"               # order_id
DELIVERY_STATUS = "status"
DELIVERY_ASSIGNED_AT = "assigned_at"
DELIVERY_ACCEPTED_AT = "accepted_at"      # added by Dev 4; picked_up_at is the delivery-start time
DELIVERY_PICKED_UP_AT = "picked_up_at"
DELIVERY_DELIVERED_AT = "delivered_at"
DELIVERY_FAILED_STATUS = "FAILED"
DELIVERY_CANCELLED_STATUS = "CANCELLED"
# Confirmed by Dev 4 on 16 Nov 2026 (schema.sql lists fewer):
DELIVERY_STATUSES = ("ASSIGNED", "ACCEPTED", "PICKED_UP", "IN_TRANSIT", "DELIVERED", "FAILED", "CANCELLED")
DELIVERY_DELIVERED_STATUS = "DELIVERED"


# --- Dev 1: who may open the dashboard (roles: CUSTOMER, STAFF, RIDER, ADMIN) --
def is_dashboard_user(user):
    """Placeholder: Django staff flag, or a `role` of STAFF/ADMIN once Dev 1 adds it."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return bool(getattr(user, "is_staff", False) or getattr(user, "role", None) in ("STAFF", "ADMIN"))

# =============================================================================
# Live order board (apps.dashboard.board). Placeholders until Dev 3 confirms.
# =============================================================================
from importlib import import_module  # noqa: E402

from django.core.exceptions import PermissionDenied, ValidationError  # noqa: E402

HISTORY_MODEL = ("orders", "OrderStatusHistory")   # orders_orderstatushistory
HISTORY_ORDER = "order"
HISTORY_STATUS = "status"
HISTORY_CREATED_AT = "created_at"
ORDER_REFERENCE = "reference"
ORDER_CUSTOMER = "customer"
ORDER_CITY = "delivery_city"

BOARD_STATUSES = ("PENDING", "CONFIRMED", "PREPARING", "READY_FOR_PICKUP", "OUT_FOR_DELIVERY")
BOARD_LABELS = {"PENDING": "New", "CONFIRMED": "Confirmed", "PREPARING": "Preparing",
                "READY_FOR_PICKUP": "Ready", "OUT_FOR_DELIVERY": "On the way"}
# Kitchen steps staff may advance from the board. Later steps belong to riders (Dev 4).
STAFF_NEXT_STATUS = {"PENDING": "CONFIRMED", "CONFIRMED": "PREPARING", "PREPARING": "READY_FOR_PICKUP"}
STAFF_NEXT_LABEL = {"PENDING": "Confirm order", "CONFIRMED": "Start preparing", "PREPARING": "Mark ready"}
LATE_AFTER_MINUTES = {"PENDING": 5, "CONFIRMED": 5, "PREPARING": 25, "READY_FOR_PICKUP": 10, "OUT_FOR_DELIVERY": 45}
BOARD_POLL_SECONDS = 10

ORDER_SERVICES_MODULE = "apps.orders.services"     # Dev 3: module and function names not confirmed


class OrderServiceUnavailable(Exception):
    pass


def history_model():
    return apps.get_model(*HISTORY_MODEL)


def find_order(reference):
    return order_model().objects.filter(**{ORDER_REFERENCE: reference}).first()


def _order_services():
    try:
        return import_module(ORDER_SERVICES_MODULE)
    except ImportError as exc:
        raise OrderServiceUnavailable("The order service is not available yet.") from exc


def update_order_status(*, order, new_status, actor, note=""):
    fn = getattr(_order_services(), "update_order_status", None)
    if fn is None:
        raise OrderServiceUnavailable("The order service is not available yet.")
    return fn(order=order, new_status=new_status, actor=actor, note=note)


def order_transition_errors():
    errors = [ValidationError, PermissionDenied]
    try:
        bad = getattr(_order_services(), "InvalidOrderTransition", None)
    except OrderServiceUnavailable:
        bad = None
    if bad:
        errors.append(bad)
    return tuple(errors)