from django.urls import include, path
from rest_framework.routers import DefaultRouter

from records.views import ProfileViewSet, RecordViewSet, me_view

router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profile")
router.register("records", RecordViewSet, basename="record")

urlpatterns = [
    path("me/", me_view, name="me"),
    path("", include(router.urls)),
]
