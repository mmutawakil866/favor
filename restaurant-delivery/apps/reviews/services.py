"""
Review rules from the PRD:
  - only the customer who placed a DELIVERED order can review it, once per order
  - editable for 7 days after creation
  - staff hide/restore (soft). There is intentionally no delete function.
Order access goes through apps/dev5_adapter.py.
"""
from datetime import timedelta

from django.utils import timezone

from apps import dev5_adapter as adapter

from .models import RATING_VALUES, Rating, Review

EDIT_WINDOW = timedelta(days=7)
EDITABLE_FIELDS = ("overall_rating", "food_rating", "service_rating", "comment")

MESSAGES = {
    "NOT_OWNER": "You can only review your own orders.",
    "NOT_DELIVERED": "You can review an order once it has been delivered.",
    "ALREADY_REVIEWED": "This order has already been reviewed.",
    "INVALID_RATING": "Invalid rating value.",
    "EDIT_WINDOW_CLOSED": "Reviews can only be edited within 7 days.",
    "UNKNOWN_FIELD": "That field cannot be edited.",
}


class ReviewError(Exception):
    def __init__(self, code):
        super().__init__(MESSAGES.get(code, code))
        self.code = code


def _check_rating(value):
    if value not in Rating.values:
        raise ReviewError("INVALID_RATING")


def submit_review(*, user, order, overall_rating, food_rating, service_rating, comment=""):
    for value in (overall_rating, food_rating, service_rating):
        _check_rating(value)
    if adapter.order_owner_id(order) != user.pk:
        raise ReviewError("NOT_OWNER")
    if not adapter.order_is_delivered(order):
        raise ReviewError("NOT_DELIVERED")
    if Review.objects.filter(order_id=order.pk).exists():
        raise ReviewError("ALREADY_REVIEWED")
    return Review.objects.create(
        order_id=order.pk,
        customer=user,
        overall_rating=overall_rating,
        food_rating=food_rating,
        service_rating=service_rating,
        comment=comment,
    )


def edit_review(*, review, user, now=None, **changes):
    now = now or timezone.now()
    if review.customer_id != user.pk:
        raise ReviewError("NOT_OWNER")
    if now - review.created_at > EDIT_WINDOW:
        raise ReviewError("EDIT_WINDOW_CLOSED")
    for field, value in changes.items():
        if field not in EDITABLE_FIELDS:
            raise ReviewError("UNKNOWN_FIELD")
        if field != "comment":
            _check_rating(value)
        setattr(review, field, value)
    review.save()
    return review


def hide_review(*, review, staff_user, reason=""):
    review.is_visible = False
    review.hidden_reason = reason
    review.hidden_by = staff_user
    review.hidden_at = timezone.now()
    review.save()
    return review


def restore_review(*, review):
    review.is_visible = True
    review.hidden_reason = ""
    review.hidden_by = None
    review.hidden_at = None
    review.save()
    return review


def visible_reviews():
    return Review.objects.filter(is_visible=True)


def average_ratings(queryset=None):
    """Average 1-5 scores over visible reviews (or the queryset you pass)."""
    rows = list((queryset if queryset is not None else visible_reviews())
                .values_list("overall_rating", "food_rating", "service_rating"))
    if not rows:
        return {"count": 0, "overall": None, "food": None, "service": None}
    n = len(rows)

    def avg(i):
        return round(sum(RATING_VALUES[Rating(r[i])] for r in rows) / n, 2)

    return {"count": n, "overall": avg(0), "food": avg(1), "service": avg(2)}