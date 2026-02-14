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

## 2026-02-09: Resolved (JSON) Button in bblocks-viewer

**What changed:** Added a "Resolved (JSON)" button to the bblocks-viewer's JSON Schema tab, allowing users to view the fully resolved schema (all `$ref` inlined, `allOf` flattened, no `$defs`) directly in the viewer.

**Three-part implementation:**

1. **`augment_register.py`** — New script that injects `resolvedSchema` URLs into `build/register.json` for profile building blocks. Scans bblock identifiers for `.profiles.{name}` patterns and maps to `_sources/profiles/{name}/resolvedSchema.json` on GitHub Pages.

2. **bblocks-viewer fork** (`/tmp/bblocks-viewer/`) — Two files modified:
   - `src/components/bblock/JsonSchemaViewer.vue` — Added 4th button "Resolved (JSON)" (conditionally shown when `bblock.resolvedSchema` exists), with lazy fetch via `fetchDocumentByUrl()`, loading spinner, error alert, and URL display. The button has a tooltip: "Fully resolved schema with all $ref inlined and allOf flattened — no external references".
   - `src/services/bblock.service.js` — Added `'resolvedSchema'` to `COPY_PROPERTIES` so the URL persists through `fetchBBlock()` (which loads from `json-full` and only copies whitelisted properties from the register entry).

3. **Workflow integration** — `generate-jsonforms.yml` now runs `augment_register.py` after `convert_for_jsonforms.py` and stages `build/register.json` in the commit step.

**Also changed:** `cors_server.py` now accepts an optional directory argument (`python tools/cors_server.py 8090 /path/to/dir`) for serving from a specific directory.

**Key finding:** `fetchBBlock()` in `bblock.service.js` loads full bblock data from a separate `json-full` URL and only copies `COPY_PROPERTIES` from the register entry. Any custom properties added to `register.json` must be added to this whitelist or they'll be silently dropped.

**deploy-viewer workflow:** The OGC postprocessor deploys GitHub Pages with the upstream bblocks-viewer (which lacks the Resolved JSON button) and a `register.json` without `resolvedSchema` URLs. A new `deploy-viewer.yml` workflow re-deploys Pages after the postprocessor completes, with three additions:
1. Runs `augment_register.py` to inject `resolvedSchema` URLs into `register.json`
2. Generates `config.js` pointing to the local register (the postprocessor generates this in-memory during its deploy but doesn't commit it)
3. Generates `index.html` loading assets from the `smrgeoinfo/bblocks-viewer` fork instead of upstream `ogcincubator/bblocks-viewer`

The workflow chain is: push → "Validate and process Building Blocks" (OGC postprocessor) → triggers both "Generate JSON Forms schemas" and "Deploy custom bblocks-viewer".

**Files changed:**
- `OCGbuildingBlockTest/tools/augment_register.py` — New script
- `OCGbuildingBlockTest/.github/workflows/generate-jsonforms.yml` — Added augment step + register.json staging
- `OCGbuildingBlockTest/.github/workflows/deploy-viewer.yml` — New workflow: re-deploys Pages with custom viewer + augmented register
- `OCGbuildingBlockTest/tools/cors_server.py` — Added directory argument
- `OCGbuildingBlockTest/build/register.json` — 6 profile bblocks now have `resolvedSchema` URLs
- `smrgeoinfo/bblocks-viewer` (GitHub fork) — Fork of `ogcincubator/bblocks-viewer` with Resolved (JSON) button; deployed to GitHub Pages at `smrgeoinfo.github.io/bblocks-viewer/`
- `/tmp/bblocks-viewer/src/components/bblock/JsonSchemaViewer.vue` — Added Resolved (JSON) button
- `/tmp/bblocks-viewer/src/services/bblock.service.js` — Added `resolvedSchema` to COPY_PROPERTIES

## 2026-02-09: resolvedSchema.json as Source of Truth for JSON Forms

**What changed:** Refactored the JSON Forms schema pipeline so that `resolvedSchema.json` (produced by `resolve_schema.py`) is the single source of truth. The old pipeline read from OGC postprocessor output (`build/annotated/`); the new pipeline reads from the resolved schemas directly.

**New pipeline:**
```
schema.yaml → resolve_schema.py → resolvedSchema.json → convert_for_jsonforms.py → schema.json
```

**Three issues fixed:**

1. **`deep_merge` conflict (resolve_schema.py):** When `flatten_allof` merges `cdifMandatory` (which has `anyOf` on distribution) and `adaProduct` (which has `oneOf`), both keywords ended up in the same object — an invalid schema. Fixed with an `_is_complete_schema` heuristic: when merging `properties` dicts, if the overlay property has `type`, `oneOf`, `anyOf`, `allOf`, or `$ref`, it **replaces** the base entirely. Partial constraint patches (no composition keywords) are deep-merged to preserve the base structure. This correctly handles both adaProduct replacing cdifMandatory's distribution AND technique profiles deep-merging constraints into adaProduct.

2. **WebAPI distribution branch (adaProduct/schema.yaml):** Distribution now has 3 `oneOf` branches:
   - Branch 1: Single DataDownload file
   - Branch 2: DataDownload archive with `schema:hasPart`
   - Branch 3: WebAPI with `schema:potentialAction` → Action → `schema:result` (which reuses single-file/archive oneOf)

3. **Technique-specific fileDetail constraints:** Each technique profile now constrains `fileDetail` to only the file types valid for that technique (via `anyOf` subsets), rather than inheriting all 8 file types from the base profile:
   - adaEMPA: imageMap, image, tabularData, collection, supDocImage, document
   - adaICPMS: tabularData, collection, document
   - adaVNMIR: tabularData, imageMap, dataCube, supDocImage, document
   - adaXRD: tabularData, image, document

**Cross-def fragment resolution fix (resolve_schema.py):** Added `_inline_unresolved_defs` function. Pass 1 resolves each `$def` with an empty defs dict, so cross-def fragment refs (e.g., `#/$defs/VariableMeasured` referenced from another def) become `$comment` placeholders. Pass 2 walks the schema and replaces those placeholders with the actual resolved content.

**convert_for_jsonforms.py refactor:**
- Changed input source from `build/annotated/bbr/metadata/profiles/{name}/schema.json` to `_sources/profiles/{name}/resolvedSchema.json`
- Removed dead code: `resolve_external_refs`, `_resolve_json_pointer`, `merge_allof_entries`, `merge_technique_profile`, `resolve_all_refs`, `convert_defs_to_definitions`, `deep_merge`, `GHPAGES_PREFIX`, `LOCAL_ANNOTATED`, `BASE_PROFILES`, `ANNOTATED_DIR`
- New `simplify_distribution_items()` preserves `oneOf` structure and merges technique constraints into applicable branches
- New `simplify_file_detail_anyof()` preserves `anyOf` of file types
- Pipeline order fix: `simplify_contains_to_enum` must run before `simplify_const_to_default` (otherwise WebAPI `@type` `contains.const` gets converted to `contains.default` and the enum simplifier can't find it)

**Files changed:**
- `OCGbuildingBlockTest/tools/resolve_schema.py` — `deep_merge` → `_deep_merge_inner` with `_is_complete_schema` heuristic; added `_inline_unresolved_defs` for pass-2 cross-def resolution
- `OCGbuildingBlockTest/tools/convert_for_jsonforms.py` — Complete refactor to read from resolvedSchema.json
- `OCGbuildingBlockTest/_sources/profiles/adaProduct/schema.yaml` — Added WebAPI as 3rd distribution oneOf branch
- `OCGbuildingBlockTest/_sources/profiles/adaEMPA/schema.yaml` — Added fileDetail anyOf constraint (6 file types)
- `OCGbuildingBlockTest/_sources/profiles/adaICPMS/schema.yaml` — Added fileDetail anyOf constraint (3 file types)
- `OCGbuildingBlockTest/_sources/profiles/adaVNMIR/schema.yaml` — Added fileDetail anyOf constraint (5 file types)
- `OCGbuildingBlockTest/_sources/profiles/adaXRD/schema.yaml` — Added fileDetail anyOf constraint (3 file types)
- `OCGbuildingBlockTest/_sources/profiles/*/resolvedSchema.json` — Regenerated for all 6 profiles
- `OCGbuildingBlockTest/build/jsonforms/profiles/*/schema.json` — Regenerated for all 6 profiles

## 2026-02-09: MIME-Type-Driven Distribution Form with Per-Profile Filtering

**What changed:** Three-phase overhaul of the distribution form to fix the archive visibility bug, add MIME-type-driven field groups, and filter MIME types per technique profile.

### Phase 1: Fix Archive Bug + encodingFormat Simplification

**Root cause:** `schema:encodingFormat` was an array, and the archive contents SHOW rule used `{"contains": {"const": "application/zip"}}`. JSON Forms evaluates `contains` via JSON Schema validation, and empty/undefined arrays match `contains` vacuously — so Archive Contents was always visible.

**Fix:** Convert `schema:encodingFormat` from array to single string at serve time. This enables simple `{"const": "application/zip"}` rule conditions.

- **`uischema_injection.py`** — Changed encodingFormat injection from `{type: array, items: {enum: ...}}` to `{type: string, enum: MIME_TYPE_ENUM}`. Fixed archive rule from `{"contains": {"const": "application/zip"}}` to `{"const": "application/zip"}`.
- **`serializers.py`** — Wraps string back to array on save (`"text/csv"` → `["text/csv"]`); empty strings are removed entirely.
- **`catalog.ts`** — `populateOnLoad()` unwraps array to string on form load (`["text/csv"]` → `"text/csv"`).

### Phase 2: fileDetail Flattening + MIME-Driven Field Groups

**Problem:** `fileDetail` had `anyOf` of 9 file type schemas — JSON Forms can't render anyOf discriminators. Technique-specific fields (image channels, CSV delimiters, etc.) were invisible.

**Fix:** Flatten all anyOf branches into single merged object in `convert_for_jsonforms.py`, then use UISchema SHOW rules keyed to MIME type categories to display only the relevant field group.

- **`convert_for_jsonforms.py`** — Rewrote `simplify_file_detail_anyof()` to merge all 9 branches (skip `@type`, merge componentType enums via recursive `_collect_component_type_enums()`). Result: 40 merged properties, 110 unique componentType values.
- **`uischema_injection.py`** — Added MIME category constants and 4 file-type Groups to `DISTRIBUTION_DETAIL`:

  | Group | MIME trigger | Key fileDetail fields |
  |-------|-------------|----------------------|
  | Image Details | IMAGE_MIMES (jpeg, png, tiff, bmp, svg) | componentType, acquisitionTime, channels, pixelSize, illuminationType |
  | Tabular Data Details | TABULAR_MIMES (csv, tsv) | componentType, csvw:delimiter/quoteChar/header, countRows/Columns, physicalMapping |
  | Data Cube Details | DATACUBE_MIMES (hdf5, netcdf) | componentType, physicalMapping, dataComponentResource |
  | Document Details | DOCUMENT_MIMES (pdf, txt, html, md, rtf, docx) | componentType, schema:version, schema:isBasedOn |

  Each group uses an AND rule: `_distributionType == "Data Download"` AND `encodingFormat in [MIME list]`. The `enum` condition pattern works because JSON Forms evaluates rules via JSON Schema validation.

- **`serializers.py`** — Added fileDetail `@type` inference from componentType on save. Lookup tables `_FILE_TYPE_PREFIXES` (exact match) and `_FILE_TYPE_PREFIX_RULES` (prefix fallback) map componentType strings to `[ada:type, schema:Type]` pairs. E.g., `ada:EMPAImage` → `["ada:imageMap", "schema:ImageObject"]`.

### Phase 3: Per-Profile MIME Type Filtering

> **Superseded** by 2026-02-13 entry: `PROFILE_FILE_TYPES` replaced with `PROFILE_COMPONENT_TYPES` which auto-derives both MIME and componentType filtering for all 35 technique profiles.

**Original fix:** Added profile→file-types→MIME-types mapping via `PROFILE_FILE_TYPES` dict for the original 4 profiles. This has been replaced by `PROFILE_COMPONENT_TYPES` which covers all 35 profiles and also drives componentType dropdown filtering.

**Files changed:**
- `dspback-django/records/uischema_injection.py` — encodingFormat→string, archive rule fix, MIME categories, fileDetail Groups, per-profile filtering
- `dspback-django/records/serializers.py` — encodingFormat wrap/unwrap, fileDetail @type inference, profile_name passthrough
- `dspfront/src/services/catalog.ts` — encodingFormat array→string unwrap in populateOnLoad()
- `OCGbuildingBlockTest/tools/convert_for_jsonforms.py` — Flatten fileDetail anyOf into merged object
- `OCGbuildingBlockTest/build/jsonforms/profiles/*/schema.json` — Regenerated for all 6 profiles
- `dspback-django/records/tests.py` — 123 tests (up from 99)

## 2026-02-09: MIME-Driven Groups in hasPart (Archive Contents)

**What changed:** Extended the MIME-type-driven field groups from distribution items to hasPart items (files within archives). Archive member files now show the same technique-specific field groups (Image Details, Tabular Data Details, Data Cube Details, Document Details) based on the selected MIME type.

**Implementation:**
- Added `_hp_mime_rule(mime_list)` helper — simpler than distribution-level rules because hasPart items don't need the `_distributionType == "Data Download"` AND condition (they're always data files).
- Expanded `HAS_PART_DETAIL` from 3 elements (name, description, MIME type) to 8 elements: name, description, MIME type, nested archive contents (for archives-in-archives), Image Details group, Tabular Data Details group, Data Cube Details group, Document Details group.
- hasPart `schema:encodingFormat` also converted from array to string (same serve-time injection pattern as distribution).
- Serializer wraps hasPart encodingFormat strings back to arrays on save (same pattern).
- Frontend `populateOnLoad()` unwraps hasPart encodingFormat arrays to strings on load.

**Files changed:**
- `dspback-django/records/uischema_injection.py` — `_hp_mime_rule()`, expanded `HAS_PART_DETAIL` with 4 file-type groups + nested archive contents
- `dspback-django/records/serializers.py` — hasPart encodingFormat string→array wrap on save
- `dspfront/src/services/catalog.ts` — hasPart encodingFormat array→string unwrap in `populateOnLoad()`
- `dspback-django/records/tests.py` — 130 tests (up from 123): `test_has_part_nested_archive`, `test_has_part_image_group`, `test_has_part_tabular_group`, `test_has_part_datacube_group`, `test_has_part_document_group`, `test_has_part_encoding_format_wrapped`, `test_has_part_empty_encoding_format_removed`

## 2026-02-09: Flatten fileDetail and Full v3 Schema Alignment (adaMetadataViews)

**What changed:** Restructured the JSON-LD template and views.py so that hasPart items in `schema:distribution` validate against `adaMetadata-SchemaOrgSchema-v3.json`. Result: 77/77 test files valid, 0 errors (down from 77 errors).

**Root cause of prior failures:** Every hasPart item had hardcoded `@type: ["schema:MediaObject"]` with type-specific properties buried inside a `fileDetail` sub-object. The v3 schema's `files_type` requires each hasPart item to match one of the defined type schemas (image, tabular, dataCube, etc.) with `@type`, `componentType`, and type-specific properties at the **top level**.

**Key changes:**

1. **Template restructure (`templates/adaJSONLD.json`):**
   - `@type` now emits actual type from `keyset.type_` instead of hardcoded `["schema:MediaObject"]`
   - `componentType` emitted at top level (skipped for Metadata files)
   - `cdi:hasPhysicalMapping` replaces old `cdi:isStructuredBy` / `DataStructureComponent` nesting
   - `tabularProps` (e.g., `cdi:isDelimited: true`) emitted as top-level properties
   - `thedetail` properties flattened to top level
   - `fileDetail` wrapper completely removed

2. **`@type` fixes (`viewapp/views.py`):**
   - tabularData: `"cdi:PhysicalDataSet"` → `"cdi:TabularTextDataSet"`
   - dataCube: `"cdi:DimensionalDataStructure"` → `"cdi:StructuredDataSet"`
   - metadata: `["ada:metadata", "schema:Dataset"]` → `["Metadata"]`
   - fallback (no subject): `["schema:MediaObject"]` → `["ada:otherFileType"]`, componentType `"unknown"` → `"ada:other"`
   - empty fallback: `["noComponentFiles"]` → `["ada:otherFileType"]`, componentType `"missing"` → `"ada:other"`

3. **Added `tabularProps`** (`viewapp/views.py`): `fileitem['tabularProps'] = {'cdi:isDelimited': True}` in the tabular branch, satisfying `tabularData_type`'s `oneOf` requiring either `cdi:isDelimited: true` or `cdi:isFixedWidth: true`.

4. **`schema:encodingFormat` omitted for `other_type` items** — critical schema conflict fix (see below).

**schema:encodingFormat conflict in other_type (important for future schema work):**

The v3 schema's `other_type` defines `schema:encodingFormat` as an `enum` of specific human-readable format descriptions (`"Spectral Data Exchange File (.emsa)"`, `"3D model file (.obj)"`, etc.), while the base `files_type` defines it as `{"type": "array", "items": {"type": "string"}}` (MIME type arrays). Since `files_type` uses `allOf` (base AND anyOf type-specific), both constraints apply simultaneously to the same value. No value can satisfy both — an array `["text/csv"]` passes the base but fails the enum; a string `"3D model file (.obj)"` passes the enum but fails the array type.

**Fix:** The template conditionally skips `schema:encodingFormat` for `other_type` items:
```django
{% if "ada:otherFileType" not in fileitem.keyset.type_ %}
,"schema:encodingFormat": ["{{fileitem.keyset.encodingFormat}}"]
{% endif %}
```
Neither the base nor `other_type` schemas require the property, so omitting it satisfies both vacuously.

**Data finding:** None of the 77 test DOIs have `subject_schema_id=6` records, so ALL non-metadata files fall through to the `other_type` fallback path. The type-specific code paths (tabular, image, dataCube, etc.) are unreachable with the current test data — they will only activate when the ADA database has file-level subject metadata populated.

**Files changed:**
- `adaMetadataViews/viewapp/views.py` — `@type` fixes, `tabularProps`, `thedetail = {}` for metadata/fallback paths
- `adaMetadataViews/templates/adaJSONLD.json` — Complete hasPart restructure, conditional encodingFormat
- `adaMetadataViews/Standalone/regen_test_json.py` — New utility script for regenerating test JSON

## 2026-02-10: Demo Deployment Stack

**What changed:** Added a self-contained Docker Compose configuration (`docker-compose-demo.yml`) that builds and runs the full 5-service stack from source, suitable for VPS demo hosting or local testing.

**Architecture:**
```
Internet → :80/:443 → Nginx (nginx-demo.conf, self-signed SSL)
                        ├── /              → dspfront (Vue SPA on :5001)
                        ├── /api/catalog/* → catalog (Django on :5003)
                        ├── /api/*         → dspback (FastAPI on :5002)
                        └── /docs, /redoc  → dspback
                      PostgreSQL (:5432, named volume, two databases: dsp + catalog)
```

**New files:**
- `docker-compose-demo.yml` — All 5 services, HTTP+HTTPS, postgres healthcheck, auto-migrate + load_profiles on catalog startup
- `nginx/nginx-demo.conf` — Reverse proxy with HTTP (port 80) and HTTPS (port 443, self-signed certs from `nginx/config/`)
- `.env.demo` — Template env file (copy to `.env` and customize `DEMO_HOST`, `OUTSIDE_HOST`)
- `.gitattributes` — Enforces LF line endings on `*.sh` files (CRLF breaks Docker container exec)

**Key differences from `docker-compose-dev.yml`:**

| | Dev | Demo |
|---|---|---|
| Frontend | Vite dev server on host (:8080), nginx proxies to `host.docker.internal` | Production SPA built in-container, runtime env substitution via entrypoint.sh |
| Backend | `Dockerfile-dev` + `dev-entrypoint.sh`, bind-mounts source | Production `Dockerfile`, no bind-mount |
| Catalog | Bind-mounts source, gunicorn `--reload` | No source mount, auto-migrates + loads profiles, gunicorn without `--reload` |
| SSL | Self-signed certs (HTTPS :443 only) | Both HTTP :80 and HTTPS :443 |
| Postgres | Bind-mount `./dspback/postgres-data` | Named Docker volume `pgdata` |

**Submodule fixes (dspfront):**
- `.npmrc` — Added `legacy-peer-deps=true` (npm peer dependency conflict with `vite-ssg` wanting `vue-router@^4` vs project's `vue-router@^5`)
- `Dockerfile` — `COPY package*.json .npmrc ./` before `npm install` so `.npmrc` settings take effect
- `docker/entrypoint.sh` — Fixed CRLF→LF line endings (broke `exec` in Linux containers)
- `.gitattributes` — Enforces LF on shell scripts

**Submodule fixes (dspback):**
- `config/__init__.py` — Added `outside_proto: str = "https"` setting
- `dependencies.py` — `url_for()` uses `OUTSIDE_PROTO` instead of hardcoded `https://`, enabling HTTP deployments

**ORCID OAuth setup for demo:**
- ORCID sandbox doesn't accept `localhost` or `127.0.0.1` as redirect URI domains
- Workaround: use `lvh.me` (a public domain that resolves to 127.0.0.1) — add `127.0.0.1 lvh.me` to hosts file if DNS doesn't resolve it
- Register `https://lvh.me/api/auth` as redirect URI in ORCID developer tools
- Set `OUTSIDE_HOST=lvh.me` and `DEMO_HOST=lvh.me` in `.env`
- `VITE_APP_API_URL` must include `/api` suffix and match the protocol/host the user accesses (compose uses `${OUTSIDE_PROTO}://${DEMO_HOST}/api`)

**Issues encountered and fixed:**
1. CRLF line endings in `entrypoint.sh` and `init-catalog-db.sh` → "no such file or directory" in containers
2. npm peer dependency conflict → added `legacy-peer-deps=true` to `.npmrc` and copied it before `npm install`
3. Postgres startup race → added healthcheck + `condition: service_healthy` on dependent services
4. Missing `/api` in `VITE_APP_API_URL` → login popup opened the SPA instead of the backend login endpoint
5. Hardcoded `https://` in `url_for()` → added configurable `OUTSIDE_PROTO`
6. ORCID redirect URI mismatch → use `lvh.me` domain, match protocol to `OUTSIDE_PROTO`
7. Mixed content (HTTPS page calling HTTP API) → frontend env vars derive protocol from `OUTSIDE_PROTO`

**To deploy:**
```bash
cp .env.demo .env
# Edit .env: set DEMO_HOST, OUTSIDE_HOST, ORCID credentials
docker compose -f docker-compose-demo.yml up -d --build
```

## 2026-02-10: ADA Bridge — Phase 1 Backend Integration

**What changed:** Added the `ada_bridge` Django app to `dspback-django/`, providing a backend bridge between IEDA catalog records (JSON-LD) and the ADA (Astromat Data Archive) REST API. This is Phase 1: backend-only, no frontend UI yet.

**Why:** The ADA frontend is browse/search-only — no UI for creating records or uploading bundles. IEDA has rich schema-driven forms for ADA metadata profiles. The bridge enables records authored in IEDA's forms to be pushed to ADA via its REST API, with DOI and status synced back.

**Architecture:**
```
IEDADataSubmission (dspback-django)         ADA API (Django/DRF)
┌──────────────────────────────────┐        ┌─────────────────────┐
│  records app (existing)          │        │                     │
│    └─ Record model (JSON-LD)     │        │  /api/record/       │
│                                  │        │  /api/download/     │
│  ada_bridge app (NEW)            │        │                     │
│    ├─ AdaRecordLink model        │───────>│  Api-Key auth       │
│    ├─ translator_ada.py          │  HTTP  │  CamelCaseJSON      │
│    ├─ client.py (AdaClient)      │        │                     │
│    ├─ bundle_service.py          │        └─────────────────────┘
│    ├─ views.py (push/sync API)   │
│    └─ services.py (orchestrator) │
└──────────────────────────────────┘
```

**New files (all under `dspback-django/ada_bridge/`):**
- `models.py` — `AdaRecordLink`: OneToOne to `records.Record`, stores `ada_record_id` (int), `ada_doi`, `ada_status`, `push_checksum` (SHA-256 for change detection), timestamps
- `translator_ada.py` — Translates JSON-LD (namespace-prefixed keys) to ADA API camelCase format. Maps `schema:creator` → `creators[].nameEntity`, `schema:contributor` → `contributors[]`, `schema:funding` → `funding[]`, `schema:license` → `licenses[]`, `schema:distribution` → `files[]`, `schema:about` → `subjects[]`. Includes `compute_payload_checksum()` for change detection.
- `client.py` — `AdaClient`: HTTP client wrapping ADA REST API with `Api-Key` auth. Methods: `create_record()`, `update_record()`, `get_record()`, `upload_bundle()`, `get_record_status()`. Uses DOI-based URL paths (`/api/record/{doi}`).
- `bundle_service.py` — ZIP introspection using `ada_metadata_forms` inspectors (ZipInspector, CSVInspector, ImageInspector, HDF5Inspector). Falls back gracefully when inspectors are unavailable.
- `services.py` — Orchestration: `push_record_to_ada()` (translate → checksum → skip-if-unchanged → create/update → save link), `sync_ada_status()` (pull status/DOI from ADA → update link), `upload_bundle_and_introspect()` (save to temp → introspect → optionally push to ADA).
- `views.py` — DRF function-based views: push, sync, status, bundle-introspect, bundle-upload
- `urls.py` — Routes under `/api/ada-bridge/`
- `serializers.py` — Request/response DRF serializers
- `tests.py` — 74 tests (62 unit tests on SQLite, 12 integration tests requiring PostgreSQL)

**API endpoints (all under `/api/ada-bridge/`, authenticated):**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `push/<uuid:record_id>/` | POST | Translate JSON-LD → ADA payload, create/update in ADA |
| `sync/<uuid:record_id>/` | POST | Pull status + DOI from ADA → update AdaRecordLink |
| `status/<uuid:record_id>/` | GET | Return current AdaRecordLink data |
| `bundle/introspect/` | POST | Upload ZIP, return introspection results |
| `bundle/upload/<uuid:record_id>/` | POST | Upload bundle to linked ADA record |

**ADA-side changes (separate repo `ADA/api/`):**
- `astromat_api/models/record.py` — Added `_SKIP_DATACITE` flag: when `DATACITE_PASSWORD` env var is unset, `get_doi_data()` generates dummy DOIs (`10.82622/dev-{uuid}`) instead of calling DataCite. Enables local dev without DataCite credentials.
- `astromat_api/serializers/record_serializers.py` — Fixed `ListRecordSerializer.create()`: changed hard `.pop("recordcreator_set")` to `.pop("recordcreator_set", [])` (and similar for contributors, funding, licenses, subjects, files) so records with empty/missing nested fields don't raise `KeyError`.

**Push flow (end-to-end verified):**
1. `POST /api/ada-bridge/push/{id}/` → `services.push_record_to_ada()`
2. Fetch IEDA Record → translate JSON-LD via `translator_ada.jsonld_to_ada()`
3. Compute SHA-256 checksum → skip if matches `AdaRecordLink.push_checksum`
4. No existing link → `AdaClient.create_record(payload)` → ADA creates record + mints DOI
5. Has existing link → `AdaClient.update_record(doi, payload)` → ADA updates record
6. Save `AdaRecordLink` with `ada_record_id`, `ada_doi`, `ada_status`, `push_checksum`

**Key design decision — camelCase output:** ADA uses `djangorestframework-camel-case` (`CamelCaseJSONParser`/`CamelCaseJSONRenderer`), so the translator outputs camelCase keys (`fullName`, `givenName`, `awardNumber`, etc.) which ADA's parser converts to snake_case internally.

**Key design decision — DOI-based API paths:** ADA's `RecordViewSet` uses DOI as the lookup field (not integer PK). The client uses `GET/PATCH /api/record/{doi}` for updates and status checks.

**Test suite (74 tests):**
- **Unit tests (62, run on SQLite):** translator helpers, creator/contributor/funding/license/file/subject translation, full payload translation, checksum stability, bundle introspection, payload format validation
- **Integration tests (12, require PostgreSQL):** push (create + update + skip-unchanged), sync, status — mock `AdaClient` via `unittest.mock.patch`
- Integration tests use `if connection.vendor != "postgresql": self.skipTest(...)` because Record model uses PostgreSQL-specific features (ArrayField, GinIndex)

**Configuration added:**
- `catalog/settings.py` — `ADA_API_BASE_URL`, `ADA_API_KEY` from environment; `ada_bridge` in `INSTALLED_APPS`
- `catalog/urls.py` — `include("ada_bridge.urls")` under `api/ada-bridge/`

**Deploy:** `docker exec catalog python manage.py migrate` to create `ada_bridge_adarecordlink` table. Set `ADA_API_BASE_URL` and `ADA_API_KEY` in `.env`.

## 2026-02-13: Per-Profile MIME and componentType Filtering

**Problem:** All 35 ADA technique profiles showed the same full MIME type dropdown (~26 options) and the same componentType dropdowns (full category lists). Only 4 profiles (adaEMPA, adaXRD, adaICPMS, adaVNMIR) had MIME filtering via the hardcoded `PROFILE_FILE_TYPES` dict. The per-category componentType enums were completely unfiltered.

**Fix:** Replaced `PROFILE_FILE_TYPES` with a single `PROFILE_COMPONENT_TYPES` dict mapping all 35 technique profiles to their allowed `ada:`-prefixed component types. Both MIME filtering and componentType dropdown filtering are auto-derived from this dict.

**How it works:**
- `PROFILE_COMPONENT_TYPES` — Maps each profile → list of allowed component types (e.g., `"adaDSC": ["ada:DSCHeatTabular", "ada:DSCResultsTabular"]`)
- `_derive_profile_mime_categories()` — Checks which global category lists (IMAGE, TABULAR, DATACUBE) the profile's types intersect → derives MIME categories. Document and collection always included.
- `_get_profile_mime_enum()` — Returns filtered MIME list for a profile (replaces old `PROFILE_FILE_TYPES` lookup)
- `_get_profile_category_components()` — Intersects profile's types with a global category list, appends `GENERIC_COMPONENT_TYPES` → used for per-category dropdown filtering
- `inject_schema_defaults()` — `_CT_CATEGORIES` now calls `_get_profile_category_components()` for profile-filtered enums instead of static full lists

**Also extended global category lists** with missing component types from the 31 generated profiles:
- `IMAGE_COMPONENT_TYPES` +10 types (EMPAImageMap, XRDIndexedImage, VNMIRSpectraPlot, NanoSIMSImageCollection, XCTImageCollection, AIVAImageCollection, UVFMImageCollection, VLMImageCollection, SEMEDSElementalMaps, NanoIRMapCollection)
- `TABULAR_COMPONENT_TYPES` +8 types (NanoIRPointCollection, NanoSIMSCollection, LIT2DDataCollection, LITPolarDataCollection, MCICPMSCollection, SEMEDSPointDataCollection, SIMSCollection, ARGTCollection)
- `DATACUBE_COMPONENT_TYPES` +7 types (GCGCMSCollection, LCMSMSCollection, TOFSIMSCollection, XANESCollection, QRISCalibratedCollection, QRISRawCollection, RITOFNGMSCollection)
- `DOCUMENT_COMPONENT_TYPES` +3 types (SLSShapeModel, SLSPartialScan, MCICPMSRaw)

**Files changed:**
- `dspback-django/records/uischema_injection.py` — Removed `PROFILE_FILE_TYPES`, added `PROFILE_COMPONENT_TYPES` + 3 helper functions, updated `inject_schema_defaults()` componentType injection
- `dspback-django/records/tests.py` — Added 4 test classes (20 tests): `GeneratedProfileMimeFilterTest`, `ComponentTypeDropdownFilterTest`, `InjectSchemaComponentTypeFilterTest`, `BackwardCompatProfileMimeTest`. Total: 171 tests.
- `CLAUDE.md` — Added "Per-Profile MIME and componentType Filtering" section, updated Adding a New Profile checklist
- `agents.md` — Updated profile count, key file descriptions, test count, Adding a New ADA Profile steps, added filtering subsection

## 2026-02-14: In-App User Guide Page

**What changed:** Added an in-app User Guide page at `/user-guide` that renders the existing `docs/user-guide.md` using `markdown-it`. The guide is accessible from a nav menu item and a text link on the home page.

**Implementation:**
- Installed `markdown-it` (runtime) and `@types/markdown-it` (dev) in dspfront
- Copied `docs/user-guide.md` to `dspfront/src/assets/user-guide.md` so Vite can import it as a raw string (`?raw` suffix)
- Added `*.md?raw` TypeScript module declaration to `shims.d.ts`
- Created `cz.user-guide.vue` component with:
  - `markdown-it` rendering via `v-html`
  - Custom `heading_open` renderer that generates GitHub-style slug IDs on headings (so TOC anchor links work)
  - Click handler intercepting `#hash` links to use `scrollIntoView({ behavior: 'smooth' })` (browser native hash navigation doesn't work inside Vuetify's scroll container)
  - `mounted()` hook for initial hash navigation on direct URL access
  - Scoped CSS for markdown elements (headings, tables, lists, code, links, blockquotes, hr)
- Added `/user-guide` route in `routes.ts`
- Added "User Guide" nav menu item in `App.vue` (after "Resources", with `mdi-book-open-page-variant` icon)
- Added "For complete instructions..." link on home page between action cards and FAIR section

**Anchor link fix:** Initial deployment had non-working TOC links due to two issues:
1. `slugify()` was collapsing double hyphens (`--` → `-`), causing mismatches for headings with `&` (e.g., "Account & Settings" → `account--settings`)
2. Browser hash navigation doesn't scroll inside Vuetify's `v-main` scroll container — fixed with explicit `scrollIntoView()` on click

**Files changed:**
- `dspfront/package.json` — Added `markdown-it`, `@types/markdown-it`
- `dspfront/src/assets/user-guide.md` — New (copy of `docs/user-guide.md`)
- `dspfront/src/components/user-guide/cz.user-guide.vue` — New component
- `dspfront/src/shims.d.ts` — Added `*.md?raw` module declaration
- `dspfront/src/routes.ts` — Added import + route
- `dspfront/src/App.vue` — Added nav menu item
- `dspfront/src/components/home/cz.home.vue` — Added text link

## 2026-02-14: Digital Ocean Deployment

**What changed:** Deployed the demo instance to a Digital Ocean Droplet at `104.131.83.88`. SSH key access configured for `root` from the development machine.

**Setup:**
- Generated ed25519 SSH key pair on Windows dev machine (`~/.ssh/id_ed25519`, no passphrase)
- Added public key to droplet's `~/.ssh/authorized_keys` via DO web console (the forced password reset after DO password reset doesn't work well via SSH terminal — use the DO Droplet Console instead)
- Repo cloned at `/root/IEDADataSubmission` on the droplet

**Deploy commands:**
```bash
ssh root@104.131.83.88 "cd /root/IEDADataSubmission && git pull --recurse-submodules && docker compose -f docker-compose-demo.yml up -d --build && docker exec catalog python manage.py load_profiles"
```

**Gotcha:** The `dspback` submodule on the droplet may have local Dockerfile edits (e.g., the ADA model codegen line added manually before it was committed upstream). If `git pull --recurse-submodules` fails with "Your local changes would be overwritten", stash the submodule changes first:
```bash
ssh root@104.131.83.88 "cd /root/IEDADataSubmission/dspback && git stash && cd /root/IEDADataSubmission && git submodule update --recursive"
```
