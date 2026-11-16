"""
Reviews (table: reviews_review). One review per order, three ratings, soft-hide
only (PRD: admins never hard-delete). order_id is a plain integer for now and
becomes a OneToOneField to Dev 3's Order later (see apps/dev5_adapter.py).
"""
from django.conf import settings
from django.db import models


class Rating(models.TextChoices):
    VERY_BAD = "VERY_BAD", "Very bad"
    BAD = "BAD", "Bad"
    OKAY = "OKAY", "Okay"
    GOOD = "GOOD", "Good"
    EXCELLENT = "EXCELLENT", "Excellent"


RATING_VALUES = {
    Rating.VERY_BAD: 1,
    Rating.BAD: 2,
    Rating.OKAY: 3,
    Rating.GOOD: 4,
    Rating.EXCELLENT: 5,
}


class Review(models.Model):
    order_id = models.PositiveBigIntegerField(unique=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews")
    overall_rating = models.CharField(max_length=10, choices=Rating.choices)
    food_rating = models.CharField(max_length=10, choices=Rating.choices)
    service_rating = models.CharField(max_length=10, choices=Rating.choices)
    comment = models.TextField(blank=True)

    is_visible = models.BooleanField(default=True)
    # PROPOSED (not in schema.sql yet): moderation audit trail
    hidden_reason = models.CharField(max_length=200, blank=True)
    hidden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    hidden_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review of order {self.order_id} ({self.overall_rating})"