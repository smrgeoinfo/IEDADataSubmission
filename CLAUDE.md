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

## Profiles (38 total)

- **ADA** (36): `adaProduct` (base) + 35 technique-specific profiles
  - Original 4: `adaEMPA`, `adaXRD`, `adaICPMS`, `adaVNMIR`
  - Generated 31: `adaAIVA`, `adaAMS`, `adaARGT`, `adaDSC`, `adaEAIRMS`, `adaFTICRMS`, `adaGCMS`, `adaGPYC`, `adaIC`, `adaICPOES`, `adaL2MS`, `adaLAF`, `adaLCMS`, `adaLIT`, `adaNGNSMS`, `adaNanoIR`, `adaNanoSIMS`, `adaPSFD`, `adaQRIS`, `adaRAMAN`, `adaRITOFNGMS`, `adaSEM`, `adaSIMS`, `adaSLS`, `adaSVRUEC`, `adaTEM`, `adaToFSIMS`, `adaUVFM`, `adaVLM`, `adaXANES`, `adaXCT`
- **CDIF** (2): `CDIFDiscovery`, `CDIFxas`

## Profile Generator

`tools/generate_profiles.py` is a data-driven generator that creates all technique profile building blocks from a single `PROFILES` config dict. Each profile gets: `schema.yaml`, `bblock.json`, `context.jsonld`, `description.md`, `examples.yaml`.

```bash
# Generate all profiles
python tools/generate_profiles.py

# Generate a single profile
python tools/generate_profiles.py adaSEM

# List all available profiles
python tools/generate_profiles.py --list
```

The generator produces technique profile schemas that constrain `schema:additionalType` at the product and hasPart levels. File-type constraints (image, tabular, etc.) come from the shared `files/schema.yaml` building block via `allOf` composition — individual profiles no longer need file-type refs.

## Adding a New Profile

For **ADA technique profiles**, add an entry to `PROFILES` in `generate_profiles.py` and re-run the generator. Then:
1. Run `generate_profiles.py` to create the building block directory
2. Run `resolve_schema.py` to produce `resolvedSchema.json`
3. Add to `TERMCODE_TO_PROFILE` in `update_conformsto.py`, `validate_instance.py`, and `yaml_to_jsonld.py`
4. Add to `ADA_PROFILES` in `convert_for_jsonforms.py`
5. Add to `KNOWN_PROFILES` in `validate_instance.py`
6. Create `uischema.json` + `defaults.json` in `_sources/jsonforms/profiles/` (if UI form needed)
7. Add `profileNames` entry in `geodat.ada-profile-form.vue` (if UI form needed)
8. Add i18n strings in `messages.ts` (if UI form needed)
9. `docker exec catalog python manage.py load_profiles`

For **CDIF profiles**, see `agents.md` > "Adding a New CDIF Profile".

## Common Patterns

- `@type` uses `type: array` + `contains: {const: "..."}` + `minItems: 1` for extensibility
- `schema:propertyID` in `contains` must use `{type: array, contains: {const: "..."}}` (not bare `const`) because AdditionalProperty base defines it as array
- `prov:wasGeneratedBy` must be `type: array` across all composed schemas (cdifOptional requires array)
- UISchema scopes must include `schema:` prefix: `#/properties/schema:name` not `#/properties/name`
- Frontend profile selection auto-discovers CDIF profiles (names starting with `CDIF`, excluding `CDIFDiscovery`)
- ADA technique profiles need `base_profile` FK set via `PARENT_PROFILES` in `load_profiles.py`

## Technique-Specific Measurement Details

ADA technique profiles (adaVNMIR, adaEMPA, adaXRD) display measurement detail properties from building block detail schemas. These properties live inside `componentType` at the hasPart item level (flat — no `fileDetail` wrapper).

- **Schema pipeline**: `_collect_component_type_info()` in `convert_for_jsonforms.py` collects both `@type` enum values AND non-`@type` detail properties from componentType anyOf branches, merging them into `componentType.properties`. The file-type `anyOf` (from `files/schema.yaml`) appears at the hasPart items level; `_is_file_type_anyof()` detects it and `simplify_file_detail_anyof()` merges all branches into flat properties on the hasPart item.
- **UISchema injection**: `PROFILE_MEASUREMENT_CONTROLS` in `uischema_injection.py` maps technique profiles to measurement detail UI controls. `_inject_measurement_group()` inserts the group after each ComponentType dropdown in all file-type detail groups (Image, Tabular, Data Cube, Document)
- **adaProduct/adaICPMS/CDIF**: No measurement detail groups injected (not in `PROFILE_MEASUREMENT_CONTROLS`)
- To add measurement details for a new technique, add an entry to `PROFILE_MEASUREMENT_CONTROLS` using `_ct_ctrl(prop, label)` helper

## Distribution Schema Flattening

The `schema:distribution` schema is `type: array` in the canonical JSON-LD but the uischema scopes into it as an object (archive info + hasPart file list as separate groups). Both `MetadataFormStep.vue` (bundle wizard) and `geodat.ada-profile-form.vue` (profile form) flatten the schema at load time:

1. **Schema**: `_flattenDistributionSchema()` converts `distribution` from `{type: "array", items: {...}}` to the items object
2. **Data load**: Unwrap `distribution` array to single object; unwrap `encodingFormat` arrays to strings
3. **Data save**: Wrap `distribution` object back to array; serializer wraps `encodingFormat` strings back to arrays

This is required because `uischema_injection.py` also converts `encodingFormat` from array to string (with MIME enum) so that SHOW rule conditions (`{"const": "text/csv"}`) work against simple string values.

## CzForm Rule Conditions

CzForm (cznet-vue-core) does NOT reliably support `enum` in rule conditions. Use OR with individual `{"const": value}` conditions instead:
```json
{"type": "OR", "conditions": [
  {"scope": "#/properties/field", "schema": {"const": "value1"}},
  {"scope": "#/properties/field", "schema": {"const": "value2"}}
]}
```

## Form Hints (Hover-to-Show)

CzForm's `showUnfocusedDescription: false` config controls hint visibility per-control. The Vuetify-level `persistent-hint` in `formConfig.vuetify.commonAttrs` must be `false` to avoid overriding this. CSS hover-to-show rules must target both `.metadata-form-step` and `.v-overlay__content` to reach CzForm content rendered in Vuetify dialog/overlay portals.

## Draft Record Validation

Draft records (`status: 'draft'`) skip JSON Schema validation in `RecordSerializer.validate()`. This allows importing non-conforming metadata (e.g., old ADA format) for editing in the form. The `create()` serializer handles identifier conflicts via upsert (same owner updates existing record; different owner mints fresh UUID).

## Save vs Submit to ADA (Two-Step Flow)

**"Save Changes"** saves to the local catalog only. `RecordSerializer.update()` extracts `title`/`creators`, stamps `sdDatePublished`, calls `upsert_known_entities()`, but does NOT touch the identifier. This avoids hash-based `@id` conflicts when `populateOnSave()` generates a new hash.

**"Submit to ADA"** saves locally first (PATCH), then calls `POST /api/ada-bridge/push/{record_id}/`. The push flow in `ada_bridge/services.py`:
1. `_apply_versioning()` runs if `jsonld["@id"] != record.identifier` — deprecates conflicting family records, bumps to `_N+1` suffix
2. Sets `record.status = "published"`
3. Translates JSON-LD → ADA payload, computes checksum, creates/updates in ADA
4. Saves `AdaRecordLink` with `ada_status`, `ada_doi`

The record list API (`RecordListSerializer`) exposes `ada_status` and `ada_doi` fields from `AdaRecordLink`. The frontend shows ADA status/DOI in the profile form (alert banner) and submissions list (chips + "Push to ADA" button).

Re-import versioning in `create()` (for DOI lookups) is unchanged.
