import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ada_bridge", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BundleSession",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "session_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        unique=True,
                        db_index=True,
                    ),
                ),
                (
                    "bundle_path",
                    models.CharField(
                        help_text="Temp file path or URL of the uploaded bundle",
                        max_length=500,
                    ),
                ),
                (
                    "product_yaml",
                    models.JSONField(
                        blank=True,
                        help_text="Parsed product.yaml if found in the bundle",
                        null=True,
                    ),
                ),
                (
                    "introspection_result",
                    models.JSONField(
                        blank=True,
                        help_text="File inspection results from bundle introspection",
                        null=True,
                    ),
                ),
                (
                    "jsonld_draft",
                    models.JSONField(
                        blank=True,
                        help_text="In-progress JSON-LD metadata document",
                        null=True,
                    ),
                ),
                (
                    "profile_id",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Selected OGC Building Block profile identifier",
                        max_length=100,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "Created"),
                            ("introspecting", "Introspecting"),
                            ("ready", "Ready"),
                            ("submitted", "Submitted"),
                        ],
                        default="created",
                        max_length=20,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bundle_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Bundle Session",
                "verbose_name_plural": "Bundle Sessions",
                "ordering": ["-created_at"],
            },
        ),
    ]
