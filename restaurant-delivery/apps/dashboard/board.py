"""Data feed for the staff live-order board. Read-only; all names come from the adapter."""
from collections import defaultdict
from datetime import datetime, time

from django.db.models import DateTimeField, F, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps import dev5_adapter as ad

ITEMS_SHOWN = 3


def _customer_name(user):
    if user is None:
        return ""
    return (user.get_full_name() or user.get_username()).strip()


def _status_since():
    """When the order entered its current status: the newest matching history row,
    falling back to the time it was placed."""
    latest = (
        ad.history_model().objects
        .filter(**{ad.HISTORY_ORDER: OuterRef("pk"), ad.HISTORY_STATUS: OuterRef(ad.ORDER_STATUS_FIELD)})
        .order_by(f"-{ad.HISTORY_CREATED_AT}")
        .values(ad.HISTORY_CREATED_AT)[:1]
    )
    return Coalesce(Subquery(latest), F(ad.ORDER_PLACED_AT), output_field=DateTimeField())


def _items_by_order(order_ids):
    rows = ad.order_item_model().objects.filter(**{f"{ad.ITEM_ORDER}__in": order_ids}).values_list(
        f"{ad.ITEM_ORDER}_id", ad.ITEM_NAME, ad.ITEM_QUANTITY).order_by("pk")
    grouped = defaultdict(list)
    for order_id, name, qty in rows:
        grouped[order_id].append(f"{qty} x {name}")
    return grouped


def board_snapshot(now=None):
    now = now or timezone.now()
    orders = list(
        ad.order_model().objects
        .filter(**{f"{ad.ORDER_STATUS_FIELD}__in": ad.BOARD_STATUSES})
        .select_related(ad.ORDER_CUSTOMER)
        .annotate(status_since=_status_since())
        .order_by(ad.ORDER_PLACED_AT)
    )
    items = _items_by_order([o.pk for o in orders])
    columns = {status: [] for status in ad.BOARD_STATUSES}
    for o in orders:
        status = getattr(o, ad.ORDER_STATUS_FIELD)
        lines = items.get(o.pk, [])
        columns[status].append({
            "reference": getattr(o, ad.ORDER_REFERENCE),
            "status": status,
            "customer": _customer_name(getattr(o, ad.ORDER_CUSTOMER)),
            "items": lines[:ITEMS_SHOWN],
            "more_items": max(0, len(lines) - ITEMS_SHOWN),
            "total": getattr(o, ad.ORDER_TOTAL),
            "payment_method": getattr(o, ad.ORDER_PAYMENT_METHOD),
            "city": getattr(o, ad.ORDER_CITY, "") or "",
            "age_seconds": max(0, int((now - o.status_since).total_seconds())),
            "late_after_minutes": ad.LATE_AFTER_MINUTES.get(status),
            "next_label": ad.STAFF_NEXT_LABEL.get(status),
        })
    midnight = timezone.make_aware(datetime.combine(timezone.localdate(now), time.min))
    today = ad.order_model().objects.filter(**{f"{ad.ORDER_PLACED_AT}__gte": midnight})
    return {
        "server_time": now,
        "columns": [{"status": s, "label": ad.BOARD_LABELS[s], "orders": columns[s]} for s in ad.BOARD_STATUSES],
        "today": {
            "delivered": today.filter(**{ad.ORDER_STATUS_FIELD: ad.ORDER_DELIVERED_STATUS}).count(),
            "cancelled": today.filter(**{ad.ORDER_STATUS_FIELD: ad.ORDER_CANCELLED_STATUS}).count(),
        },
    }