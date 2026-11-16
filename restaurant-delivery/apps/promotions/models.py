"""
Promotions models, aligned with docs/schema.sql:
  promotions_campaign, promotions_campaign_items, promotions_promocode.

Columns marked PROPOSED are NOT in schema.sql yet and need team approval
(see docs/DEV5_ASSUMPTIONS.md): per_user_limit, max_discount_amount,
applies_to_delivery_fee, and the whole PromoRedemption table.

Cross-team references are plain integers for now (fooditem_id, order_id) so this
app does not depend on Dev 1 / Dev 3 models existing. Swap them for real
ForeignKeys once those apps land (see apps/dev5_adapter.py).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class DiscountType(models.TextChoices):
    PERCENTAGE = "PERCENTAGE", "Percentage"
    FIXED = "FIXED", "Fixed amount"


def _check_discount(discount_type, value):
    if value is None or value < 0:
        raise ValidationError({"discount_value": "Cannot be negative."})
    if discount_type == DiscountType.PERCENTAGE and value > 100:
        raise ValidationError({"discount_value": "A percentage cannot exceed 100."})


class Campaign(models.Model):
    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    description = models.TextField(blank=True)
    banner_image = models.CharField(max_length=500, blank=True)  # Cloudinary URL / path
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices,
                                     default=DiscountType.PERCENTAGE)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:170]
        super().save(*args, **kwargs)

    def clean(self):
        _check_discount(self.discount_type, self.discount_value)
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "Must be after the start date."})

    def is_running(self, now=None):
        now = now or timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date


class CampaignItem(models.Model):
    """Food items a campaign applies to (promotions_campaign_items)."""

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="items")
    fooditem_id = models.PositiveBigIntegerField()  # becomes FK to menu.FoodItem later

    class Meta:
        db_table = "promotions_campaign_items"
        constraints = [
            models.UniqueConstraint(fields=["campaign", "fooditem_id"], name="uniq_campaign_fooditem")
        ]

    def __str__(self):
        return f"{self.campaign_id}:{self.fooditem_id}"


class PromoCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="promo_codes")
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices,
                                     default=DiscountType.PERCENTAGE)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2)
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Blank = unlimited")
    used_count = models.PositiveIntegerField(default=0, editable=False)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True, help_text="Blank = never expires")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # PROPOSED (not in schema.sql yet):
    per_user_limit = models.PositiveIntegerField(null=True, blank=True, default=1,
                                                 help_text="Blank = unlimited per customer")
    max_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # PRD: delivery fees are excluded from discounts unless a promo targets them.
    applies_to_delivery_fee = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        _check_discount(self.discount_type, self.discount_value)
        if self.valid_until and self.valid_from and self.valid_until <= self.valid_from:
            raise ValidationError({"valid_until": "Must be after valid_from."})


class PromoRedemption(models.Model):
    """PROPOSED table: one row per redeemed order, for idempotency and per-customer limits."""

    promo = models.ForeignKey(PromoCode, on_delete=models.PROTECT, related_name="redemptions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name="promo_redemptions")
    order_id = models.PositiveBigIntegerField(unique=True)  # becomes OneToOne to orders.Order later
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-redeemed_at"]

    def __str__(self):
        return f"{self.promo_id} -> order {self.order_id}"