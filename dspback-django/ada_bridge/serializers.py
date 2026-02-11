"""
Request / response serializers for the ADA Bridge API endpoints.
"""

from rest_framework import serializers

from ada_bridge.models import AdaRecordLink


class AdaRecordLinkSerializer(serializers.ModelSerializer):
    """Read-only representation of an ADA ↔ IEDA link."""

    ieda_record_id = serializers.UUIDField(source="ieda_record.id", read_only=True)

    class Meta:
        model = AdaRecordLink
        fields = [
            "id",
            "ieda_record_id",
            "ada_record_id",
            "ada_doi",
            "ada_status",
            "last_pushed_at",
            "last_synced_at",
            "push_checksum",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PushResponseSerializer(serializers.Serializer):
    """Response returned after a push operation."""

    ada_record_id = serializers.UUIDField()
    ada_status = serializers.CharField()
    ada_doi = serializers.CharField(allow_blank=True)
    pushed_at = serializers.DateTimeField(source="last_pushed_at")


class SyncResponseSerializer(serializers.Serializer):
    """Response returned after a sync operation."""

    ada_record_id = serializers.UUIDField()
    ada_status = serializers.CharField()
    ada_doi = serializers.CharField(allow_blank=True)
    synced_at = serializers.DateTimeField(source="last_synced_at")


class BundleUploadSerializer(serializers.Serializer):
    """Request for bundle upload / introspection."""

    file = serializers.FileField()
    record_id = serializers.UUIDField(required=False, help_text="IEDA record ID to link the bundle to")
