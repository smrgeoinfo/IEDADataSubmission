import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models


class Profile(models.Model):
    """A metadata schema profile (e.g. CDIFDiscovery, adaEMPA)."""

    name = models.CharField(max_length=255, unique=True, db_index=True)
    version = models.CharField(max_length=32, default="1.0.0")
    schema = models.JSONField(default=dict, help_text="JSON Schema for validation")
    uischema = models.JSONField(default=dict, blank=True, help_text="UI Schema for form rendering")
    defaults = models.JSONField(default=dict, blank=True, help_text="Default values template")
    description = models.TextField(blank=True, default="")
    base_profile = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_profiles",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} v{self.version}"


class Record(models.Model):
    """A JSON-LD metadata record."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        Profile,
        on_delete=models.PROTECT,
        related_name="records",
    )
    jsonld = models.JSONField(default=dict, help_text="Complete JSON-LD document")
    title = models.TextField(blank=True, default="", help_text="Extracted from schema:name")
    creators = ArrayField(
        models.TextField(),
        default=list,
        blank=True,
        help_text="Extracted from schema:creator",
    )
    identifier = models.TextField(
        unique=True,
        db_index=True,
        help_text="DOI or UUID identifier",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="records",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            GinIndex(fields=["jsonld"], name="record_jsonld_gin"),
        ]

    def __str__(self):
        return f"{self.title or self.identifier} ({self.profile.name})"


class KnownPerson(models.Model):
    """Accumulated person entities extracted from saved records."""

    name = models.TextField(db_index=True)
    identifier_type = models.TextField(blank=True, default="")
    identifier_value = models.TextField(blank=True, default="")
    identifier_url = models.TextField(blank=True, default="")
    affiliation_name = models.TextField(blank=True, default="")
    affiliation_identifier_type = models.TextField(blank=True, default="")
    affiliation_identifier_value = models.TextField(blank=True, default="")
    affiliation_identifier_url = models.TextField(blank=True, default="")
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "identifier_value"],
                name="unique_person_name_id",
            ),
        ]

    def __str__(self):
        return self.name


class KnownOrganization(models.Model):
    """Accumulated organization entities extracted from saved records."""

    name = models.TextField(db_index=True)
    identifier_type = models.TextField(blank=True, default="")
    identifier_value = models.TextField(blank=True, default="")
    identifier_url = models.TextField(blank=True, default="")
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "identifier_value"],
                name="unique_org_name_id",
            ),
        ]

    def __str__(self):
        return self.name
