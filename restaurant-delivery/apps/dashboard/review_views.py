from datetime import date

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from apps import dev5_adapter as ad
from apps.reviews import services as review_services
from apps.reviews.models import Rating, Review

from .board_views import _deny_json
from .reports import ReportFilter
from .review_moderation import VISIBILITIES, review_page, review_queryset

MAX_REASON = 200
MAX_SEARCH = 100


@require_GET
@ensure_csrf_cookie
def reviews_page(request):
    user = request.user
    if not getattr(user, "is_authenticated", False):
        return redirect_to_login(request.get_full_path())
    if not ad.is_dashboard_user(user):
        return HttpResponseForbidden("Staff access only.")
    context = {"ratings": [{"value": v, "label": l} for v, l in Rating.choices],
               "can_moderate": ad.is_admin_user(user)}
    return render(request, "dashboard/reviews.html", context)


@require_GET
def reviews_feed(request):
    denied = _deny_json(request)
    if denied:
        return denied
    visibility = request.GET.get("visibility", "all")
    ratings = request.GET.getlist("rating")
    if visibility not in VISIBILITIES:
        return JsonResponse({"detail": "Unknown visibility filter."}, status=400)
    if any(r not in Rating.values for r in ratings):
        return JsonResponse({"detail": "Unknown rating filter."}, status=400)
    try:
        flt = ReportFilter(
            date_from=date.fromisoformat(request.GET["date_from"]) if request.GET.get("date_from") else None,
            date_to=date.fromisoformat(request.GET["date_to"]) if request.GET.get("date_to") else None,
        )
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        page = 1
    q = request.GET.get("q", "").strip()[:MAX_SEARCH]
    data = review_page(review_queryset(visibility, ratings, q, flt), page)
    data["can_moderate"] = ad.is_admin_user(request.user)
    return JsonResponse(data)


def _moderation_target(request, pk):
    """(review, error response). Moderation is for administrators only."""
    denied = _deny_json(request)
    if denied:
        return None, denied
    if not ad.is_admin_user(request.user):
        return None, JsonResponse({"detail": "Only administrators can moderate reviews."}, status=403)
    review = Review.objects.filter(pk=pk).first()
    if review is None:
        return None, JsonResponse({"detail": "Review not found."}, status=404)
    return review, None


@require_POST
def hide_review(request, pk):
    review, error = _moderation_target(request, pk)
    if error:
        return error
    reason = request.POST.get("reason", "").strip()
    if not reason:
        return JsonResponse({"detail": "Give a reason for hiding this review."}, status=400)
    if len(reason) > MAX_REASON:
        return JsonResponse({"detail": f"The reason must be {MAX_REASON} characters or fewer."}, status=400)
    if not review.is_visible:
        return JsonResponse({"detail": "This review is already hidden."}, status=409)
    review_services.hide_review(review=review, staff_user=request.user, reason=reason)
    return JsonResponse({"id": review.pk, "is_visible": False})


@require_POST
def restore_review(request, pk):
    review, error = _moderation_target(request, pk)
    if error:
        return error
    if review.is_visible:
        return JsonResponse({"detail": "This review is already visible."}, status=409)
    review_services.restore_review(review=review)
    return JsonResponse({"id": review.pk, "is_visible": True})