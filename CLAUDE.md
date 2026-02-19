# Claude Code Project Memory

## Project Overview

IEDA Data Submission Portal — monorepo with FastAPI backend (`dspback/`), Django catalog backend (`dspback-django/`), Vue 3 frontend (`dspfront/`), and OGC Building Blocks (`BuildingBlockSubmodule/`). Three are git submodules.

## Key Commands

```bash
# Resolve a building block schema
cd BuildingBlockSubmodule
python tools/resolve_schema.py <ProfileName> --flatten-allof -o _sources/profiles/<ProfileName>/resolvedSchema.json

# Resolve all building blocks with external $refs (writes resolvedSchema.json next to each schema.yaml)
python tools/resolve_schema.py --all

# Resolve an arbitrary schema file
python tools/resolve_schema.py --file _sources/cdifProperties/cdifDataCube/schema.yaml -o _sources/cdifProperties/cdifDataCube/resolvedSchema.json

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

- `BuildingBlockSubmodule/` — main branch, remote: `usgin/metadataBuildingBlocks`
- `dspfront/` — develop branch, remote: `smrgeoinfo/dspfront`
- `dspback/` — develop branch, remote: `smrgeoinfo/dspback`
- Parent repo — main branch

Push changes: commit in submodule first, push submodule, then commit+push parent.

## Building Block Directory Layout

Inside `BuildingBlockSubmodule/_sources/`:

- `cdifProperties/` — CDIF-specific building blocks: `cdifMandatory`, `cdifOptional`, `cdifDataCube`, `cdifPhysicalMapping`, `cdifTabularData`, `cdifVariableMeasured`
- `schemaorgProperties/` — schema.org vocabulary building blocks: `action`, `additionalProperty`, `dataDownload`, `definedTerm`, `identifier`, `person`, `organization`, etc.
- `adaProperties/` — ADA-specific building blocks: `files`, `instrument`, `laboratory`, detail schemas, etc.
- `profiles/` — Assembled profile schemas (adaProduct, CDIFDiscovery, CDIFDataDescription, CDIFxas, technique profiles)
- `xasProperties/` — XAS-specific building blocks
- `provProperties/` — Provenance building blocks
- `qualityProperties/` — Quality measure building blocks

## Schema Pipeline

```
schema.yaml → resolve_schema.py → resolvedSchema.json → convert_for_jsonforms.py → schema.json (Draft 7)
```

Building blocks have parallel files: `schema.yaml` (source) and `{name}Schema.json`. Keep them in sync — run `compare_schemas.py` after editing. Any building block with external `$ref`s should have a `resolvedSchema.json` — run `resolve_schema.py --all` to regenerate them all.

## Profiles (39 total)

- **ADA** (36): `adaProduct` (base) + 35 technique-specific profiles
  - Original 4: `adaEMPA`, `adaXRD`, `adaICPMS`, `adaVNMIR`
  - Generated 31: `adaAIVA`, `adaAMS`, `adaARGT`, `adaDSC`, `adaEAIRMS`, `adaFTICRMS`, `adaGCMS`, `adaGPYC`, `adaIC`, `adaICPOES`, `adaL2MS`, `adaLAF`, `adaLCMS`, `adaLIT`, `adaNGNSMS`, `adaNanoIR`, `adaNanoSIMS`, `adaPSFD`, `adaQRIS`, `adaRAMAN`, `adaRITOFNGMS`, `adaSEM`, `adaSIMS`, `adaSLS`, `adaSVRUEC`, `adaTEM`, `adaToFSIMS`, `adaUVFM`, `adaVLM`, `adaXANES`, `adaXCT`
- **CDIF** (3): `CDIFDiscovery`, `CDIFDataDescription`, `CDIFxas`

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
6. Add entry to `PROFILE_COMPONENT_TYPES` in `uischema_injection.py` (MIME filtering and componentType dropdowns are auto-derived from this dict)
7. Create `uischema.json` + `defaults.json` in `_sources/jsonforms/profiles/` (if UI form needed)
8. Add `profileNames` entry in `geodat.ada-profile-form.vue` (if UI form needed)
9. Add i18n strings in `messages.ts` (if UI form needed)
10. `docker exec catalog python manage.py load_profiles`

For **CDIF profiles**, see `agents.md` > "Adding a New CDIF Profile".

## Common Patterns

- `@type` uses `type: array` + `contains: {const: "..."}` + `minItems: 1` for extensibility
- `schema:propertyID` in `contains` must use `{type: array, contains: {const: "..."}}` (not bare `const`) because AdditionalProperty base defines it as array
- `prov:wasGeneratedBy` must be `type: array` across all composed schemas (cdifOptional requires array)
- UISchema scopes must include `schema:` prefix: `#/properties/schema:name` not `#/properties/name`
- Frontend profile selection auto-discovers CDIF profiles (names starting with `CDIF`, excluding `CDIFDiscovery`)
- ADA technique profiles need `base_profile` FK set via `PARENT_PROFILES` in `load_profiles.py`

## Per-Profile MIME and componentType Filtering

Technique profiles show only the MIME types and componentType dropdown values relevant to their technique. All filtering is driven by a single dict `PROFILE_COMPONENT_TYPES` in `uischema_injection.py`.

- **`PROFILE_COMPONENT_TYPES`**: Maps each of the 35 technique profiles to its allowed `ada:`-prefixed component types. `adaProduct` and unknown profiles are absent → no filtering (full lists).
- **MIME filtering (hasPart level)**: `_derive_profile_mime_categories()` checks which global category lists (IMAGE, TABULAR, DATACUBE, DOCUMENT) the profile's types intersect. Document and collection (ZIP) categories are always included. `_get_profile_mime_enum()` returns the filtered MIME list.
- **MIME filtering (distribution level)**: `PROFILE_DIST_MIME_CATEGORIES` maps profiles to restricted MIME categories for the top-level distribution (e.g., `adaL2MS` → dataCube only). `_get_dist_mime_enum()` returns archive + primary data + structured data MIMEs. Profiles not in this dict fall back to `_get_profile_mime_enum()`.
- **componentType dropdowns**: `_get_profile_category_components()` intersects the profile's types with each per-category global list, then appends `GENERIC_COMPONENT_TYPES` (always available). Called from `inject_schema_defaults()` when building `_CT_CATEGORIES`.
- **Adding a new profile**: Add entry to `PROFILE_COMPONENT_TYPES` — MIME filtering and componentType dropdowns are auto-derived. Optionally add to `PROFILE_DIST_MIME_CATEGORIES` if the distribution-level MIME list should be narrower than the hasPart list.

## Technique-Specific Measurement Details

ADA technique profiles (adaVNMIR, adaEMPA, adaXRD) display measurement detail properties from building block detail schemas. These properties live inside `componentType` at the hasPart item level (flat — no `fileDetail` wrapper).

- **Schema pipeline**: `_collect_component_type_info()` in `convert_for_jsonforms.py` collects both `@type` enum values AND non-`@type` detail properties from componentType anyOf branches, merging them into `componentType.properties`. The file-type `anyOf` (from `files/schema.yaml`) appears at the hasPart items level; `_is_file_type_anyof()` detects it and `simplify_file_detail_anyof()` merges all branches into flat properties on the hasPart item.
- **UISchema injection**: `PROFILE_MEASUREMENT_CONTROLS` in `uischema_injection.py` maps technique profiles to measurement detail UI controls. `_inject_measurement_group()` inserts the group after each ComponentType dropdown in all file-type detail groups (Image, Tabular, Data Cube, Document)
- **adaProduct/adaICPMS/CDIF**: No measurement detail groups injected (not in `PROFILE_MEASUREMENT_CONTROLS`)
- To add measurement details for a new technique, add an entry to `PROFILE_MEASUREMENT_CONTROLS` using `_ct_ctrl(prop, label)` helper

## File Detail Properties (Flat Structure)

File-type-specific properties (`componentType`, `cdi:hasPhysicalMapping`, CSV metadata, etc.) live directly on distribution and hasPart items — there is no `fileDetail` wrapper object.

- **Schema**: `files/schema.yaml` uses `allOf` with file-type `anyOf` at the top level; `convert_for_jsonforms.py` merges these into flat properties on hasPart items
- **UISchema**: `uischema_injection.py` scopes use `#/properties/{prop}` (via `_fd_ctrl`) and `#/properties/componentType/properties/{prop}` (via `_ct_ctrl`) — no `fileDetail` path segment
- **Serializer**: `serializers.py` runs `_consolidate_component_type()`, `_clean_physical_mapping_items()`, and `_merge_inferred_file_types()` directly on dist/part items
- **Frontend load/save**: `catalog.ts` unwraps/wraps `cdi:formats_InstanceVariable` and populates per-category componentType UI properties directly on dist/part items
- **Bundle wizard**: `MetadataFormStep.vue` assigns CSV metadata and `cdi:hasPhysicalMapping` directly to hasPart items

## Distribution Schema Flattening

The `schema:distribution` schema is `type: array` in the canonical JSON-LD but the uischema scopes into it as an object (archive info + hasPart file list as separate groups). Both `MetadataFormStep.vue` (bundle wizard) and `geodat.ada-profile-form.vue` (profile form) flatten the schema at load time:

1. **Schema**: `_flattenDistributionSchema()` converts `distribution` from `{type: "array", items: {...}}` to the items object
2. **Data load**: Unwrap `distribution` array to single object; unwrap `encodingFormat` arrays to strings
3. **Data save**: Wrap `distribution` object back to array; serializer wraps `encodingFormat` strings back to arrays

This is required because `uischema_injection.py` also converts `encodingFormat` from array to string (with MIME enum) so that SHOW rule conditions (`{"const": "text/csv"}`) work against simple string values.

### Two uischema injection paths for distribution

The stored uischema determines which injection path runs:

- **Array-style** (`#/properties/schema:distribution` scope): `_walk()` injects `DISTRIBUTION_DETAIL` as the array control's detail layout. File-type groups (Image, Tabular, Data Cube, Document) live inside this detail with `_mime_and_download_rule()` SHOW rules using relative scopes (`#/properties/schema:encodingFormat`).
- **Flattened-style** (scopes like `#/properties/schema:distribution/properties/schema:name`): The stored uischema has separate Archive + Distribution (Files) groups. `_walk()` detects the `Category label="Distribution"` and calls `_inject_dist_file_detail_groups()` which: (a) adds a zip-only SHOW rule on the hasPart group, (b) appends `DIST_*_DETAIL_GROUP` constants with full-path scopes (`#/properties/schema:distribution/properties/...`). The `inject_schema_defaults()` function copies file-detail properties (physical mapping, image channels, CSV metadata, etc.) from hasPart items to `dist_props` so CzForm can render the distribution-level controls.

ADA technique profiles currently use the **flattened-style** (inherited from adaProduct's stored uischema).

## CzForm Rule Conditions

CzForm (cznet-vue-core) has strict limitations on rule condition complexity:

1. **No `enum` in conditions** — `{"schema": {"enum": [...]}}` does not reliably fire. Use OR with individual `{"const": value}` conditions instead.
2. **No nested compound conditions** — CzForm cannot evaluate AND wrapping OR, OR wrapping AND, or any deeper nesting. Only **flat** compound conditions work (AND of simple conditions, OR of simple conditions).
3. **Working patterns:**
   - Single condition: `{"scope": "...", "schema": {"const": "value"}}`
   - Flat OR: `{"type": "OR", "conditions": [{simple}, {simple}, ...]}`
   - Flat AND: `{"type": "AND", "conditions": [{simple}, {simple}]}`
4. **Non-working patterns:**
   - `{"type": "AND", "conditions": [{simple}, {"type": "OR", ...}]}` — nested OR inside AND
   - `{"type": "OR", "conditions": [{"type": "AND", ...}, ...]}` — nested AND inside OR
   - `{"schema": {"enum": [...]}}` — enum in condition

If you need AND + multi-value matching (e.g., distributionType == X AND mime in [a, b, c]), you **cannot** express this in a single rule. Either drop one guard (if safe) or restructure the UI to avoid the need.

```json
// GOOD: flat OR of simple conditions
{"type": "OR", "conditions": [
  {"scope": "#/properties/field", "schema": {"const": "value1"}},
  {"scope": "#/properties/field", "schema": {"const": "value2"}}
]}

// BAD: nested compound
{"type": "AND", "conditions": [
  {"scope": "#/properties/a", "schema": {"const": "x"}},
  {"type": "OR", "conditions": [
    {"scope": "#/properties/b", "schema": {"const": "y"}},
    {"scope": "#/properties/b", "schema": {"const": "z"}}
  ]}
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

## Upstream OGC Contributions

Generalized versions of `resolve_schema.py` and `compare_schemas.py` (plus a bblocks-viewer feature) are staged in `ogc-contributions/bblock-template/tools/` and submitted as PRs:

| PR | Target | Status |
|---|---|---|
| [opengeospatial/bblock-template#8](https://github.com/opengeospatial/bblock-template/pull/8) | Schema tools in bblock-template | Open |
| [opengeospatial/bblocks-postprocess#62](https://github.com/opengeospatial/bblocks-postprocess/pull/62) | Schema tools in bblocks-postprocess | Open |
| [ogcincubator/bblocks-viewer#6](https://github.com/ogcincubator/bblocks-viewer/pull/6) | Resolved (JSON) button in viewer | Open |
