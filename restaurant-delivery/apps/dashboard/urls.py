from django.urls import path

from . import board_views, report_page_views, review_views, views

app_name = "dashboard"

urlpatterns = [
    path("api/reports/summary/", views.report_summary, name="report-summary"),
    path("reports/", report_page_views.reports_page, name="reports"),
    path("reviews/", review_views.reviews_page, name="reviews"),
    path("api/reviews/", review_views.reviews_feed, name="reviews-feed"),
    path("api/reviews/<int:pk>/hide/", review_views.hide_review, name="reviews-hide"),
    path("api/reviews/<int:pk>/restore/", review_views.restore_review, name="reviews-restore"),
    path("orders/board/", board_views.board_page, name="orders-board"),
    path("api/orders/board/", board_views.board_feed, name="orders-board-feed"),
    path("api/orders/<str:reference>/advance/", board_views.advance_order, name="orders-advance"),
]