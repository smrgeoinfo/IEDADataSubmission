import uuid

from django.conf import settings
from django.db import models


class AdaRecordLink(models.Model):
    """Tracks the link between an IEDA Record and its counterpart in ADA."""

    ieda_record = models.OneToOneField(
        "records.Record",
        on_delete=models.CASCADE,
        related_name="ada_link",
    )
    ada_record_id = models.IntegerField(unique=True, help_text="ADA's record integer primary key")
    ada_doi = models.CharField(max_length=255, blank=True, default="", db_index=True)
    ada_status = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="ADA process status (e.g. draft, received, processing, processed, error)",
    )
    last_pushed_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    push_checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="SHA-256 of the last pushed payload for change detection",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ADA Record Link"
        verbose_name_plural = "ADA Record Links"

    def __str__(self):
        return f"IEDA {self.ieda_record_id} <-> ADA {self.ada_record_id}"


class BundleSession(models.Model):
    """Tracks an in-progress bundle upload and introspection session."""

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        INTROSPECTING = "introspecting", "Introspecting"
        READY = "ready", "Ready"
        SUBMITTED = "submitted", "Submitted"

    session_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bundle_sessions",
    )
    bundle_path = models.CharField(
        max_length=500,
        help_text="Temp file path or URL of the uploaded bundle",
    )
    product_yaml = models.JSONField(
        null=True,
        blank=True,
        help_text="Parsed product.yaml if found in the bundle",
    )
    introspection_result = models.JSONField(
        null=True,
        blank=True,
        help_text="File inspection results from bundle introspection",
    )
    jsonld_draft = models.JSONField(
        null=True,
        blank=True,
        help_text="In-progress JSON-LD metadata document",
    )
    profile_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Selected OGC Building Block profile identifier",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bundle Session"
        verbose_name_plural = "Bundle Sessions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"BundleSession {self.session_id} ({self.status})"
