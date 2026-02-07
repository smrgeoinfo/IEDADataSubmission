from django.urls import include, path
from rest_framework.routers import DefaultRouter

from records.views import ProfileViewSet, RecordViewSet

router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profile")
router.register("records", RecordViewSet, basename="record")

urlpatterns = [
    path("", include(router.urls)),
]
