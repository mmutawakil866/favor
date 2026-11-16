from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from apps import dev5_adapter as ad

from .board import board_snapshot


def _deny_json(request):
    user = request.user
    if not getattr(user, "is_authenticated", False):
        return JsonResponse({"detail": "Authentication required."}, status=401)
    if not ad.is_dashboard_user(user):
        return JsonResponse({"detail": "Staff access only."}, status=403)
    return None


@require_GET
@ensure_csrf_cookie
def board_page(request):
    user = request.user
    if not getattr(user, "is_authenticated", False):
        return redirect_to_login(request.get_full_path())
    if not ad.is_dashboard_user(user):
        return HttpResponseForbidden("Staff access only.")
    context = {"poll_seconds": ad.BOARD_POLL_SECONDS, "ws_url": getattr(settings, "DASHBOARD_WS_URL", "")}
    return render(request, "dashboard/orders_board.html", context)


@require_GET
def board_feed(request):
    return _deny_json(request) or JsonResponse(board_snapshot())


@require_POST
def advance_order(request, reference):
    """Move an order to the next kitchen status. The server picks the next status itself;
    the client only says which status it was looking at, so a double click cannot skip a step."""
    denied = _deny_json(request)
    if denied:
        return denied
    order = ad.find_order(reference)
    if order is None:
        return JsonResponse({"detail": "Order not found."}, status=404)
    current = ad.order_status(order)
    target = ad.STAFF_NEXT_STATUS.get(current)
    if target is None:
        return JsonResponse({"detail": "This order cannot be advanced from the board."}, status=400)
    seen = request.POST.get("from_status")
    if seen and seen != current:
        return JsonResponse({"detail": f"This order is already {current}."}, status=409)
    try:
        ad.update_order_status(order=order, new_status=target, actor=request.user)
    except ad.OrderServiceUnavailable as exc:
        return JsonResponse({"detail": str(exc)}, status=503)
    except PermissionDenied:
        return JsonResponse({"detail": "You are not allowed to do that."}, status=403)
    except ad.order_transition_errors() as exc:
        return JsonResponse({"detail": str(exc)}, status=409)
    return JsonResponse({"reference": reference, "status": target})