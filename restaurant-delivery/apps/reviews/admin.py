from django.contrib import admin

from . import services
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("order_id", "customer", "overall_rating", "food_rating", "service_rating",
                    "is_visible", "created_at")
    list_filter = ("is_visible", "overall_rating")
    search_fields = ("comment",)
    actions = ["hide_selected", "restore_selected"]

    def has_delete_permission(self, request, obj=None):
        return False  # PRD: soft-hide only

    @admin.action(description="Hide selected reviews")
    def hide_selected(self, request, queryset):
        for review in queryset:
            services.hide_review(review=review, staff_user=request.user, reason="Hidden by staff")

    @admin.action(description="Restore selected reviews")
    def restore_selected(self, request, queryset):
        for review in queryset:
            services.restore_review(review=review)