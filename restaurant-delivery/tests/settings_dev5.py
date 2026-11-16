"""Standalone settings so Dev 5 tests run without Dev 1's project. Not for deployment."""
SECRET_KEY = "dev5-test-only"
DEBUG = True
USE_TZ = True
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "apps.promotions",
    "apps.reviews",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CURRENCY_CODE = "GHS"