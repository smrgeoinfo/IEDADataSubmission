"""Backfill KnownPerson and KnownOrganization from existing records."""

from django.core.management.base import BaseCommand

from records.models import Record
from records.services import upsert_known_entities


class Command(BaseCommand):
    help = "Scan all records and extract person/organization entities into KnownPerson/KnownOrganization tables."

    def handle(self, *args, **options):
        records = Record.objects.all()
        total = records.count()
        self.stdout.write(f"Processing {total} records...")

        success = 0
        for i, record in enumerate(records.iterator(), 1):
            try:
                upsert_known_entities(record.jsonld)
                success += 1
            except Exception as exc:
                self.stderr.write(f"  Error on record {record.pk}: {exc}")

            if i % 100 == 0:
                self.stdout.write(f"  Processed {i}/{total}...")

        self.stdout.write(self.style.SUCCESS(
            f"Done. Processed {success}/{total} records successfully."
        ))
