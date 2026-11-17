"""Read side of review moderation. Hiding and restoring go through apps.reviews.services."""
from django.core.paginator import Paginator

from apps import dev5_adapter as ad
from apps.reviews import services as review_services
from apps.reviews.models import RATING_VALUES, Rating, Review

from .reports import ReportFilter, _range_kwargs

PAGE_SIZE = 20
VISIBILITIES = ("all", "visible", "hidden")


def _name(user):
    if user is None:
        return ""
    return (user.get_full_name() or user.get_username()).strip()


def review_queryset(visibility="all", ratings=(), q="", flt=None):
    qs = Review.objects.select_related("customer", "hidden_by").order_by("-created_at", "-pk")
    if visibility == "visible":
        qs = qs.filter(is_visible=True)
    elif visibility == "hidden":
        qs = qs.filter(is_visible=False)
    if ratings:
        qs = qs.filter(overall_rating__in=ratings)
    if q:
        qs = qs.filter(comment__icontains=q)
    if flt is not None:
        qs = qs.filter(**_range_kwargs("", "created_at", flt))
    return qs


def _rating(value):
    return {"value": value, "label": Rating(value).label, "score": RATING_VALUES[Rating(value)]}


def serialize(review, refs):
    return {
        "id": review.pk,
        "order_id": review.order_id,
        "order_reference": refs.get(review.order_id, ""),
        "customer": _name(review.customer),
        "overall": _rating(review.overall_rating),
        "food": _rating(review.food_rating),
        "service": _rating(review.service_rating),
        "comment": review.comment,
        "is_visible": review.is_visible,
        "hidden_reason": review.hidden_reason,
        "hidden_by": _name(review.hidden_by),
        "hidden_at": review.hidden_at,
        "created_at": review.created_at,
    }


def review_page(qs, page=1):
    paginator = Paginator(qs, PAGE_SIZE)
    current = paginator.get_page(page)
    refs = ad.order_references([r.order_id for r in current])
    return {
        "count": paginator.count,
        "page": current.number,
        "pages": paginator.num_pages,
        "results": [serialize(r, refs) for r in current],
        "summary": review_services.average_ratings(qs.filter(is_visible=True)),
        "hidden_count": qs.filter(is_visible=False).count(),
    }