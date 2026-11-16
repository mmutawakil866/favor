"""
Promo services. Dev 3's checkout calls these; we never touch their order code.

    result = validate_promo(code, subtotal, user, delivery_fee=fee)
    if result.valid: total = subtotal + fee - result.discount
    ...after payment is CONFIRMED (never before):
    record_redemption(code=code, user=user, order_id=order.pk, discount_amount=result.discount)

validate_promo is read-only. Only record_redemption consumes a use, so a failed
or abandoned payment never burns a code.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import DiscountType, PromoCode, PromoRedemption

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


class Reason:
    NOT_FOUND = "NOT_FOUND"
    INACTIVE = "INACTIVE"
    NOT_STARTED = "NOT_STARTED"
    EXPIRED = "EXPIRED"
    MIN_ORDER = "MIN_ORDER"
    LIMIT_REACHED = "LIMIT_REACHED"
    USER_LIMIT_REACHED = "USER_LIMIT_REACHED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    NO_DISCOUNT = "NO_DISCOUNT"


MESSAGES = {
    Reason.NOT_FOUND: "That promo code is not valid.",
    Reason.INACTIVE: "That promo code is not active.",
    Reason.NOT_STARTED: "That promo code is not available yet.",
    Reason.EXPIRED: "That promo code has expired.",
    Reason.MIN_ORDER: "Your order is below the minimum for this promo code.",
    Reason.LIMIT_REACHED: "That promo code has reached its usage limit.",
    Reason.USER_LIMIT_REACHED: "You have already used this promo code.",
    Reason.LOGIN_REQUIRED: "Please sign in to use a promo code.",
    Reason.NO_DISCOUNT: "This promo code gives no discount on your order.",
}


class PromoError(Exception):
    def __init__(self, reason):
        super().__init__(MESSAGES.get(reason, reason))
        self.reason = reason


@dataclass(frozen=True)
class PromoResult:
    valid: bool
    discount: Decimal = ZERO
    reason: str = ""
    message: str = ""
    promo: Optional[PromoCode] = None


def _dec(value):
    return Decimal(str(value))


def _money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_discount(*, discount_type, value, subtotal, delivery_fee=0,
                       applies_to_delivery_fee=False, max_discount=None):
    """Pure function (no DB). Delivery fee is only discountable when flagged."""
    subtotal, fee, value = _dec(subtotal), _dec(delivery_fee), _dec(value)
    base = subtotal + (fee if applies_to_delivery_fee else ZERO)
    if base <= 0:
        return ZERO
    if discount_type == DiscountType.PERCENTAGE:
        raw = base * min(value, Decimal("100")) / Decimal("100")
    else:
        raw = value
    if max_discount is not None:
        raw = min(raw, _dec(max_discount))
    return _money(max(min(raw, base), ZERO))


def _fail(reason):
    return PromoResult(valid=False, reason=reason, message=MESSAGES[reason])


def validate_promo(code, subtotal, user=None, delivery_fee=0, now=None):
    """Read-only check. min_order_amount is compared against the subtotal (food only)."""
    now = now or timezone.now()
    normalized = (code or "").strip().upper()
    if not normalized:
        return _fail(Reason.NOT_FOUND)
    promo = PromoCode.objects.filter(code=normalized).first()
    if promo is None:
        return _fail(Reason.NOT_FOUND)
    if not promo.is_active:
        return _fail(Reason.INACTIVE)
    if now < promo.valid_from:
        return _fail(Reason.NOT_STARTED)
    if promo.valid_until is not None and now > promo.valid_until:
        return _fail(Reason.EXPIRED)
    if _dec(subtotal) < promo.min_order_amount:
        return _fail(Reason.MIN_ORDER)
    if promo.max_uses is not None and promo.used_count >= promo.max_uses:
        return _fail(Reason.LIMIT_REACHED)
    if user is None or not getattr(user, "is_authenticated", False):
        return _fail(Reason.LOGIN_REQUIRED)
    if promo.per_user_limit is not None:
        used = PromoRedemption.objects.filter(promo=promo, user=user).count()
        if used >= promo.per_user_limit:
            return _fail(Reason.USER_LIMIT_REACHED)

    discount = calculate_discount(
        discount_type=promo.discount_type,
        value=promo.discount_value,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        applies_to_delivery_fee=promo.applies_to_delivery_fee,
        max_discount=promo.max_discount_amount,
    )
    if discount <= 0:
        return _fail(Reason.NO_DISCOUNT)
    return PromoResult(valid=True, discount=discount, message="Promo applied.", promo=promo)


def record_redemption(*, code, user, order_id, discount_amount):
    """
    Call once payment is confirmed. Idempotent per order_id (webhook retries are
    safe). Re-checks only the usage limits, not the validity window: a code that
    was valid at checkout still counts if payment confirms a moment later.
    """
    normalized = (code or "").strip().upper()
    with transaction.atomic():
        try:
            promo = PromoCode.objects.select_for_update().get(code=normalized)
        except PromoCode.DoesNotExist:
            raise PromoError(Reason.NOT_FOUND)

        existing = PromoRedemption.objects.filter(order_id=order_id).first()
        if existing is not None:
            return existing

        if promo.max_uses is not None and promo.used_count >= promo.max_uses:
            raise PromoError(Reason.LIMIT_REACHED)
        if promo.per_user_limit is not None:
            used = PromoRedemption.objects.filter(promo=promo, user=user).count()
            if used >= promo.per_user_limit:
                raise PromoError(Reason.USER_LIMIT_REACHED)

        redemption = PromoRedemption.objects.create(
            promo=promo, user=user, order_id=order_id, discount_amount=_money(_dec(discount_amount))
        )
        PromoCode.objects.filter(pk=promo.pk).update(used_count=F("used_count") + 1)
    return redemption