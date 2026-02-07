"""Root URL configuration for the catalog project."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/catalog/admin/", admin.site.urls),
    path("api/catalog/", include("records.urls")),
    path("api/", include("accounts.urls")),
]
