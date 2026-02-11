"""
Request / response serializers for the ADA Bridge API endpoints.
"""

from rest_framework import serializers

from ada_bridge.models import AdaRecordLink, BundleSession


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

    ada_record_id = serializers.IntegerField()
    ada_status = serializers.CharField()
    ada_doi = serializers.CharField(allow_blank=True)
    pushed_at = serializers.DateTimeField(source="last_pushed_at")


class SyncResponseSerializer(serializers.Serializer):
    """Response returned after a sync operation."""

    ada_record_id = serializers.IntegerField()
    ada_status = serializers.CharField()
    ada_doi = serializers.CharField(allow_blank=True)
    synced_at = serializers.DateTimeField(source="last_synced_at")


class BundleUploadSerializer(serializers.Serializer):
    """Request for bundle upload / introspection."""

    file = serializers.FileField(required=False)
    url = serializers.URLField(required=False, help_text="URL to a ZIP bundle file")
    record_id = serializers.UUIDField(required=False, help_text="IEDA record ID to link the bundle to")

    def validate(self, data):
        if not data.get("file") and not data.get("url"):
            raise serializers.ValidationError("Either 'file' or 'url' must be provided.")
        return data


class BundleSessionSerializer(serializers.ModelSerializer):
    """Read/write representation of a BundleSession."""

    class Meta:
        model = BundleSession
        fields = [
            "id",
            "session_id",
            "bundle_path",
            "product_yaml",
            "introspection_result",
            "jsonld_draft",
            "profile_id",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "session_id",
            "bundle_path",
            "introspection_result",
            "status",
            "created_at",
            "updated_at",
        ]


class BundleSessionUpdateSerializer(serializers.Serializer):
    """Partial update for a BundleSession."""

    product_yaml = serializers.JSONField(required=False)
    jsonld_draft = serializers.JSONField(required=False)
    profile_id = serializers.CharField(required=False)


class BundleSubmitSerializer(serializers.Serializer):
    """Request to submit a bundle session."""

    catalog_record_id = serializers.UUIDField(
        required=False,
        help_text="Existing catalog record ID to link and push",
    )
