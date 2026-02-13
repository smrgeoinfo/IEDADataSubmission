from django.urls import path

from ada_bridge.views import (
    browse_directory_view,
    bundle_introspect_view,
    bundle_session_detail_view,
    bundle_session_introspect_view,
    bundle_session_select_product_view,
    bundle_session_submit_view,
    bundle_session_upload_view,
    bundle_upload_view,
    doi_lookup_view,
    push_view,
    status_view,
    sync_view,
)

app_name = "ada_bridge"

urlpatterns = [
    # Record push / sync / status
    path("push/<uuid:record_id>/", push_view, name="push"),
    path("sync/<uuid:record_id>/", sync_view, name="sync"),
    path("status/<uuid:record_id>/", status_view, name="status"),

    # Legacy bundle endpoints
    path("bundle/introspect/", bundle_introspect_view, name="bundle-introspect"),
    path("bundle/upload/<uuid:record_id>/", bundle_upload_view, name="bundle-upload"),

    # Directory browser
    path("bundle/browse-directory/", browse_directory_view, name="bundle-browse-directory"),

    # New session-based bundle endpoints
    path("bundle/upload/", bundle_session_upload_view, name="bundle-session-upload"),
    path("bundle/<uuid:session_id>/introspect/", bundle_session_introspect_view, name="bundle-session-introspect"),
    path("bundle/<uuid:session_id>/select-product-yaml/", bundle_session_select_product_view, name="bundle-session-select-product"),
    path("bundle/<uuid:session_id>/", bundle_session_detail_view, name="bundle-session-detail"),
    path("bundle/<uuid:session_id>/submit/", bundle_session_submit_view, name="bundle-session-submit"),

    # DOI lookup (Update Existing Metadata flow)
    path("lookup/", doi_lookup_view, name="doi-lookup"),
]
