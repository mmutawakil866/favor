from django.urls import include, path

urlpatterns = [path("dashboard/", include("apps.dashboard.urls"))]