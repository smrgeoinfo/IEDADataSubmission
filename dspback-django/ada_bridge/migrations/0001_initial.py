import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("records", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdaRecordLink",
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
                    "ada_record_id",
                    models.UUIDField(
                        help_text="ADA's record primary key",
                        unique=True,
                    ),
                ),
                (
                    "ada_doi",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "ada_status",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="ADA process status (e.g. draft, received, processing, processed, error)",
                        max_length=50,
                    ),
                ),
                (
                    "last_pushed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "last_synced_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "push_checksum",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="SHA-256 of the last pushed payload for change detection",
                        max_length=64,
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
                    "ieda_record",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ada_link",
                        to="records.record",
                    ),
                ),
            ],
            options={
                "verbose_name": "ADA Record Link",
                "verbose_name_plural": "ADA Record Links",
            },
        ),
    ]
