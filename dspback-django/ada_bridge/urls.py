from django.urls import path

from ada_bridge.views import (
    bundle_introspect_view,
    bundle_upload_view,
    push_view,
    status_view,
    sync_view,
)

app_name = "ada_bridge"

urlpatterns = [
    path("push/<uuid:record_id>/", push_view, name="push"),
    path("sync/<uuid:record_id>/", sync_view, name="sync"),
    path("status/<uuid:record_id>/", status_view, name="status"),
    path("bundle/introspect/", bundle_introspect_view, name="bundle-introspect"),
    path("bundle/upload/<uuid:record_id>/", bundle_upload_view, name="bundle-upload"),
]
