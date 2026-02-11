"""
DRF views for the ADA Bridge API.

Endpoints:
    POST /api/ada-bridge/push/{record_id}/        — push record to ADA
    POST /api/ada-bridge/sync/{record_id}/        — sync status from ADA
    GET  /api/ada-bridge/status/{record_id}/      — get AdaRecordLink info
    POST /api/ada-bridge/bundle/introspect/       — upload ZIP, return metadata
    POST /api/ada-bridge/bundle/upload/{record_id}/ — upload bundle to linked ADA record
"""

from rest_framework import permissions, status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from ada_bridge.client import AdaClientError
from ada_bridge.models import AdaRecordLink
from ada_bridge.serializers import (
    AdaRecordLinkSerializer,
    BundleUploadSerializer,
    PushResponseSerializer,
    SyncResponseSerializer,
)
from ada_bridge.services import (
    push_record_to_ada,
    sync_ada_status,
    upload_bundle_and_introspect,
)
from records.models import Record


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


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser])
def bundle_introspect_view(request):
    """Upload a ZIP bundle and return introspection results."""
    serializer = BundleUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    file_obj = serializer.validated_data["file"]
    result = upload_bundle_and_introspect(file_obj)
    return Response(result, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser])
def bundle_upload_view(request, record_id):
    """Upload a bundle to a linked ADA record."""
    serializer = BundleUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    file_obj = serializer.validated_data["file"]

    try:
        result = upload_bundle_and_introspect(file_obj, ieda_record_id=record_id)
    except AdaClientError as exc:
        return Response(
            {"detail": "ADA API error.", "ada_error": exc.detail},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(result, status=status.HTTP_200_OK)
