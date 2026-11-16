"""Business reports for the admin/staff dashboard.

Read-only. Every field and model name comes from apps.dev5_adapter, so when Dev 3
or Dev 4 rename something only that file changes. Rules follow docs/schema.sql:
revenue is the sum of `total` on DELIVERED orders (as in vw_daily_sales), and
cancelled orders are counted separately.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional, Tuple

from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps import dev5_adapter as ad
from apps.reviews import services as review_services
from apps.reviews.models import Review

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class ReportFilter:
    """Inclusive date range (in the project time zone) and an optional status filter."""

    date_from: Optional[date] = None
    date_to: Optional[date] = None
    statuses: Optional[Tuple[str, ...]] = None

    def __post_init__(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        for status in self.statuses or ():
            if status not in ad.ORDER_STATUSES:
                raise ValueError(f"Unknown order status: {status}")

    def bounds(self):
        """(start, end) as aware datetimes; end is exclusive. Either may be None."""
        tz = timezone.get_current_timezone()
        start = end = None
        if self.date_from:
            start = timezone.make_aware(datetime.combine(self.date_from, time.min), tz)
        if self.date_to:
            end = timezone.make_aware(datetime.combine(self.date_to + timedelta(days=1), time.min), tz)
        return start, end


def _range_kwargs(prefix, field, flt):
    start, end = flt.bounds()
    kw = {}
    if start:
        kw[f"{prefix}{field}__gte"] = start
    if end:
        kw[f"{prefix}{field}__lt"] = end
    return kw


def _orders(flt):
    qs = ad.order_model().objects.filter(**_range_kwargs("", ad.ORDER_PLACED_AT, flt))
    if flt.statuses:
        qs = qs.filter(**{f"{ad.ORDER_STATUS_FIELD}__in": flt.statuses})
    return qs


def _delivered(qs):
    return qs.filter(**{ad.ORDER_STATUS_FIELD: ad.ORDER_DELIVERED_STATUS})


def _cancelled_q():
    return Q(**{ad.ORDER_STATUS_FIELD: ad.ORDER_CANCELLED_STATUS})


def _money(value):
    return Decimal(value or 0).quantize(Decimal("0.01"))


def sales_summary(flt):
    qs = _orders(flt)
    agg = _delivered(qs).aggregate(
        revenue=Sum(ad.ORDER_TOTAL), discounts=Sum(ad.ORDER_DISCOUNT),
        fees=Sum(ad.ORDER_DELIVERY_FEE_FIELD), delivered=Count("pk"),
    )
    revenue, delivered = _money(agg["revenue"]), agg["delivered"]
    return {
        "orders_count": qs.exclude(_cancelled_q()).count(),
        "cancelled_count": qs.filter(_cancelled_q()).count(),
        "delivered_count": delivered,
        "revenue": revenue,
        "average_order_value": _money(revenue / delivered) if delivered else ZERO,
        "discounts_total": _money(agg["discounts"]),
        "delivery_fees_total": _money(agg["fees"]),
        "currency": ad.currency_code(),
    }


def daily_sales(flt):
    rows = (
        _orders(flt)
        .annotate(day=TruncDate(ad.ORDER_PLACED_AT))
        .values("day")
        .annotate(
            orders_count=Count("pk", filter=~_cancelled_q()),
            cancelled_count=Count("pk", filter=_cancelled_q()),
            revenue=Sum(ad.ORDER_TOTAL, filter=Q(**{ad.ORDER_STATUS_FIELD: ad.ORDER_DELIVERED_STATUS})),
        )
        .order_by("day")
    )
    return [{**r, "revenue": _money(r["revenue"])} for r in rows]


def orders_by_status(flt):
    counts = dict(
        _orders(flt).values_list(ad.ORDER_STATUS_FIELD).annotate(n=Count("pk")).order_by()
    )
    return {status: counts.get(status, 0) for status in ad.ORDER_STATUSES}


def revenue_by_payment_method(flt):
    rows = (
        _delivered(_orders(flt))
        .values(ad.ORDER_PAYMENT_METHOD)
        .annotate(orders=Count("pk"), revenue=Sum(ad.ORDER_TOTAL))
        .order_by("-revenue")
    )
    return [
        {"payment_method": r[ad.ORDER_PAYMENT_METHOD], "orders": r["orders"], "revenue": _money(r["revenue"])}
        for r in rows
    ]


def popular_items(flt, limit=10):
    """Best sellers by units, excluding cancelled orders. Grouped by food item and
    the name it was sold under (the snapshot), so renames show up as separate rows."""
    order_path = ad.ITEM_ORDER
    kw = _range_kwargs(f"{order_path}__", ad.ORDER_PLACED_AT, flt)
    qs = ad.order_item_model().objects.filter(**kw).exclude(
        **{f"{order_path}__{ad.ORDER_STATUS_FIELD}": ad.ORDER_CANCELLED_STATUS}
    )
    if flt.statuses:
        qs = qs.filter(**{f"{order_path}__{ad.ORDER_STATUS_FIELD}__in": flt.statuses})
    rows = (
        qs.values(f"{ad.ITEM_FOOD}_id", ad.ITEM_NAME)
        .annotate(units=Sum(ad.ITEM_QUANTITY), revenue=Sum(ad.ITEM_LINE_TOTAL))
        .order_by("-units", ad.ITEM_NAME)[:limit]
    )
    return [
        {"fooditem_id": r[f"{ad.ITEM_FOOD}_id"], "name": r[ad.ITEM_NAME],
         "units": r["units"], "revenue": _money(r["revenue"])}
        for r in rows
    ]


def _minutes(start, end):
    return (end - start).total_seconds() / 60


def _avg(values):
    return round(sum(values) / len(values), 1) if values else None


def delivery_performance(flt):
    kw = _range_kwargs(f"{ad.DELIVERY_ORDER}__", ad.ORDER_PLACED_AT, flt)
    qs = ad.delivery_model().objects.filter(**kw)
    if flt.statuses:
        qs = qs.filter(**{f"{ad.DELIVERY_ORDER}__{ad.ORDER_STATUS_FIELD}__in": flt.statuses})
    rows = list(qs.values_list(ad.DELIVERY_STATUS, ad.DELIVERY_ASSIGNED_AT,
                               ad.DELIVERY_PICKED_UP_AT, ad.DELIVERY_DELIVERED_AT, ad.DELIVERY_ACCEPTED_AT))
    done = [r for r in rows if r[0] == ad.DELIVERY_DELIVERED_STATUS and r[3]]
    return {
        "deliveries_count": len(rows),
        "delivered_count": len(done),
        "failed_count": sum(1 for r in rows if r[0] == ad.DELIVERY_FAILED_STATUS),
        "cancelled_count": sum(1 for r in rows if r[0] == ad.DELIVERY_CANCELLED_STATUS),
        "avg_assign_to_delivered_min": _avg([_minutes(r[1], r[3]) for r in done if r[1]]),
        "avg_pickup_to_delivered_min": _avg([_minutes(r[2], r[3]) for r in done if r[2]]),
        "avg_assign_to_accepted_min": _avg([_minutes(r[1], r[4]) for r in rows if r[1] and r[4]]),
    }


def review_summary(flt):
    qs = Review.objects.filter(**_range_kwargs("", "created_at", flt))
    summary = review_services.average_ratings(qs.filter(is_visible=True))
    summary["hidden_count"] = qs.filter(is_visible=False).count()
    return summary


def report_bundle(flt, popular_limit=10):
    return {
        "range": {"date_from": flt.date_from, "date_to": flt.date_to,
                  "statuses": list(flt.statuses) if flt.statuses else None},
        "sales": sales_summary(flt),
        "daily": daily_sales(flt),
        "by_status": orders_by_status(flt),
        "by_payment_method": revenue_by_payment_method(flt),
        "popular_items": popular_items(flt, popular_limit),
        "delivery": delivery_performance(flt),
        "reviews": review_summary(flt),
    }