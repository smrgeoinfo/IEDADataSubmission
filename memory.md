# Project Memory

Running log of architectural decisions and significant changes.

## 2026-02-06: Split Instrument Detail Types into Separate Building Blocks

**What changed:** The monolithic `_sources/adaProperties/details/schema.yaml` (which bundled 16 instrument-specific detail types as `$defs`) was split into 16 standalone building blocks, one per detail type.

**New directories** (under `_sources/adaProperties/`):
`detailARGT`, `detailBasemap`, `detailDSC`, `detailEAIRMS`, `detailEMPA`, `detailICPOES`, `detailL2MS`, `detailLAF`, `detailNanoIR`, `detailNanoSIMS`, `detailPSFD`, `detailQRIS`, `detailSLS`, `detailVNMIR`, `detailXCT`, `detailXRD`

Each contains: `schema.yaml`, `bblock.json`, `context.jsonld`, `description.md`.

**Why:** As the profile library expands to cover all ~97 product types in `ADA-AnalyticalMethodsAndAttributes.xlsx`, each technique profile needs to `$ref` only its specific detail type(s). Separate BBs make this possible via `$ref: ../detailXxx/schema.yaml` instead of fragile fragment pointers `../details/schema.yaml#/$defs/xyz_detail`.

**What was updated:**
- 5 referencing schemas updated to use new `$ref` paths: `tabularData`, `imageMap`, `document`, `dataCube`, `otherFile`
- `details/schema.yaml` rewritten as an umbrella schema with `anyOf` referencing all 16 new BBs
- `details/description.md` updated accordingly

**Special cases:** `detailNanoIR`, `detailNanoSIMS`, `detailPSFD` use `$ref: ../stringArray/schema.yaml` for array-valued properties — these sibling BB references remain as-is.

**Naming convention:** `detailXxx` where `Xxx` matches the uppercase technique abbreviation (e.g., `detailEMPA`, `detailXRD`, `detailNanoSIMS`). The `_detail` suffix from the old `$defs` names is dropped.

## 2026-02-07: Tabbed ADA Form UX & Compact Profile Selection

**What changed:**
1. ADA profile forms now render with tabbed navigation (5 tabs: Basic Info, Attribution, Methods & Variables, Distribution, Metadata Record) instead of a single long scroll of groups.
2. The profile selection page (`/metadata/ada`) switched from large cards in a 3-column grid to a compact `v-list` with a search/filter field — designed to scale to 80+ data types.
3. Branding renamed from "CZ Hub" to "IEDA Hub" (browser tab title, PWA manifest, vuex storage key).
4. The cors_server now sends `Cache-Control: no-cache` to prevent stale schema files during development.

**How tabs work:** The `Categorization` type is handled at the parent component level (`cz.ada-profile-form.vue`), not via a custom JSON Forms renderer. CzForm's `renderers` field is internal (not a prop), so custom renderer injection isn't possible. Instead, when the uischema root type is `Categorization`, the parent renders Vuetify `v-tabs` and passes each Category's elements as a `VerticalLayout` uischema to a separate `CzForm` instance per tab. All tabs share the same reactive `data` object. Non-Categorization schemas fall back to the original single-form rendering.

**Profile selection layout:** `cz.ada-select-type.vue` now separates the general product (always first) from analytical methods (alphabetically sorted below an "Analytical Method" divider/subheader). The `methodProfiles` array is pre-sorted alphabetically by key. The search field filters both sections by name and description.

**Files changed:**
- `dspfront/src/components/metadata/cz.ada-profile-form.vue` — Added tab detection, rendering, and state
- `dspfront/src/components/metadata/cz.ada-select-type.vue` — Compact list with search and section divider
- `dspfront/src/constants.ts` — `APP_NAME` → `'IEDA Hub'`
- `dspfront/vite.config.ts` — PWA manifest name/short_name → `'IEDA Hub'`
- `dspfront/src/modules/vuex.ts` — Vuex persisted state key → `'IEDA Hub'`
- `OCGbuildingBlockTest/_sources/jsonforms/profiles/*/uischema.json` (all 5) — Root type changed from `VerticalLayout` to `Categorization` with 5 `Category` elements
- `OCGbuildingBlockTest/tools/cors_server.py` — Added `Cache-Control: no-cache` header

**Note on vuex key change:** Changing the vuex persisted state key from `"CZ Hub"` to `"IEDA Hub"` means previously persisted local state won't carry over — users start with fresh state on first visit after this change.

## 2026-02-07: Django Catalog Backend (Milestone 1)

**What changed:** Added a new Django + DRF backend (`dspback-django/`) that coexists alongside the existing FastAPI backend (`dspback/`). This is the foundation for evolving the system from a CZHub submission tool into a profile-driven metadata catalog.

**Why:** The new catalog backend provides generic Profile and Record management — profiles are loaded from OGC Building Block build output (schema, uischema, defaults), and records store JSON-LD natively with JSON Schema validation. This decouples metadata storage from repository-specific submission logic, enabling 70+ ADA product types and other domains to be added without per-type backend code.

**Architecture:**
- Separate Django service on port 5003, separate `catalog` PostgreSQL database
- Nginx routes `/api/catalog/*` → catalog service, `/api/*` → dspback (existing)
- Zero impact on existing dspback/dspfront — complete coexistence

**New components:**
- `accounts` app — Custom User model with ORCID as `USERNAME_FIELD`, ORCID OAuth views (login/callback/logout), SimpleJWT token issuance with ORCID in `sub` claim, custom DRF auth supporting both `Authorization: Bearer` header and `?access_token=` query param
- `records` app — Profile model (schema/uischema/defaults/base_profile FK), Record model (UUID PK, JSON-LD with GIN index, extracted title/creators/identifier), JSON Schema validation (auto-detects Draft-07 vs Draft-2020-12), field extraction from JSON-LD
- `load_profiles` management command — Reads from OGC BB `build/jsonforms/profiles/`, sets parent relationships (adaEMPA/adaICPMS/adaVNMIR/adaXRD → adaProduct)

**API endpoints (all under `/api/catalog/`):**
- `GET/POST profiles/` — List/create profiles (public read, admin write)
- `GET profiles/{name}/` — Profile detail by name (returns schema+uischema+defaults)
- `GET/POST records/` — List/create records (public read, authenticated write)
- `GET/PATCH/DELETE records/{id}/` — Record CRUD (owner-only write)
- `GET records/{id}/jsonld/` — Raw JSON-LD with `application/ld+json` content type
- `POST records/import-url/`, `POST records/import-file/` — Import from URL or file upload

**Infrastructure:**
- `dspback-django/Dockerfile-dev` — Python 3.12-slim, gunicorn
- `docker-compose-dev.yml` — Added `catalog` service, mounted `OCGbuildingBlockTest` volume, added `scripts/init-catalog-db.sh` to postgres init
- `nginx/nginx-dev.conf` — Added `/api/catalog` location block before `/api`
- `.env` — Added `CATALOG_DATABASE`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`

**Setup for existing installs:** The init script only runs on fresh postgres. For existing installs: `docker exec dsp_postgres psql -U dsp -d dsp -c "CREATE DATABASE catalog OWNER dsp;"`, then `docker exec catalog python manage.py migrate` and `docker exec catalog python manage.py load_profiles`.

**Schema validation note:** The OGC BB schemas use Draft-07 (`$schema: http://json-schema.org/draft-07/schema#`). The validator auto-detects the draft version. Draft-07 lacks `unevaluatedProperties`, so strict `allOf` composition (rejecting unknown properties across composed schemas) isn't possible — typos in property names pass validation silently.

## 2026-02-07: Wire Frontend to Catalog API (Milestone 2)

**What changed:** The ADA and CDIF form components now use the Django catalog API (`/api/catalog/`) for schema loading, record saving, and record editing — eliminating the dependency on a local BB CORS dev server and the dspback FastAPI JSON-LD endpoints. The submissions page gained a "Catalog Records" tab showing records saved to the catalog.

**Architecture after this change:**
```
Frontend Form  ──→  GET /api/catalog/profiles/{name}/  (schema + uischema + defaults)
      │
      └──→  POST /api/catalog/records/  {profile: id, jsonld: {...}}
                                              │
                                    catalog validates against schema
                                    extracts title/creators/identifier
                                              │
My Submissions page  ──→  GET /api/catalog/records/?mine=true  (catalog records tab)
                     ──→  GET /api/submissions                  (dspback submissions tab)
```

**Schema loading:** Both `geodat.ada-profile-form.vue` and `geodat.cdif-form.vue` now make a single request to `GET /api/catalog/profiles/{name}/` instead of three separate requests to `http://localhost:8090/profiles/{name}/{schema,uischema,defaults}.json`. No local BB CORS dev server needed.

**Save target:** Records are POSTed/PATCHed to `/api/catalog/records/` with `{profile: <id>, jsonld: <data>}` instead of to dspback's `/api/metadata/ada/jsonld` or `/api/metadata/cdif/jsonld`. The catalog backend validates against the profile schema and extracts indexed fields.

**Edit support:** Both forms accept a `?record=<uuid>` query param. When present, the form loads the existing record's JSON-LD from the catalog API and pre-populates the form. Save uses PATCH instead of POST.

**Dynamic profile selection:** `geodat.ada-select-type.vue` fetches the profile list from `GET /api/catalog/profiles/` instead of using a hardcoded array. It separates `adaProduct` (no `base_profile`) from technique profiles (have `base_profile === 'adaProduct'`). Falls back to hardcoded profiles if the API call fails. Display names use i18n with fallback to API `name`.

**Submissions page tabs:** `geodat.submissions.vue` has a tab bar: "Repository Submissions" (existing dspback behavior) and "Catalog Records" (fetches from catalog API with `?mine=true`). Catalog records show title, creators, profile, status chip, and updated date. Actions: Edit (routes to form with `?record=` param), View JSON-LD (opens raw endpoint), Delete (with confirmation dialog).

**Backend changes:**
- `accounts/authentication.py` — Changed `User.objects.get()` to `get_or_create()` so users from dspback JWT tokens are auto-created in the catalog database
- `records/views.py` — Added `?mine=true` query param to `RecordViewSet.get_queryset()` filtering records to the authenticated user

**New file:** `dspfront/src/services/catalog.ts` — Helper functions `fetchMyRecords()` and `deleteRecord()` with `CatalogRecord` TypeScript interface.

**File renames (cz. → geodat. prefix):**
- `cz.ada-profile-form.vue` → `geodat.ada-profile-form.vue`
- `cz.cdif-form.vue` → `geodat.cdif-form.vue`
- `cz.ada-select-type.vue` → `geodat.ada-select-type.vue`
- `cz.submissions.vue` → `geodat.submissions.vue`

Component names, class names, and CSS selectors updated accordingly (e.g., `cz-ada-profile-form` → `geodat-ada-profile-form`). Only these 4 files were renamed; other `cz.` prefixed files remain unchanged.

**What dspback still handles:** HydroShare, EarthChem, Zenodo, and External submissions — these need repository OAuth and file uploads that the catalog backend doesn't provide. The submissions page shows both sources side by side in tabs.

## 2026-02-07: Person/Org Pick Lists and Variable Panel Progressive Disclosure

**What changed:** Added autocomplete pick lists for person and organization fields, and a progressive disclosure layout for the variableMeasured panel.

**Person/Org Pick Lists:**
- New `KnownPerson` and `KnownOrganization` models accumulate entities extracted from saved records. Unique constraint on `(name, identifier_value)` so same name with different ORCID/ROR creates separate entries.
- `extract_known_entities()` walks JSON-LD paths: `schema:creator.@list[]`, `schema:contributor[]`, `schema:subjectOf.schema:maintainer`, `schema:publisher`, `schema:provider[]`, and nested `schema:affiliation` objects. `upsert_known_entities()` does `update_or_create` for each.
- Upsert called on record create, update, import-url, and import-file.
- Search endpoints: `GET /api/catalog/persons/?q=` and `GET /api/catalog/organizations/?q=` return schema.org-shaped JSON (with `schema:name`, `schema:identifier`, `schema:affiliation` objects) for direct mapping into CzForm fields.
- UISchema injection at serve time: `ProfileSerializer.to_representation()` calls `inject_vocabulary()` which walks the UISchema tree and adds CzForm `vocabulary` options on creator, contributor, maintainer, provider, and publisher controls.
- `backfill_entities` management command scans all existing records to populate the tables.

**Variable Panel Progressive Disclosure:**
- UISchema injection also replaces the `schema:variableMeasured` control's `options.detail` with a three-tier layout:
  - Collapsed: shows `schema:name` via `elementLabelProp`
  - Expanded: `schema:name`, `schema:propertyID`, `schema:description` (multiline) + "Advanced" group
  - Advanced group (collapsed by default): `schema:measurementTechnique`, `schema:unitText`+`schema:unitCode` (horizontal), `schema:minValue`+`schema:maxValue` (horizontal)
- Advanced group has `options.collapsed: true` and `options.expandWhenPopulated: true` (latter requires CzForm GroupRenderer support).

**New files:**
- `records/uischema_injection.py` — UISchema tree walker for vocabulary and variable panel injection
- `records/management/commands/backfill_entities.py` — Backfill command
- `records/migrations/0002_knownorganization_knownperson.py` — Migration
- `records/tests.py` — 51 tests (entity extraction, upsert, search API, vocabulary injection, variable panel layout)
- `catalog/test_settings.py` — SQLite settings for running tests without PostgreSQL

**API endpoints added:** `GET /api/catalog/persons/?q=`, `GET /api/catalog/organizations/?q=` (public, no auth)

**Known limitations:**
- CzForm vocabulary `value` mapping has only been tested with flat strings (Zenodo grants). Nested objects (identifier, affiliation) may need flattening if CzForm doesn't support object values.
- HydroShare/Zenodo forms use dspback (FastAPI), not the catalog API, so their entities aren't captured yet. Deferred to follow-up.

**Deploy:** `python manage.py migrate`, then `python manage.py backfill_entities`.

## 2026-02-08: Variable Advanced Toggle, Distribution UX, and MIME Type Improvements

**What changed:** Five UX improvements to the ADA form, all implemented via serve-time injection (no schema file edits needed).

**Variable Advanced Toggle:**
- Replaced the `collapsed`/`expandWhenPopulated` approach (which CzForm's GroupRenderer didn't support) with a `_showAdvanced` boolean checkbox + JSON Forms `rule` with `effect: "SHOW"`.
- The rule uses an OR compound condition: the Advanced group shows when the toggle is checked OR any advanced field has data (`measurementTechnique`, `unitText`, `unitCode`, `minValue`, `maxValue`). Field conditions use `failWhenUndefined: true` so undefined fields don't trigger the rule.
- `_showAdvanced` boolean is injected into the variableMeasured items schema at serve time and stripped by the serializer before storage.

**Distribution Type Selector + WebAPI Support:**
- Distribution detail now has a `_distributionType` enum selector ("Data Download" / "Web API") injected at serve time.
- Data Download fields (contentUrl, encodingFormat) and WebAPI fields (serviceType, documentation URL) are conditionally shown via SHOW rules keyed to `_distributionType`.
- Archive Contents (`schema:hasPart`) uses an AND rule: only visible when type is "Data Download" AND `encodingFormat` contains "application/zip".
- The serializer strips `_distributionType` and sets `@type` to `["schema:WebAPI"]` or `["schema:DataDownload"]` based on the selector value.
- Frontend `populateOnLoad()` reverse-maps `@type` → `_distributionType` on form load so existing records show the correct selector state.

**MIME Type Selectable List:**
- 26-entry `MIME_TYPE_OPTIONS` constant with `{"const": media_type, "title": ".ext - Type Name (media_type)"}` format. Sorted alphabetically by media type. Derived from the `adaFileExtensions` lookup table.
- `MIME_TYPE_ENUM` flat list of media type strings derived from `MIME_TYPE_OPTIONS`. CzForm doesn't render `oneOf` on primitive strings as a searchable dropdown, so `enum` is used instead.
- Injected as `enum` on `schema:encodingFormat.items` for both distribution items and hasPart items (files within archives).

**Key finding:** JSON Forms rules work on Groups, not just Controls. `@jsonforms/core` supports `rule.effect: "SHOW"/"HIDE"` on any UISchema element (Controls, Groups, Layouts), with `OR`/`AND` compound conditions and `SchemaBasedCondition` with `failWhenUndefined`.

**CzForm limitation:** CzForm does NOT support `oneOf` on primitive string items — results in "No applicable renderer found". Use `enum` instead for selectable dropdowns on string fields.

**Files changed:**
- `dspback-django/records/uischema_injection.py` — MIME_TYPE_OPTIONS, MIME_TYPE_ENUM, DISTRIBUTION_DETAIL, HAS_PART_DETAIL, DISTRIBUTION_SCOPES, updated VARIABLE_DETAIL with rule, expanded inject_schema_defaults and inject_uischema
- `dspback-django/records/serializers.py` — Cleanup logic in validate() for _showAdvanced and _distributionType
- `dspfront/src/services/catalog.ts` — _distributionType initialization in populateOnLoad()
- `dspback-django/records/tests.py` — 30+ new tests (99 total, up from 51)

## 2026-02-08: CDIF Funding UISchema and Schema Fixes

**What changed:** Fixed three issues in the CDIF Discovery profile's funding section.

**Bug 1 — "No applicable renderer found" in funding detail:**
The hand-crafted CDIF uischema (`OCGbuildingBlockTest/_sources/jsonforms/profiles/CDIFDiscovery/uischema.json`) had wrong scopes in the funding detail — missing `schema:` prefixes. CzForm couldn't find renderers because the scopes didn't match any schema properties.

Fixes applied:
- `#/properties/name` → `#/properties/schema:name`
- `#/properties/identifier` → `#/properties/schema:identifier`
- `#/properties/funder/properties/schema:name` → `#/properties/schema:funder/properties/schema:name`
- `elementLabelProp: "name"` → `"schema:name"`

**Bug 2 — Grant identifier missing detail layout:**
`schema:identifier` in funding items is a `PropertyValue` object (with `schema:propertyID`, `schema:value`, `schema:url`), not a simple string. Without a detail layout, CzForm rendered it as an opaque object. Added a proper detail layout with ID Type, ID Value, and ID URL controls.

**Bug 3 — `schema:description` not in funding schema:**
Metadata files may include `schema:description` on funding items (e.g., grant acknowledgement text). This property was missing from the funder building block schema, so it couldn't be displayed or round-tripped. Added `schema:description: {type: string}` to the funder schema and a "Description" control to the funding detail in the uischema.

**Validation note:** `schema:funder` is correctly required in funding items (via `allOf`). Metadata files with funding items that lack `schema:funder` will trigger a validation warning — this is expected and correct.

**Files changed:**
- `OCGbuildingBlockTest/_sources/schemaorgProperties/funder/schema.yaml` — Added `schema:description` property
- `OCGbuildingBlockTest/_sources/jsonforms/profiles/CDIFDiscovery/uischema.json` — Fixed funding scopes, added identifier detail, added description control
- `OCGbuildingBlockTest/build/jsonforms/profiles/CDIFDiscovery/schema.json` — Added `schema:description` to funding items
- `OCGbuildingBlockTest/build/jsonforms/profiles/CDIFDiscovery/uischema.json` — Same fixes as source

## 2026-02-08: Merge hasPartFile into files Building Block

**What changed:** Consolidated `hasPartFile/` and `files/` into a single generic `files` building block. The `@type` constraint (`contains: const: "schema:DataDownload"`) was removed from `files/schema.yaml`, making it a reusable base for both top-level distribution files and archive member files. Type constraints are now applied at the composition level in profile schemas.

**Why:** The two building blocks described essentially the same file-level metadata — the only difference was the `@type` constraint (DataDownload required in `files`, DataDownload forbidden in `hasPartFile`). Consolidating eliminates duplication and makes `files/schema.yaml` a single source of truth for file properties.

**New distribution structure in `adaProduct/schema.yaml`:**
- `schema:distribution.items` uses `oneOf` with two `allOf` branches:
  - **Single file:** `$ref: files/schema.yaml` + overlay requiring `@type contains "schema:DataDownload"`
  - **Archive with parts:** `$ref: files/schema.yaml` + overlay requiring `@type contains "schema:DataDownload"` + `schema:provider`, `schema:additionalType`, and `schema:hasPart`
- `schema:hasPart.items` uses `allOf`: `$ref: files/schema.yaml` + overlay with `@type not contains "schema:DataDownload"`

**Deleted:** `_sources/adaProperties/hasPartFile/` directory (schema.yaml, bblock.json, context.jsonld, description.md).

**Files changed:**
- `OCGbuildingBlockTest/_sources/adaProperties/files/schema.yaml` — Removed `contains`/`minItems` constraint on `@type`, updated description
- `OCGbuildingBlockTest/_sources/profiles/adaProduct/schema.yaml` — Rewrote `schema:distribution` section with `oneOf`+`allOf` composition pattern
- `OCGbuildingBlockTest/_sources/adaProperties/hasPartFile/` — Deleted entirely
- `OCGbuildingBlockTest/agents.md` — Removed `hasPartFile` entry, updated `files` description
- `OCGbuildingBlockTest/_sources/profiles/*/resolvedSchema.json` — Regenerated for all 6 profiles
- `README.md` — Updated building block tree to remove `hasPartFile`
