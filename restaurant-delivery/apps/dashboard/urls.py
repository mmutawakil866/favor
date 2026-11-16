from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("api/reports/summary/", views.report_summary, name="report-summary"),
]