from django.urls import path

from . import board_views, report_page_views, views

app_name = "dashboard"

urlpatterns = [
    path("api/reports/summary/", views.report_summary, name="report-summary"),
    path("reports/", report_page_views.reports_page, name="reports"),
    path("orders/board/", board_views.board_page, name="orders-board"),
    path("api/orders/board/", board_views.board_feed, name="orders-board-feed"),
    path("api/orders/<str:reference>/advance/", board_views.advance_order, name="orders-advance"),
]