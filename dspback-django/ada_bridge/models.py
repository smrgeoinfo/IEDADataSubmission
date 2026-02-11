import uuid

from django.db import models


class AdaRecordLink(models.Model):
    """Tracks the link between an IEDA Record and its counterpart in ADA."""

    ieda_record = models.OneToOneField(
        "records.Record",
        on_delete=models.CASCADE,
        related_name="ada_link",
    )
    ada_record_id = models.UUIDField(unique=True, help_text="ADA's record primary key")
    ada_doi = models.CharField(max_length=255, blank=True, default="")
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
