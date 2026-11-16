from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.reviews import services
from apps.reviews.models import Review
from apps.reviews.services import ReviewError


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="ama", password="x")


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user(username="kofi", password="x")


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_user(username="staff", password="x", is_staff=True)


def order_for(user, pk=1, status="DELIVERED"):
    return SimpleNamespace(pk=pk, customer_id=user.pk, status=status)


def submit(user, order, **kw):
    args = dict(overall_rating="GOOD", food_rating="EXCELLENT", service_rating="OKAY", comment="Tasty")
    args.update(kw)
    return services.submit_review(user=user, order=order, **args)


def code_of(exc_info):
    return exc_info.value.code


def test_submit_on_delivered_order(user):
    review = submit(user, order_for(user))
    assert review.pk and review.is_visible and review.order_id == 1


def test_cannot_review_someone_elses_order(user, other_user):
    with pytest.raises(ReviewError) as e:
        submit(other_user, order_for(user))
    assert code_of(e) == "NOT_OWNER"


@pytest.mark.parametrize("status", ["PENDING", "CONFIRMED", "PREPARING", "OUT_FOR_DELIVERY", "CANCELLED"])
def test_cannot_review_undelivered_order(user, status):
    with pytest.raises(ReviewError) as e:
        submit(user, order_for(user, status=status))
    assert code_of(e) == "NOT_DELIVERED"


def test_one_review_per_order(user):
    order = order_for(user)
    submit(user, order)
    with pytest.raises(ReviewError) as e:
        submit(user, order)
    assert code_of(e) == "ALREADY_REVIEWED"


def test_invalid_rating_rejected(user):
    with pytest.raises(ReviewError) as e:
        submit(user, order_for(user), food_rating="AMAZING")
    assert code_of(e) == "INVALID_RATING"


def test_edit_within_window(user):
    review = submit(user, order_for(user))
    services.edit_review(review=review, user=user, comment="Even better", food_rating="GOOD")
    review.refresh_from_db()
    assert review.comment == "Even better" and review.food_rating == "GOOD"


def test_edit_after_seven_days_rejected(user):
    review = submit(user, order_for(user))
    later = review.created_at + timedelta(days=7, minutes=1)
    with pytest.raises(ReviewError) as e:
        services.edit_review(review=review, user=user, comment="late", now=later)
    assert code_of(e) == "EDIT_WINDOW_CLOSED"


def test_only_owner_can_edit(user, other_user):
    review = submit(user, order_for(user))
    with pytest.raises(ReviewError) as e:
        services.edit_review(review=review, user=other_user, comment="hax")
    assert code_of(e) == "NOT_OWNER"


def test_cannot_edit_protected_fields(user):
    review = submit(user, order_for(user))
    with pytest.raises(ReviewError) as e:
        services.edit_review(review=review, user=user, is_visible=False)
    assert code_of(e) == "UNKNOWN_FIELD"


def test_hide_and_restore_keep_the_row(user, staff):
    review = submit(user, order_for(user))
    services.hide_review(review=review, staff_user=staff, reason="Abusive language")
    review.refresh_from_db()
    assert not review.is_visible and review.hidden_by_id == staff.pk and review.hidden_at
    assert Review.objects.count() == 1

    services.restore_review(review=review)
    review.refresh_from_db()
    assert review.is_visible and review.hidden_by is None


def test_hidden_reviews_excluded_from_visible_and_averages(user, other_user, staff):
    r1 = submit(user, order_for(user, pk=1), overall_rating="EXCELLENT", food_rating="EXCELLENT", service_rating="EXCELLENT")
    r2 = submit(other_user, order_for(other_user, pk=2), overall_rating="VERY_BAD", food_rating="VERY_BAD", service_rating="VERY_BAD")
    assert services.average_ratings()["overall"] == 3.0
    services.hide_review(review=r2, staff_user=staff)
    assert list(services.visible_reviews()) == [r1]
    assert services.average_ratings() == {"count": 1, "overall": 5.0, "food": 5.0, "service": 5.0}


def test_average_with_no_reviews(db):
    assert services.average_ratings() == {"count": 0, "overall": None, "food": None, "service": None}