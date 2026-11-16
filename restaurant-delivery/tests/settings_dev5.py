"""Standalone settings so Dev 5 tests run without Dev 1's project. Not for deployment.

The tests.stubs.* apps imitate Dev 1/3/4 tables from docs/schema.sql. When the real
apps land, replace the three stub entries below with the real apps (apps.menu,
apps.orders, apps.delivery) and delete tests/stubs.
"""
SECRET_KEY = "dev5-test-only"
DEBUG = True
USE_TZ = True
TIME_ZONE = "Africa/Accra"
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "apps.promotions",
    "apps.reviews",
    "apps.dashboard",
    "tests.stubs.menu",
    "tests.stubs.orders",
    "tests.stubs.delivery",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CURRENCY_CODE = "GHS"