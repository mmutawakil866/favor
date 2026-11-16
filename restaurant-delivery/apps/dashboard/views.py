from datetime import date, timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps import dev5_adapter as ad

from .reports import ReportFilter, report_bundle


def _parse_date(value, default):
    if not value:
        return default
    return date.fromisoformat(value)


@require_GET
def report_summary(request):
    """JSON feed for the dashboard charts. Defaults to the last 30 days.
    Query: date_from, date_to (YYYY-MM-DD), status (repeatable)."""
    user = request.user
    if not getattr(user, "is_authenticated", False):
        return JsonResponse({"detail": "Authentication required."}, status=401)
    if not ad.is_dashboard_user(user):
        return JsonResponse({"detail": "Staff access only."}, status=403)
    today = timezone.localdate()
    try:
        flt = ReportFilter(
            date_from=_parse_date(request.GET.get("date_from"), today - timedelta(days=29)),
            date_to=_parse_date(request.GET.get("date_to"), today),
            statuses=tuple(request.GET.getlist("status")) or None,
        )
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    return JsonResponse(report_bundle(flt))