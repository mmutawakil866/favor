from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.promotions import services
from apps.promotions.models import DiscountType, PromoCode, PromoRedemption
from apps.promotions.services import PromoError, Reason, calculate_discount, record_redemption, validate_promo

D = Decimal


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="ama", password="x")


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user(username="kofi", password="x")


@pytest.fixture
def make_promo(db):
    def make(**kw):
        now = timezone.now()
        defaults = dict(code="WELCOME10", discount_type=DiscountType.PERCENTAGE, discount_value=D("10"),
                        valid_from=now - timedelta(days=1), valid_until=now + timedelta(days=1))
        defaults.update(kw)
        return PromoCode.objects.create(**defaults)
    return make


# --- calculate_discount (pure) ------------------------------------------------
def test_percent_discount():
    assert calculate_discount(discount_type="PERCENTAGE", value=10, subtotal=100) == D("10.00")


def test_fixed_discount():
    assert calculate_discount(discount_type="FIXED", value=15, subtotal=100) == D("15.00")


def test_fixed_discount_never_exceeds_subtotal():
    assert calculate_discount(discount_type="FIXED", value=50, subtotal=20) == D("20.00")


def test_max_discount_caps_percent():
    assert calculate_discount(discount_type="PERCENTAGE", value=50, subtotal=200, max_discount=30) == D("30.00")


def test_delivery_fee_excluded_by_default():
    assert calculate_discount(discount_type="PERCENTAGE", value=100, subtotal=40, delivery_fee=10) == D("40.00")


def test_delivery_fee_included_when_promo_targets_it():
    got = calculate_discount(discount_type="PERCENTAGE", value=100, subtotal=40, delivery_fee=10,
                             applies_to_delivery_fee=True)
    assert got == D("50.00")


def test_rounds_half_up_to_two_places():
    assert calculate_discount(discount_type="PERCENTAGE", value=15, subtotal="33.33") == D("5.00")


def test_zero_subtotal_gives_zero():
    assert calculate_discount(discount_type="PERCENTAGE", value=10, subtotal=0) == D("0.00")


# --- validate_promo -----------------------------------------------------------
def test_valid_code_returns_discount(user, make_promo):
    make_promo()
    r = validate_promo("welcome10", D("80"), user)
    assert r.valid and r.discount == D("8.00") and r.promo.code == "WELCOME10"


def test_code_is_trimmed_and_case_insensitive(user, make_promo):
    make_promo()
    assert validate_promo("  Welcome10 ", D("80"), user).valid


@pytest.mark.parametrize("code", ["", None, "NOPE"])
def test_unknown_or_empty_code(user, make_promo, code):
    make_promo()
    assert validate_promo(code, D("80"), user).reason == Reason.NOT_FOUND


def test_inactive(user, make_promo):
    make_promo(is_active=False)
    assert validate_promo("WELCOME10", D("80"), user).reason == Reason.INACTIVE


def test_not_started(user, make_promo):
    make_promo(valid_from=timezone.now() + timedelta(hours=1), valid_until=timezone.now() + timedelta(days=2))
    assert validate_promo("WELCOME10", D("80"), user).reason == Reason.NOT_STARTED


def test_expired(user, make_promo):
    make_promo(valid_from=timezone.now() - timedelta(days=3), valid_until=timezone.now() - timedelta(days=1))
    assert validate_promo("WELCOME10", D("80"), user).reason == Reason.EXPIRED


def test_minimum_order(user, make_promo):
    make_promo(min_order_amount=D("50"))
    assert validate_promo("WELCOME10", D("49.99"), user).reason == Reason.MIN_ORDER
    assert validate_promo("WELCOME10", D("50"), user).valid


def test_total_max_uses(user, make_promo):
    make_promo(max_uses=1, used_count=1)
    assert validate_promo("WELCOME10", D("80"), user).reason == Reason.LIMIT_REACHED


def test_requires_user(make_promo):
    make_promo()
    assert validate_promo("WELCOME10", D("80"), None).reason == Reason.LOGIN_REQUIRED


def test_per_user_limit(user, make_promo):
    promo = make_promo(per_user_limit=1)
    PromoRedemption.objects.create(promo=promo, user=user, order_id=1, discount_amount=D("5"))
    assert validate_promo("WELCOME10", D("80"), user).reason == Reason.USER_LIMIT_REACHED


def test_validate_does_not_consume_a_use(user, make_promo):
    promo = make_promo(max_uses=1)
    validate_promo("WELCOME10", D("80"), user)
    promo.refresh_from_db()
    assert promo.used_count == 0


# --- record_redemption --------------------------------------------------------
def test_record_redemption_increments_used_count(user, make_promo):
    promo = make_promo()
    record_redemption(code="WELCOME10", user=user, order_id=7, discount_amount=D("8"))
    promo.refresh_from_db()
    assert promo.used_count == 1 and PromoRedemption.objects.filter(order_id=7).exists()


def test_record_redemption_is_idempotent_per_order(user, make_promo):
    promo = make_promo(per_user_limit=None)
    a = record_redemption(code="WELCOME10", user=user, order_id=7, discount_amount=D("8"))
    b = record_redemption(code="WELCOME10", user=user, order_id=7, discount_amount=D("8"))
    promo.refresh_from_db()
    assert a.pk == b.pk and promo.used_count == 1


def test_record_redemption_respects_max_uses(user, other_user, make_promo):
    make_promo(max_uses=1)
    record_redemption(code="WELCOME10", user=user, order_id=1, discount_amount=D("8"))
    with pytest.raises(PromoError) as exc:
        record_redemption(code="WELCOME10", user=other_user, order_id=2, discount_amount=D("8"))
    assert exc.value.reason == Reason.LIMIT_REACHED


def test_record_redemption_respects_per_user_limit(user, make_promo):
    make_promo(per_user_limit=1)
    record_redemption(code="WELCOME10", user=user, order_id=1, discount_amount=D("8"))
    with pytest.raises(PromoError) as exc:
        record_redemption(code="WELCOME10", user=user, order_id=2, discount_amount=D("8"))
    assert exc.value.reason == Reason.USER_LIMIT_REACHED


def test_record_redemption_unknown_code(user):
    with pytest.raises(PromoError):
        record_redemption(code="NOPE", user=user, order_id=1, discount_amount=D("1"))


# --- schema alignment extras ---------------------------------------------------
def test_code_without_expiry_never_expires(user, make_promo):
    make_promo(valid_until=None)
    far_future = timezone.now() + timedelta(days=3650)
    assert validate_promo("WELCOME10", D("80"), user, now=far_future).valid


def test_code_saved_uppercase_and_trimmed(make_promo):
    assert make_promo(code="  jollof20 ").code == "JOLLOF20"


def test_campaign_slug_and_running_window(db):
    from apps.promotions.models import Campaign
    now = timezone.now()
    c = Campaign.objects.create(title="Black Friday", discount_type="PERCENTAGE", discount_value=25,
                                start_date=now - timedelta(hours=1), end_date=now + timedelta(hours=1))
    assert c.slug == "black-friday" and c.is_running()
    assert not c.is_running(now + timedelta(days=1))