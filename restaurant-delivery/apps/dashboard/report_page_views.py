from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps import dev5_adapter as ad


@require_GET
def reports_page(request):
    user = request.user
    if not getattr(user, "is_authenticated", False):
        return redirect_to_login(request.get_full_path())
    if not ad.is_dashboard_user(user):
        return HttpResponseForbidden("Staff access only.")
    return render(request, "dashboard/reports.html", {"statuses": list(ad.ORDER_STATUSES)})