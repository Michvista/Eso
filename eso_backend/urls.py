from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.db import connections
from django.conf import settings


def health(request):
    """
    GET /api/health/ — unauthenticated keep-alive + readiness check.
    Free Render instances spin down after 15 minutes of inactivity.
    Call this every 10 minutes from cron-job.org or UptimeRobot.
    """
    db_ok = False
    try:
        connections["default"].cursor().execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    return JsonResponse({
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "groq_configured": bool(settings.GROQ_API_KEY),
    })


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("transactions.urls")),
    path("api/health/", health),
]
