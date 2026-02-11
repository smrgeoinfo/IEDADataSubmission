# Claude Code Project Memory

## Project Overview

IEDA Data Submission Portal — monorepo with FastAPI backend (`dspback/`), Django catalog backend (`dspback-django/`), Vue 3 frontend (`dspfront/`), and OGC Building Blocks (`OCGbuildingBlockTest/`). Three are git submodules.

## Key Commands

```bash
# Resolve a building block schema
cd OCGbuildingBlockTest
python tools/resolve_schema.py <ProfileName> --flatten-allof -o _sources/profiles/<ProfileName>/resolvedSchema.json

# Convert to JSON Forms
python tools/convert_for_jsonforms.py --profile <ProfileName>
python tools/convert_for_jsonforms.py --all

# Compare YAML vs JSON schemas for consistency
python tools/compare_schemas.py

# Validate example against resolved schema
python -c "import json, jsonschema; s=json.load(open('resolvedSchema.json')); d=json.load(open('example.json')); jsonschema.validate(d,s)"

# Load profiles into catalog
docker exec catalog python manage.py load_profiles

# Run Django tests
docker exec catalog python manage.py test records
docker exec catalog python manage.py test ada_bridge

# Deploy (demo)
docker compose -f docker-compose-demo.yml up -d --build
```

## Git Submodule Structure

- `OCGbuildingBlockTest/` — master branch, remote: `smrgeoinfo/OCGbuildingBlockTest`
- `dspfront/` — develop branch, remote: `smrgeoinfo/dspfront`
- `dspback/` — develop branch, remote: `smrgeoinfo/dspback`
- Parent repo — main branch

Push changes: commit in submodule first, push submodule, then commit+push parent.

## Schema Pipeline

```
schema.yaml → resolve_schema.py → resolvedSchema.json → convert_for_jsonforms.py → schema.json (Draft 7)
```

Building blocks have parallel files: `schema.yaml` (source) and `{name}Schema.json`. Keep them in sync — run `compare_schemas.py` after editing.

## Profiles (7 total)

- **ADA**: `adaProduct` (base), `adaEMPA`, `adaXRD`, `adaICPMS`, `adaVNMIR`
- **CDIF**: `CDIFDiscovery`, `CDIFxas`

## Adding a New Profile

See `agents.md` > "Adding a New ADA Profile" or "Adding a New CDIF Profile" for step-by-step guides.

Quick checklist:
1. Create building blocks under `_sources/`
2. Create profile `schema.yaml` with `allOf` composition
3. Resolve schema → JSON Forms conversion
4. Create `uischema.json` + `defaults.json` in `_sources/jsonforms/profiles/`
5. Add to `CDIF_PROFILES` or `ADA_PROFILES` in `convert_for_jsonforms.py`
6. Add `profileNames` entry in `geodat.ada-profile-form.vue`
7. Add i18n strings in `messages.ts`
8. `docker exec catalog python manage.py load_profiles`

## Common Patterns

- `@type` uses `type: array` + `contains: {const: "..."}` + `minItems: 1` for extensibility
- `schema:propertyID` in `contains` must use `{type: array, contains: {const: "..."}}` (not bare `const`) because AdditionalProperty base defines it as array
- `prov:wasGeneratedBy` must be `type: array` across all composed schemas (cdifOptional requires array)
- UISchema scopes must include `schema:` prefix: `#/properties/schema:name` not `#/properties/name`
- Frontend profile selection auto-discovers CDIF profiles (names starting with `CDIF`, excluding `CDIFDiscovery`)
- ADA technique profiles need `base_profile` FK set via `PARENT_PROFILES` in `load_profiles.py`
