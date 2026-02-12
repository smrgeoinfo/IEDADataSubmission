"""
DRF views for the ADA Bridge API.

Endpoints:
    POST /api/ada-bridge/push/{record_id}/                — push record to ADA
    POST /api/ada-bridge/sync/{record_id}/                — sync status from ADA
    GET  /api/ada-bridge/status/{record_id}/              — get AdaRecordLink info
    POST /api/ada-bridge/bundle/introspect/               — upload ZIP, return metadata (legacy)
    POST /api/ada-bridge/bundle/upload/{record_id}/       — upload bundle to linked ADA record (legacy)
    POST /api/ada-bridge/bundle/upload/                   — create BundleSession from upload
    POST /api/ada-bridge/bundle/{session_id}/introspect/           — run introspection on session
    POST /api/ada-bridge/bundle/{session_id}/select-product-yaml/ — parse user-selected file as product.yaml
    GET  /api/ada-bridge/bundle/{session_id}/                     — get session state
    PATCH /api/ada-bridge/bundle/{session_id}/                    — update session (product_yaml, jsonld_draft)
    POST /api/ada-bridge/bundle/{session_id}/submit/      — save to catalog + push to ADA
    GET  /api/ada-bridge/lookup/                          — look up ADA record by DOI
"""

import logging

from rest_framework import permissions, status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from ada_bridge.client import AdaClient, AdaClientError
from ada_bridge.models import AdaRecordLink, BundleSession
from ada_bridge.serializers import (
    AdaRecordLinkSerializer,
    BundleSessionSerializer,
    BundleSessionUpdateSerializer,
    BundleSubmitSerializer,
    BundleUploadSerializer,
    PushResponseSerializer,
    SyncResponseSerializer,
)
from ada_bridge.services import (
    create_bundle_session,
    introspect_bundle_session,
    push_record_to_ada,
    select_product_yaml,
    submit_bundle_session,
    sync_ada_status,
    upload_bundle_and_introspect,
)
from ada_bridge.translator_ada import ada_to_jsonld
from records.models import Record

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Existing push / sync / status views
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def push_view(request, record_id):
    """Translate and push an IEDA record to ADA."""
    try:
        link = push_record_to_ada(record_id)
    except Record.DoesNotExist:
        return Response(
            {"detail": "Record not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except AdaClientError as exc:
        return Response(
            {"detail": "ADA API error.", "ada_error": exc.detail},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    serializer = PushResponseSerializer(link)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def sync_view(request, record_id):
    """Pull status and DOI from ADA for an IEDA record."""
    try:
        link = sync_ada_status(record_id)
    except AdaRecordLink.DoesNotExist:
        return Response(
            {"detail": "No ADA link exists for this record."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except AdaClientError as exc:
        return Response(
            {"detail": "ADA API error.", "ada_error": exc.detail},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    serializer = SyncResponseSerializer(link)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def status_view(request, record_id):
    """Get current AdaRecordLink info for an IEDA record."""
    try:
        link = AdaRecordLink.objects.get(ieda_record_id=record_id)
    except AdaRecordLink.DoesNotExist:
        return Response(
            {"detail": "No ADA link exists for this record."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = AdaRecordLinkSerializer(link)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Legacy bundle views (kept for backward compatibility)
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser])
def bundle_introspect_view(request):
    """Upload a ZIP bundle and return introspection results."""
    serializer = BundleUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    file_obj = serializer.validated_data.get("file")
    if not file_obj:
        return Response(
            {"detail": "File is required for this endpoint."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = upload_bundle_and_introspect(file_obj)
    return Response(result, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser])
def bundle_upload_view(request, record_id):
    """Upload a bundle to a linked ADA record."""
    serializer = BundleUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    file_obj = serializer.validated_data.get("file")
    if not file_obj:
        return Response(
            {"detail": "File is required for this endpoint."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = upload_bundle_and_introspect(file_obj, ieda_record_id=record_id)
    except AdaClientError as exc:
        return Response(
            {"detail": "ADA API error.", "ada_error": exc.detail},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(result, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# New session-based bundle endpoints
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser])
def bundle_session_upload_view(request):
    """Accept a ZIP file or URL, create a BundleSession, return session_id."""
    serializer = BundleUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        session = create_bundle_session(
            user=request.user,
            file_obj=serializer.validated_data.get("file"),
            url=serializer.validated_data.get("url"),
        )
    except ValueError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        BundleSessionSerializer(session).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def bundle_session_introspect_view(request, session_id):
    """Run BundleProcessor / inspectors on the session's bundle."""
    try:
        session = BundleSession.objects.get(session_id=session_id)
    except BundleSession.DoesNotExist:
        return Response(
            {"detail": "Bundle session not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        session = introspect_bundle_session(session)
    except FileNotFoundError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(BundleSessionSerializer(session).data, status=status.HTTP_200_OK)


@api_view(["GET", "PATCH"])
@permission_classes([permissions.IsAuthenticated])
def bundle_session_detail_view(request, session_id):
    """Get or update a BundleSession."""
    try:
        session = BundleSession.objects.get(session_id=session_id)
    except BundleSession.DoesNotExist:
        return Response(
            {"detail": "Bundle session not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(BundleSessionSerializer(session).data, status=status.HTTP_200_OK)

    # PATCH
    serializer = BundleSessionUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if "product_yaml" in serializer.validated_data:
        session.product_yaml = serializer.validated_data["product_yaml"]
    if "jsonld_draft" in serializer.validated_data:
        session.jsonld_draft = serializer.validated_data["jsonld_draft"]
    if "profile_id" in serializer.validated_data:
        session.profile_id = serializer.validated_data["profile_id"]

    session.save()
    return Response(BundleSessionSerializer(session).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([JSONParser])
def bundle_session_submit_view(request, session_id):
    """Save bundle session to catalog and optionally push to ADA."""
    try:
        session = BundleSession.objects.get(session_id=session_id)
    except BundleSession.DoesNotExist:
        return Response(
            {"detail": "Bundle session not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = BundleSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    catalog_record_id = serializer.validated_data.get("catalog_record_id")

    try:
        result = submit_bundle_session(session, catalog_record_id=catalog_record_id)
    except AdaClientError as exc:
        return Response(
            {"detail": "ADA API error.", "ada_error": exc.detail},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(result, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([JSONParser])
def bundle_session_select_product_view(request, session_id):
    """Parse a user-selected file from the bundle as product.yaml."""
    try:
        session = BundleSession.objects.get(session_id=session_id)
    except BundleSession.DoesNotExist:
        return Response(
            {"detail": "Bundle session not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    filepath = request.data.get("filepath", "").strip()
    if not filepath:
        return Response(
            {"detail": "'filepath' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        session = select_product_yaml(session, filepath)
    except FileNotFoundError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_404_NOT_FOUND,
        )
    except ValueError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(BundleSessionSerializer(session).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# DOI lookup (for Update Existing Metadata flow)
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def doi_lookup_view(request):
    """
    Look up an ADA record by DOI and return its JSON-LD representation.

    Query params:
        doi — the DOI to look up
    """
    doi = request.query_params.get("doi", "").strip()
    if not doi:
        return Response(
            {"detail": "Query parameter 'doi' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        client = AdaClient()
        ada_record = client.get_record(doi)
        jsonld = ada_to_jsonld(ada_record)
        return Response({"jsonld": jsonld, "ada_record": ada_record}, status=status.HTTP_200_OK)
    except AdaClientError as exc:
        return Response(
            {"detail": "ADA API error.", "ada_error": exc.detail},
            status=status.HTTP_502_BAD_GATEWAY,
        )
