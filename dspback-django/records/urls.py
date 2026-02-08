from django.urls import include, path
from rest_framework.routers import DefaultRouter

from records.views import (
    ProfileViewSet,
    RecordViewSet,
    me_view,
    organizations_search,
    persons_search,
)

router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profile")
router.register("records", RecordViewSet, basename="record")

urlpatterns = [
    path("me/", me_view, name="me"),
    path("persons/", persons_search, name="persons-search"),
    path("organizations/", organizations_search, name="organizations-search"),
    path("", include(router.urls)),
]
