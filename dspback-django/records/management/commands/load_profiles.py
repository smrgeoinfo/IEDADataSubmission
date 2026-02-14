"""Load metadata profiles from OGC Building Block build output.

Usage:
    python manage.py load_profiles
    python manage.py load_profiles --profiles-dir /path/to/profiles
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from records.models import Profile

# Base profile name for all ADA technique profiles
ADA_BASE_PROFILE = "adaProduct"

def _default_profiles_dir() -> str:
    """Resolve the default profiles directory.

    In Docker the submodule is mounted at /BuildingBlockSubmodule.
    Locally it sits next to dspback-django in the repo root.
    """
    docker_path = Path("/BuildingBlockSubmodule/build/jsonforms/profiles")
    if docker_path.is_dir():
        return str(docker_path)
    # Fallback: relative to the manage.py location (repo root / dspback-django)
    local_path = Path(__file__).resolve().parents[4] / "BuildingBlockSubmodule/build/jsonforms/profiles"
    return str(local_path)


class Command(BaseCommand):
    help = "Load or update profiles from OGC Building Block JSON Forms output"

    def add_arguments(self, parser):
        parser.add_argument(
            "--profiles-dir",
            type=str,
            default=None,
            help="Path to the profiles directory (default: ../BuildingBlockSubmodule/build/jsonforms/profiles/)",
        )

    def handle(self, *args, **options):
        profiles_dir = Path(options["profiles_dir"] or _default_profiles_dir())

        if not profiles_dir.is_dir():
            self.stderr.write(self.style.ERROR(f"Profiles directory not found: {profiles_dir}"))
            return

        # First pass: create/update all profiles
        loaded = []
        for subdir in sorted(profiles_dir.iterdir()):
            if not subdir.is_dir():
                continue

            schema_path = subdir / "schema.json"
            if not schema_path.exists():
                self.stderr.write(self.style.WARNING(f"Skipping {subdir.name}: no schema.json"))
                continue

            name = subdir.name
            schema = json.loads(schema_path.read_text(encoding="utf-8"))

            uischema = {}
            uischema_path = subdir / "uischema.json"
            if uischema_path.exists():
                uischema = json.loads(uischema_path.read_text(encoding="utf-8"))

            defaults = {}
            defaults_path = subdir / "defaults.json"
            if defaults_path.exists():
                defaults = json.loads(defaults_path.read_text(encoding="utf-8"))

            description = schema.get("description", "")

            profile, created = Profile.objects.update_or_create(
                name=name,
                defaults={
                    "schema": schema,
                    "uischema": uischema,
                    "defaults": defaults,
                    "description": description,
                },
            )

            action = "Created" if created else "Updated"
            self.stdout.write(f"  {action}: {name}")
            loaded.append(name)

        # Second pass: set base_profile and inherit uischema/defaults
        # for all ADA technique profiles
        try:
            parent = Profile.objects.get(name=ADA_BASE_PROFILE)
        except Profile.DoesNotExist:
            parent = None
        if parent:
            for profile in Profile.objects.filter(name__startswith="ada").exclude(name=ADA_BASE_PROFILE):
                updated_fields = []
                if profile.base_profile != parent:
                    profile.base_profile = parent
                    updated_fields.append("base_profile")
                    self.stdout.write(f"  Linked: {profile.name} → {ADA_BASE_PROFILE}")
                # Inherit uischema/defaults from base if not provided
                if not profile.uischema and parent.uischema:
                    profile.uischema = parent.uischema
                    updated_fields.append("uischema")
                    self.stdout.write(f"  Inherited uischema: {profile.name} ← {ADA_BASE_PROFILE}")
                if not profile.defaults and parent.defaults:
                    profile.defaults = parent.defaults
                    updated_fields.append("defaults")
                    self.stdout.write(f"  Inherited defaults: {profile.name} ← {ADA_BASE_PROFILE}")
                if updated_fields:
                    profile.save(update_fields=updated_fields)

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(loaded)} profiles: {', '.join(loaded)}"))
