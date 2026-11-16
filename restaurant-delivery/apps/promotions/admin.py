from django.contrib import admin

from .models import Campaign, CampaignItem, PromoCode, PromoRedemption


class CampaignItemInline(admin.TabularInline):
    model = CampaignItem
    extra = 0


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("title", "discount_type", "discount_value", "start_date", "end_date", "is_active")
    list_filter = ("is_active", "discount_type")
    search_fields = ("title",)
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CampaignItemInline]


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_type", "discount_value", "used_count", "max_uses",
                    "valid_from", "valid_until", "is_active")
    list_filter = ("is_active", "discount_type")
    search_fields = ("code",)
    readonly_fields = ("used_count",)


@admin.register(PromoRedemption)
class PromoRedemptionAdmin(admin.ModelAdmin):
    list_display = ("promo", "user", "order_id", "discount_amount", "redeemed_at")
    readonly_fields = ("promo", "user", "order_id", "discount_amount", "redeemed_at")

    def has_add_permission(self, request):
        return False