"""
The ONLY place Dev 5 code touches other developers' models and field names.

Everything below is a placeholder until Dev 1 (User, menu) and Dev 3 (orders,
payments) finalise their models. When they do, edit this file and nothing else.
"""
from decimal import Decimal

from django.conf import settings

# --- Dev 3: orders. Names below are taken from docs/schema.sql ---------------
ORDER_STATUSES = ("PENDING", "CONFIRMED", "PREPARING", "READY_FOR_PICKUP",
                  "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED")
PAYMENT_STATUSES = ("PENDING", "SUCCESS", "FAILED", "REFUNDED")  # note SUCCESS, not PAID
ORDER_DELIVERED_STATUS = "DELIVERED"
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