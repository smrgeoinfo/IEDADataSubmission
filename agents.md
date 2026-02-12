# Agents Guide: IEDA Data Submission Portal

This document explains what this project is, how it works, and how to navigate the codebase when making changes.

## What This Project Is

The IEDA Data Submission Portal (repo: `smrgeoinfo/IEDADataSubmission`) is a web application that lets Earth Science researchers submit, manage, and discover research data across multiple repositories from a single interface. Researchers log in once with their ORCID, fill out standardized metadata forms, and submit to repositories like HydroShare, EarthChem, Zenodo, and ADA (Astromat Data Archive).

The project is a monorepo with four main components (three as git submodules, one local):

| Component | Stack | Location | Purpose |
|---|---|---|---|
| `dspback/` | FastAPI, PostgreSQL (SQLAlchemy/asyncpg), Python | Submodule: `smrgeoinfo/dspback` (`develop`) | REST API for metadata CRUD, auth, search |
| `dspback-django/` | Django 5.1, DRF, SimpleJWT, PostgreSQL | Local directory | Profile-driven metadata catalog API |
| `dspfront/` | Vue 3, TypeScript, Vuex ORM, Vuetify | Submodule: `smrgeoinfo/dspfront` (`develop`) | SPA for forms, submissions, discovery |
| `OCGbuildingBlockTest/` | YAML schemas, JSON-LD | Submodule: `smrgeoinfo/OCGbuildingBlockTest` (`master`) | Modular schema components (OGC Building Blocks) |

`dspback` and `dspback-django` coexist: nginx routes `/api/catalog/*` to Django (port 5003) and `/api/*` to FastAPI (port 5002). They use separate databases (`catalog` and `dsp`) on the same PostgreSQL instance.

## How It Works End-to-End

```
User → ORCID Login → Select Repository → Fill Schema-Driven Form → Submit
                                                                      ↓
                                            PostgreSQL ← Backend validates & stores
                                                ↓
                                          Discovery API → Search Results

Catalog flow:
User → ORCID Login → Select Profile → Fill Catalog-Driven Form → Save
                                         ↑                          ↓
               GET /api/catalog/profiles/{name}/       POST /api/catalog/records/
                  (schema + uischema + defaults)           (validates, extracts fields)
                                                                 ↓
My Submissions → Catalog Records tab → GET /api/catalog/records/?mine=true
                                         ↓
                              Edit → ?record={id} query param → PATCH
```

### 1. Authentication (Two Levels)

**User auth:** ORCID OAuth2 → JWT token stored in PostgreSQL `users` table and cookie.

**Repository auth:** Per-repository OAuth2 (HydroShare, Zenodo, EarthChem). Tokens stored as `repository_tokens` rows linked to user. ADA and External repos skip this (no OAuth needed).

### 2. Schema-Driven Forms

Each repository has three files in `dspback/dspback/schemas/{repo}/`:

- `schema.json` — JSON Schema defining fields and validation rules
- `uischema.json` — JSON Forms UI Schema controlling layout, grouping, widgets
- `defaults.json` — Default values pre-populated in the form

The frontend fetches these from `/api/schema/{repo}/` and passes them to the JSON Forms renderer, which dynamically generates Vuetify form components. This means **changing a repository's form only requires editing JSON files**, not code.

### 3. Metadata Submission

1. Frontend POSTs form JSON to `/api/metadata/{repo}`
2. Backend validates against auto-generated Pydantic model (from `schema.json`)
3. `Record.to_submission()` extracts title, authors, URL into a `SubmissionDB` row
4. Full metadata JSON stored as JSONB in `submissions.metadata`
5. Submission linked to user via `user_id` foreign key

### 4. Discovery

The `/api/discovery/search` endpoint provides search across submissions. Discovery functionality has been moved to the separate `dsp-discovery` repository.

## Key Architecture Patterns

### Repository Abstraction

Every repository follows the same pattern. The base class `MetadataRoutes` (in `routers/metadata_class.py`) provides CRUD scaffolding. Child routers set three properties:

```python
class AdaMetadataRoutes(MetadataRoutes):
    request_model = AdaProductMetadataSchemaForCzNetDataSubmissionPortalV100
    response_model = AdaMetadataResponse
    repository_type = RepositoryType.ADA
```

All repository settings live in the `repository_config` dict in `config/__init__.py`.

### Class-Based Views

Routers use `fastapi_restful.cbv` (class-based views) with `InferringRouter`. This lets routes share state (current user, settings, access tokens) via `self`.

### Vuex ORM Models

Frontend models extend `Repository` (in `models/repository.model.ts`). Each repo model sets `static entity` and `static baseEntity = 'repository'`. The base model handles init, authorize, CRUD, and file operations. RxJS Subjects drive the OAuth authorization dialog flow.

### OGC Building Blocks

Complex schemas (like ADA's 37 `$defs`) are decomposed into modular directories under `OCGbuildingBlockTest/_sources/`. Each building block has `bblock.json`, `schema.yaml`, `context.jsonld`, and `description.md`. The top-level profile (`profiles/adaProduct/`) composes all blocks.

Instrument-specific detail types (EMPA, XRD, NanoSIMS, etc.) are each in their own BB directory under `adaProperties/detailXxx/` (e.g., `detailEMPA/`, `detailXRD/`). This allows technique profiles to `$ref` only the specific detail type(s) they need (e.g., `$ref: ../detailEMPA/schema.yaml`) instead of using fragment pointers into a monolithic file. The old `details/` BB is now an umbrella schema that references all 16 detail BBs via `anyOf`.

**Important authoring rules** (the validate-and-process GitHub Actions workflow enforces these):

- **`bblock.json`** must include all required fields: `$schema`, `name`, `abstract`, `status`, `dateTimeAddition`, `itemClass`, `register`, `version`, `dateOfLastChange`, `link`, `maturity`, `scope`, `tags`, `sources`
- **`schema.yaml` cross-references** must use relative `$ref` paths to `schema.yaml` files, **not** standalone `.json` schema files. The postprocess tool resolves `$ref` to GitHub Pages URLs — `.json` refs cause 404s.
- **`examples.yaml`** snippet `ref:` must match the actual filename in the BB directory
- **`examples.yaml`** schema prefix must be `schema: http://schema.org/` (http, not https, with trailing slash)

## How to Add a New Repository Type

This is the most common extension task. Follow these steps in order:

### Backend (`dspback/dspback/`)

1. **`pydantic_schemas.py`** — Add to `RepositoryType` enum, create `XxxRecord(BaseRecord)` with `to_submission()` method
2. **`schemas/xxx/`** — Create `schema.json`, `uischema.json`, `defaults.json`
3. **Generate model** — Run `datamodel-codegen --input-file-type jsonschema --input schemas/xxx/schema.json --output schemas/xxx/model.py`
4. **`routers/xxx.py`** — New router following `external.py` pattern (simplest for no-OAuth repos) or `hydroshare.py` (for OAuth repos)
5. **`api.py`** — Import and `app.include_router(xxx.router, prefix="/api")`
6. **`config/__init__.py`** — Add entry to `repository_config` dict
7. **`routers/submissions.py`** — Add to `record_type_by_repo_type` dict and import the record class

### Frontend (`dspfront/src/`)

1. **`components/submissions/types.ts`** — Add to `EnumRepositoryKeys` enum
2. **`components/submit/constants.ts`** — Add to `repoMetadata` with name, logo, description, feature flags
3. **`models/xxx.model.ts`** — New model extending `Repository`
4. **`models/repository.model.ts`** — Add case in `createSubmission` switch

## File Reference

### Backend Entry Points

| File | What It Does |
|---|---|
| `dspback/dspback/api.py` | FastAPI app setup, router registration, middleware, startup |
| `dspback/dspback/config/__init__.py` | Settings from `.env`, `repository_config` dict |
| `dspback/dspback/dependencies.py` | Auth utilities: JWT validation, token refresh, user lookup |
| `dspback/dspback/pydantic_schemas.py` | `RepositoryType` enum, Pydantic record models |
| `dspback/dspback/database/models.py` | SQLAlchemy ORM: `UserDB`, `SubmissionDB`, `RepositoryTokenDB` |
| `dspback/dspback/database/session.py` | Async engine, `get_session()` FastAPI dependency |
| `dspback/dspback/database/procedures.py` | DB procedures (INSERT...ON CONFLICT upserts) |

### Backend Routers

| File | Endpoints |
|---|---|
| `routers/authentication.py` | ORCID login/callback |
| `routers/metadata_class.py` | Base CRUD class (MetadataRoutes) |
| `routers/ada.py` | `/api/metadata/ada` CRUD, `/api/metadata/ada/jsonld` JSON-LD ingest |
| `routers/external.py` | `/api/metadata/external` CRUD |
| `routers/hydroshare.py` | `/api/metadata/hydroshare` CRUD + file/folder ops |
| `routers/zenodo.py` | `/api/metadata/zenodo` CRUD + file ops |
| `routers/earthchem.py` | `/api/metadata/earthchem` CRUD + file ops |
| `routers/submissions.py` | `/api/submissions` cross-repo management |
| `routers/discovery.py` | `/api/discovery/search` Atlas Search |

### Frontend Entry Points

| File | What It Does |
|---|---|
| `models/repository.model.ts` | Base Vuex ORM model: init, authorize, CRUD, file ops, `createSubmission` switch |
| `components/submissions/types.ts` | `EnumRepositoryKeys`, `IRepository`, `ISubmission` interfaces |
| `components/submit/constants.ts` | `repoMetadata`: names, logos, file limits, feature flags per repo |
| `components/metadata/geodat.ada-select-type.vue` | ADA profile selection page (`/metadata/ada`) — fetches profiles from catalog API |
| `components/metadata/geodat.ada-profile-form.vue` | Catalog-driven ADA form (`/metadata/ada/:profile`) — fetches schema from catalog API, flattens distribution schema, unwraps encodingFormat arrays |
| `components/metadata/geodat.cdif-form.vue` | Catalog-driven CDIF form (`/metadata/cdif`) — fetches schema from catalog API |
| `components/metadata/UpdateMetadata.vue` | Update Existing Metadata page — load JSON-LD by DOI, file, or URL; create draft record |
| `components/bundle/BundleWizard.vue` | ADA Bundle Wizard — 5-step wizard for ZIP bundle upload, introspection, metadata, and push |
| `components/bundle/MetadataFormStep.vue` | Bundle wizard metadata form — pre-populates from product YAML, files, inspections |
| `components/submit/cz.submit.vue` | Submit Data landing page — repository cards (ADA first) |
| `components/submissions/geodat.submissions.vue` | My Submissions page with Repository Submissions + Catalog Records tabs |
| `services/catalog.ts` | Catalog API helpers (`fetchMyRecords`, `deleteRecord`, `populateOnLoad` with _distributionType init from @type, `populateOnSave`, `populateMaintainer`, `fetchUserInfo`) |
| `routes.ts` | Vue Router route definitions |

### Schema Files

Each repo has a directory under `dspback/dspback/schemas/`:

```
schemas/ada/
├── schema.json      # JSON Schema (source of truth for validation + forms)
├── uischema.json    # JSON Forms layout (groups, ordering, widgets)
├── defaults.json    # Pre-populated values
├── model.py         # Auto-generated Pydantic model (do not hand-edit)
└── translator.py    # JSON-LD → flat format translation (ADA only)
```

`model.py` is generated by `datamodel-codegen`. Re-run it whenever `schema.json` changes:

```bash
datamodel-codegen --input-file-type jsonschema --input dspback/dspback/schemas/ada/schema.json --output dspback/dspback/schemas/ada/model.py
```

## ADA JSON-LD Translation Layer

ADA has two ingest paths:

1. **`POST /api/metadata/ada`** — Standard flat JSON from the CZ Net frontend form (same pattern as all other repos)
2. **`POST /api/metadata/ada/jsonld`** — Raw JSON-LD from external ADA metadata tools (e.g. `ada_metadata_forms`)

The JSON-LD endpoint (`routers/ada.py:create_from_jsonld`) accepts namespace-prefixed JSON-LD matching the OGC Building Block schema (`profiles/adaProduct/schema.yaml`), translates it via `schemas/ada/translator.py`, validates with the Pydantic model, and stores it through the standard `submit()` flow.

### Translation Details (`schemas/ada/translator.py`)

Two public functions:
- `is_jsonld(data)` — sniff for `@context` key
- `translate_jsonld_to_cznet(jsonld)` — full translation

Key mappings:

| JSON-LD (prefixed) | CZ Net (flat) |
|---|---|
| `schema:name` | `name` |
| `schema:creator.@list[]` | `creators[]` (extracts type, orcid, affiliation) |
| `schema:contributor` (with Role unwrapping) | `contributors[]` (extracts roleName) |
| `schema:funding[].funder.schema:name` | `funding[].fundingAgency` |
| `prov:wasGeneratedBy.prov:used[]` | `instruments[]` |
| `prov:wasGeneratedBy.schema:location` | `laboratory` |
| `prov:wasGeneratedBy.schema:mainEntity[]` | `samples[]` |
| `schema:variableMeasured` + `cdi:unitOfMeasureKind` | `variableMeasured[].unitText` |
| `schema:creativeWorkStatus` | `status` |
| `schema:identifier.schema:propertyID` | `identifier.scheme` |

The translator strips all JSON-LD structural keys (`@context`, `@type`, `@id`, `@list`) and hardcodes `provider` to Astromat Data Archive. URL is derived from `@id` or the identifier DOI.

### Frontend Integration

The ADA model is registered in:
- `models/orm.ts` — Vuex ORM database registration
- `constants.ts` — `getRepositoryFromKey()` switch + `supportedRepositoryModels` dict
- `App.vue` — `_initRepositories()` calls `Ada.init()` to fetch schema/uischema from backend

The edit form is repository-agnostic: `cz-form` renders whatever JSON Schema + UI Schema the active repository provides. No ADA-specific form code is needed.

### Phase 2: Catalog-Driven ADA + CDIF Forms

ADA and CDIF metadata forms are driven by OGC Building Block schemas served through the Django catalog API. The flow:

1. User selects a profile at `/metadata/ada` (compact list with search filter, profiles fetched from `/api/catalog/profiles/`, general product at top, analytical methods alphabetically below a divider)
2. `geodat.ada-profile-form.vue` fetches schema, uischema, and defaults in a single request to `GET /api/catalog/profiles/{name}/`
3. The uischema uses `Categorization` type — the form component detects this and renders Vuetify tabs (Basic Info, Attribution, Methods & Variables, Distribution, Metadata Record). Each tab gets its own `CzForm` instance sharing the same data object.
4. On save, the record is POSTed to `POST /api/catalog/records/` with `{profile: <id>, jsonld: <data>}`
5. Catalog backend validates against profile schema, extracts title/creators/identifier, stores record
6. For editing, `?record=<uuid>` query param loads existing record data; save uses PATCH

The same flow applies to CDIF via `geodat.cdif-form.vue` at `/metadata/cdif`.

**My Submissions page** (`geodat.submissions.vue`) has two tabs: "Repository Submissions" (existing dspback submissions) and "Catalog Records" (fetches from `/api/catalog/records/?mine=true`). Catalog records show title, creators, profile, status, updated date, with Edit/View JSON-LD/Delete actions.

**Important:** CzForm's `renderers` is an internal class field (not a prop), so custom JSON Forms renderers cannot be injected. The Categorization tab handling is done at the parent component level instead.

**Schema pipeline** (two-step):
1. `resolve_schema.py` resolves modular YAML `$ref` references into a single `resolvedSchema.json` per profile (Draft 2020-12, all `$ref` inlined, `$defs` removed, `allOf` optionally flattened)
2. `convert_for_jsonforms.py` reads `resolvedSchema.json` and converts to JSON Forms-compatible Draft 7 by simplifying `anyOf` patterns, converting `const` → `default`, `contains` → `enum`, merging technique constraints, and removing `not` constraints

```
schema.yaml → resolve_schema.py → resolvedSchema.json → convert_for_jsonforms.py → schema.json
```

**Seven profiles**: `adaProduct` (base), `adaEMPA`, `adaXRD`, `adaICPMS`, `adaVNMIR` (ADA technique profiles), `CDIFDiscovery`, `CDIFxas` (CDIF XAS profile). ADA technique profiles add `enum` constraints on `schema:additionalType` and `schema:measurementTechnique`, plus `fileDetail` `anyOf` subsets. CDIF profiles compose `cdifMandatory` + `cdifOptional` with domain-specific building blocks (e.g., `xasRequired` + `xasOptional` for XAS).

**Key files**:
- `OCGbuildingBlockTest/tools/resolve_schema.py` — Schema resolver (YAML → resolvedSchema.json)
- `OCGbuildingBlockTest/tools/convert_for_jsonforms.py` — JSON Forms converter (resolvedSchema.json → schema.json)
- `OCGbuildingBlockTest/_sources/profiles/*/resolvedSchema.json` — Fully resolved Draft 2020-12 schemas
- `OCGbuildingBlockTest/_sources/jsonforms/profiles/*/uischema.json` — Hand-crafted UI layouts
- `OCGbuildingBlockTest/_sources/jsonforms/profiles/*/defaults.json` — Default values
- `OCGbuildingBlockTest/build/jsonforms/profiles/*/schema.json` — Generated Draft 7 schemas
- `OCGbuildingBlockTest/.github/workflows/generate-jsonforms.yml` — CI workflow
- `dspfront/src/components/metadata/geodat.ada-profile-form.vue` — ADA form component
- `dspfront/src/components/metadata/geodat.cdif-form.vue` — CDIF form component
- `dspfront/src/components/metadata/geodat.ada-select-type.vue` — Profile selection
- `dspfront/src/components/submissions/geodat.submissions.vue` — Submissions with catalog tab
- `dspfront/src/services/catalog.ts` — Catalog API helpers

### Adding a New ADA Profile

To add a new technique profile (e.g., `adaXRF`):

1. **OGC Building Block** — Create `OCGbuildingBlockTest/_sources/profiles/adaXRF/` with `bblock.json`, `schema.yaml`, `context.jsonld`, `description.md`. The `schema.yaml` should use `allOf` to extend `adaProduct` and add:
   - `schema:additionalType` constraint with `contains`/`enum` for valid component types
   - `schema:measurementTechnique` constraint (if needed)
   - `fileDetail` constraint with `anyOf` listing only the file types valid for this technique (e.g., `$ref: ../../adaProperties/tabularData/schema.yaml`)
   - Copy from an existing technique profile (e.g., `adaEMPA`).
2. **Resolve schema** — Run `python tools/resolve_schema.py adaXRF --flatten-allof -o _sources/profiles/adaXRF/resolvedSchema.json` from the `OCGbuildingBlockTest` directory.
3. **JSON Forms static files** — Create `OCGbuildingBlockTest/_sources/jsonforms/profiles/adaXRF/` with `uischema.json` and `defaults.json`. Copy from an existing technique profile and adjust defaults.
4. **Schema conversion** — Add `'adaXRF'` to the `TECHNIQUE_PROFILES` list in `OCGbuildingBlockTest/tools/convert_for_jsonforms.py`, then run `python tools/convert_for_jsonforms.py --all`.
5. **Load profile into catalog** — Run `docker exec catalog python manage.py load_profiles` to load the new profile from the BB build output. The profile list in the frontend is fetched dynamically from the catalog API, so no frontend code changes are needed for the selection page.
6. **Frontend form title** — Add `adaXRF: 'ADA XRF Product Metadata'` to the `profileNames` map in `dspfront/src/components/metadata/geodat.ada-profile-form.vue`.
7. **i18n strings** — Add the profile entry under `metadata.ada.profiles` in `dspfront/src/i18n/messages.ts`.

### Adding a New CDIF Profile

To add a new domain-specific CDIF profile (e.g., `CDIFxas`):

1. **Domain building blocks** — Create building blocks under `OCGbuildingBlockTest/_sources/xasProperties/` (or similar domain directory). Each BB has `bblock.json`, `schema.yaml`, `{name}Schema.json`. The YAML schema defines constraints using `allOf`/`contains` patterns. Keep a parallel JSON schema (`{name}Schema.json`) for direct use.
2. **Profile** — Create `OCGbuildingBlockTest/_sources/profiles/CDIFxas/` with `schema.yaml`. The schema uses `allOf` to compose `cdifMandatory`, `cdifOptional`, and domain-specific building blocks:
   ```yaml
   allOf:
   - $ref: ../../schemaorgProperties/cdifMandatory/cdifMandatorySchema.json
   - $ref: ../../schemaorgProperties/cdifOptional/cdifOptionalSchema.json
   - $ref: ../../xasProperties/xasOptional/xasOptionalSchema.json
   - $ref: ../../xasProperties/xasRequired/xasRequiredSchema.json
   ```
3. **Resolve schema** — Run `python tools/resolve_schema.py CDIFxas --flatten-allof -o _sources/profiles/CDIFxas/resolvedSchema.json`.
4. **JSON Forms static files** — Create `_sources/jsonforms/profiles/CDIFxas/` with `uischema.json` and `defaults.json`. The uischema defines tab layout; defaults provide `@context` with domain namespaces and pre-populated values (e.g., measurement technique for XAS).
5. **Schema conversion** — Add the profile name to `CDIF_PROFILES` in `tools/convert_for_jsonforms.py`, then run `python tools/convert_for_jsonforms.py --profile CDIFxas`.
6. **Load profile** — Run `docker exec catalog python manage.py load_profiles`.
7. **Frontend** — CDIF profiles with names starting with `CDIF` (excluding `CDIFDiscovery`) are auto-discovered by `ada-select-type.vue` and shown in the "CDIF Profiles" section. Add the profile to `profileNames` in `geodat.ada-profile-form.vue` and add i18n strings in `messages.ts`.
8. **Validate** — Create example JSON instances in the building block directories. Run `python tools/resolve_schema.py` and validate examples against the resolved schema.

### Schema Consistency Validation

Keep YAML (`schema.yaml`) and JSON (`{name}Schema.json`) schemas in sync. Use `tools/compare_schemas.py` periodically to detect drift between the two representations across all building blocks. The tool reports structural differences (missing keys, type mismatches, value differences) for each building block.

## Catalog Backend (dspback-django)

The Django catalog backend provides generic Profile and Record management. Profiles are loaded from OGC Building Block build output; records store JSON-LD natively with JSON Schema validation.

### Key Files

| File | What It Does |
|---|---|
| `dspback-django/catalog/settings.py` | Django settings (DB, auth, DRF, JWT, ORCID, CORS) |
| `dspback-django/catalog/urls.py` | Root URL config — mounts records and accounts |
| `dspback-django/accounts/models.py` | Custom User with ORCID as USERNAME_FIELD |
| `dspback-django/accounts/authentication.py` | JWT auth (Bearer header + ?access_token= query param, auto-creates users via get_or_create) |
| `dspback-django/accounts/views.py` | ORCID OAuth login/callback/logout, JWT issuance |
| `dspback-django/accounts/adapters.py` | allauth adapter populating orcid from social login UID |
| `dspback-django/records/models.py` | Profile (schema/uischema/defaults/base_profile), Record (UUID PK, JSON-LD, GIN index), KnownPerson, KnownOrganization |
| `dspback-django/records/serializers.py` | DRF serializers with validation + field extraction + entity upsert hooks; ProfileSerializer injects uischema and schema defaults at serve time; RecordSerializer.validate() strips UI-only fields (_showAdvanced, _distributionType) and sets distribution @type |
| `dspback-django/records/views.py` | ProfileViewSet (lookup by name), RecordViewSet (CRUD + jsonld/import actions, `?mine=true` owner filter), persons_search, organizations_search |
| `dspback-django/records/validators.py` | JSON Schema validation (auto-detects Draft-07 vs Draft-2020-12) |
| `dspback-django/records/services.py` | extract_indexed_fields(), extract_known_entities(), upsert_known_entities(), fetch_jsonld_from_url() |
| `dspback-django/records/uischema_injection.py` | UISchema tree walker: injects CzForm vocabulary configs on person/org controls, variable panel with advanced toggle (SHOW rule), distribution detail with type selector + WebAPI fields + archive conditional, MIME type enum on encodingFormat; schema defaults injection for _showAdvanced, _distributionType, WebAPI properties, MIME_TYPE_ENUM |
| `dspback-django/records/tests.py` | 130 tests covering entity extraction, upsert, search API, vocabulary injection, variable panel layout, advanced toggle rule, distribution detail, MIME type options, serializer data cleanup, hasPart groups |
| `dspback-django/ada_bridge/tests.py` | 74 tests: translator unit tests (62, SQLite), push/sync/status integration tests (12, PostgreSQL) |
| `dspback-django/records/management/commands/load_profiles.py` | Loads profiles from OGC BB build output, sets parent relationships |
| `dspback-django/records/management/commands/backfill_entities.py` | Populates KnownPerson/KnownOrganization from all existing records |

### API Endpoints

All under `/api/catalog/`:
- `profiles/` — CRUD for metadata profiles (public read, admin write), lookup by name
- `records/` — CRUD for JSON-LD records (public read, authenticated create, owner edit/delete, `?mine=true` for current user's records)
- `records/{id}/jsonld/` — Raw JSON-LD export with `application/ld+json` content type
- `records/import-url/`, `records/import-file/` — Import from URL or file upload
- `persons/?q=` — Search accumulated person entities by name (public, returns schema.org-shaped JSON with identifier/affiliation)
- `organizations/?q=` — Search accumulated organization entities by name (public, returns schema.org-shaped JSON with identifier)
- `admin/` — Django admin for Profile, Record, KnownPerson, KnownOrganization inspection

### Record Lifecycle

1. `POST /api/catalog/records/` with `{profile: <id>, jsonld: {...}, status: "draft"}`
2. Serializer validates JSON-LD against the profile's JSON Schema (skipped for draft records)
3. `extract_indexed_fields()` pulls title (from `schema:name`), creators (from `schema:creator.@list[].schema:name`), identifier (from `@id` or `schema:identifier`)
4. Identifier conflict handling: if identifier exists for same owner → upsert (update); if owned by another user → mint fresh UUID
5. `upsert_known_entities()` extracts persons/orgs from JSON-LD and upserts into KnownPerson/KnownOrganization tables (same on create, update, import-url, import-file)
6. Record stored with extracted fields for search/filter, full JSON-LD as source of truth
7. `GET /api/catalog/records/{id}/jsonld/` returns the raw JSON-LD for harvesting

### Person/Org Pick Lists (Autocomplete)

```
Record saved  ──→  extract persons/orgs from JSON-LD  ──→  upsert KnownPerson / KnownOrganization
Profile served  ──→  ProfileSerializer.to_representation()  ──→  inject vocabulary config into UISchema
Form loads  ──→  CzForm sees vocabulary on creator/contributor controls  ──→  autocomplete from API
User types  ──→  GET /api/catalog/persons/?q=Joe  ──→  CzForm populates name + identifier + affiliation
```

Entity extraction walks: `schema:creator.@list[]`, `schema:contributor[]`, `schema:subjectOf.schema:maintainer`, `schema:publisher`, `schema:provider[]`, and nested `schema:affiliation`. Unique constraint on `(name, identifier_value)` — same name with different ORCID/ROR creates separate entries.

UISchema injection targets: creator (`#/properties/schema:creator/properties/@list`), contributor (`#/properties/schema:contributor`), maintainer (`#/properties/schema:subjectOf/properties/schema:maintainer`), provider (`#/properties/schema:provider`), publisher name (`#/properties/schema:publisher/properties/schema:name`).

### Variable Panel Progressive Disclosure

The `schema:variableMeasured` array control's detail layout is injected at serve time with three tiers:
- **Collapsed:** shows `schema:name` via `elementLabelProp`
- **Expanded:** `schema:name`, `schema:propertyID`, `schema:description` (multiline), "Show Advanced Options" toggle
- **Advanced (rule-based):** `schema:measurementTechnique`, `schema:unitText`+`schema:unitCode`, `schema:minValue`+`schema:maxValue`

The Advanced group uses a JSON Forms SHOW rule with an OR compound condition: visible when `_showAdvanced` is true OR any advanced field has data (each field condition uses `failWhenUndefined: true`). The `_showAdvanced` boolean is injected into the schema at serve time and stripped by the serializer before storage.

### Distribution Detail with Type Selector

The `schema:distribution` array control's detail layout is injected at serve time with conditional fields:

```
Distribution Type selector (_distributionType: "Data Download" | "Web API")
├── Always visible: Name, Description
├── Data Download fields (SHOW when _distributionType == "Data Download"):
│   ├── Content URL
│   ├── MIME Type (encodingFormat with oneOf searchable dropdown)
│   └── Archive Contents (SHOW when Data Download AND encodingFormat contains "application/zip")
│       └── hasPart items: File Name, Description, MIME Type
└── Web API fields (SHOW when _distributionType == "Web API"):
    ├── Service Type
    └── Documentation URL
```

Schema injection adds `_distributionType` enum, `schema:serviceType`, and `schema:documentation` properties to distribution items. The serializer strips `_distributionType` and sets `@type` to `["schema:WebAPI"]` or `["schema:DataDownload"]`. Frontend `populateOnLoad()` reverse-maps `@type` → `_distributionType` on form load.

### MIME Type Selectable List

26 MIME types from the `adaFileExtensions` lookup table are hardcoded in `MIME_TYPE_OPTIONS` (sorted alphabetically by media type). Each entry has `{"const": media_type, "title": ".ext - Type Name (media_type)"}` format. `MIME_TYPE_ENUM` is a flat list of media type strings derived from `MIME_TYPE_OPTIONS`. CzForm does NOT support `oneOf` on primitive string items (causes "No applicable renderer found"), so `enum` is used instead. Injected on `encodingFormat.items` for both distribution and hasPart items.

### CDIF Profile Schema Notes

The CDIF Discovery profile schema is built from OGC Building Block source schemas under `OCGbuildingBlockTest/_sources/`. Key authoring pitfalls:

**UISchema scopes must match schema property names exactly.** All schema.org properties use the `schema:` prefix (e.g., `schema:name`, `schema:funder`). UISchema scopes must include this prefix — `#/properties/schema:name` not `#/properties/name`. Missing prefixes cause "No applicable renderer found" errors because CzForm can't resolve the scope to a schema property.

**Object properties need detail layouts.** When a schema property is an object (e.g., `schema:identifier` is a `PropertyValue` with `schema:propertyID`, `schema:value`, `schema:url`), the UISchema must provide an `options.detail` layout specifying which sub-properties to render. Without it, CzForm renders the object as opaque.

**Funding schema** (`_sources/schemaorgProperties/funder/schema.yaml`): Requires `schema:funder` (via `allOf`), plus one of `schema:identifier` or `schema:name`. Properties: `@type` (default: `schema:MonetaryGrant`), `schema:name`, `schema:description`, `schema:funder` (Organization with required `schema:name`), `schema:identifier` (PropertyValue with `schema:propertyID`, `schema:value`, `schema:url` where url has `format: "uri"`).

**Validation sources:** Frontend uses AJV (via `@cznethub/cznet-vue-core`), backend uses Python `jsonschema` (auto-detects Draft-07 vs Draft-2020-12 from `$schema`). Both validate against the same profile schema. Error messages like "must have required property" come from AJV; "Required fields missing" is the Vue component's wrapper around AJV errors.

### Serve-Time Injection Pattern

All form customizations (vocabulary, variable panel, distribution detail, MIME types) use the same pattern: `ProfileSerializer.to_representation()` calls `inject_uischema()` and `inject_schema_defaults()` which modify the schema/uischema deep copies before returning to the frontend. UI-only fields (`_showAdvanced`, `_distributionType`) are injected at serve time and stripped by `RecordSerializer.validate()` before storage. This means no OGC Building Block schema files need editing for form UX changes.

## ADA Bridge (ada_bridge app)

The `ada_bridge` Django app bridges IEDA catalog records to the ADA (Astromat Data Archive) REST API. It translates JSON-LD metadata into ADA's expected format, pushes records via HTTP, and syncs status/DOI back.

### Architecture

```
IEDA Catalog Record (JSON-LD)
        │
        ▼
  translator_ada.py   →  JSON-LD → ADA camelCase payload
        │
        ▼
  services.py         →  Orchestration (checksum, create/update logic)
        │
        ▼
  client.py           →  HTTP POST/PATCH to ADA REST API
        │
        ▼
  AdaRecordLink       →  Tracks IEDA↔ADA record pair, DOI, status, checksum
```

### Key Files

| File | What It Does |
|------|--------------|
| `ada_bridge/models.py` | `AdaRecordLink` — OneToOne link to `records.Record`, stores `ada_record_id`, `ada_doi`, `ada_status`, `push_checksum` |
| `ada_bridge/translator_ada.py` | Translates JSON-LD (namespace-prefixed) to ADA API camelCase. `jsonld_to_ada()`, `ada_to_jsonld_status()`, `compute_payload_checksum()` |
| `ada_bridge/client.py` | `AdaClient` — HTTP wrapper for ADA API with `Api-Key` auth. CRUD + bundle upload via DOI-based paths |
| `ada_bridge/services.py` | `push_record_to_ada()`, `sync_ada_status()`, `upload_bundle_and_introspect()` |
| `ada_bridge/bundle_service.py` | ZIP introspection using `ada_metadata_forms` inspectors (CSV, image, HDF5) |
| `ada_bridge/views.py` | DRF function-based views for push, sync, status, bundle endpoints |
| `ada_bridge/urls.py` | URL routes under `/api/ada-bridge/` |
| `ada_bridge/serializers.py` | Request/response DRF serializers |
| `ada_bridge/tests.py` | 74 tests (62 unit on SQLite, 12 integration on PostgreSQL) |

### API Endpoints

All under `/api/ada-bridge/`, all require authentication:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `push/<uuid:record_id>/` | POST | Translate + push record to ADA (create or update) |
| `sync/<uuid:record_id>/` | POST | Pull status + DOI from ADA |
| `status/<uuid:record_id>/` | GET | Get current `AdaRecordLink` data |
| `bundle/introspect/` | POST | Upload ZIP, return introspection results |
| `bundle/upload/<uuid:record_id>/` | POST | Upload bundle to linked ADA record |

### Push Flow

1. `POST /api/ada-bridge/push/{record_id}/`
2. Fetch IEDA Record → `translator_ada.jsonld_to_ada(record.jsonld, profile_name)`
3. Compute SHA-256 checksum → skip if matches `AdaRecordLink.push_checksum`
4. No existing link → `AdaClient.create_record(payload)` (POST to ADA)
5. Has existing link → `AdaClient.update_record(doi, payload)` (PATCH to ADA)
6. Save `AdaRecordLink` with `ada_record_id`, `ada_doi`, `ada_status`, checksum

### Field Mapping (translator_ada.py)

| JSON-LD Source | ADA API Target |
|---------------|----------------|
| `schema:name` | `title` |
| `schema:description` | `description` |
| `schema:creator[].schema:name` | `creators[].nameEntity.fullName` |
| `schema:creator[].schema:identifier` | `creators[].nameEntity.orcid` |
| `schema:contributor[]` | `contributors[].nameEntity` + `contributorType` |
| `schema:funding[].schema:funder` | `funding[].funder.name` |
| `schema:funding[].schema:identifier` | `funding[].awardNumber` |
| `schema:license[]` | `licenses[].name` / `url` |
| `schema:distribution[]` | `files[].name` / `extension` |
| `schema:additionalType` | `specificType` |
| `schema:datePublished` | `publicationDate` |

Creator names are split into `givenName`/`familyName` via `rsplit(" ", 1)`. `@type` determines `nameType` ("Personal" vs "Organizational"). ORCID identifiers are extracted from `schema:identifier`.

### ADA API Notes

- ADA uses `djangorestframework-camel-case` — accepts camelCase input, returns camelCase output
- Auth: `Authorization: Api-Key <key>` header (via `djangorestframework-api-key`)
- Record lookup by DOI: `GET/PATCH /api/record/{doi}`
- When `DATACITE_PASSWORD` env var is unset, ADA generates dummy DOIs (`10.82622/dev-{uuid}`) instead of calling DataCite
- ADA's `ListRecordSerializer.create()` handles missing nested fields (creators, contributors, etc.) with `.pop(..., [])` defaults

### Testing

- **Unit tests** (62, SQLite): translator helpers, all field mappings, checksum stability, bundle introspection
- **Integration tests** (12, PostgreSQL): push create/update/skip-unchanged, sync, status — mock `AdaClient` via `unittest.mock.patch`
- Integration tests skip on SQLite because `records.Record` uses PostgreSQL-specific features (ArrayField, GinIndex)

Run tests: `docker exec catalog python manage.py test ada_bridge`

### Configuration

Settings in `catalog/settings.py` (from environment):
- `ADA_API_BASE_URL` — Base URL of the ADA API (e.g., `http://ada-api:8000`)
- `ADA_API_KEY` — API key created in ADA's Django admin

## Bundle Wizard

The ADA Bundle Wizard (`/bundle-wizard`) lets users upload a ZIP bundle, review files, fill metadata, and push to ADA. It's a 5-step wizard:

1. **Upload** — Upload ZIP, backend introspects file contents (CSV columns, Excel sheets, HDF5 variables, image dimensions, PDF text)
2. **Product Info** — If no `product.yaml` found, user selects one from YAML files in bundle or enters manually
3. **File Review** — Table of all files with MIME types, sizes, inspection summaries, component types. Common filename prefix detection. Auto-assigns component types from product YAML
4. **Metadata Form** — CzForm driven by selected profile. Pre-populates from product YAML, bundle files, and file inspections (variables from CSV columns, samples from IGSN/DOI/ARK/OREX identifiers, distribution with hasPart file list)
5. **Review & Submit** — Final review and push to ADA

### Key Components

| File | Purpose |
|------|---------|
| `dspfront/src/components/bundle/BundleWizard.vue` | Wizard container, step navigation, YAML picker dialog |
| `dspfront/src/components/bundle/BundleUploadStep.vue` | ZIP upload with drag-and-drop |
| `dspfront/src/components/bundle/ProductFormStep.vue` | Manual product info entry |
| `dspfront/src/components/bundle/FileReviewStep.vue` | File table with MIME/component type editing |
| `dspfront/src/components/bundle/MetadataFormStep.vue` | Profile-driven metadata form with pre-population |
| `dspfront/src/components/bundle/BundleReviewStep.vue` | Final review and submit |
| `dspback-django/ada_bridge/inspectors.py` | File inspectors (CSV, Excel, HDF5, NetCDF, PDF, text) |

### Distribution Schema Flattening

The `schema:distribution` is canonically an array in JSON-LD, but the uischema treats it as a single object (one archive with hasPart file list). Both `MetadataFormStep.vue` and `geodat.ada-profile-form.vue` flatten at load time:
- **Schema**: Convert `distribution` from `{type: "array", items: {...}}` to the items object
- **Data**: Unwrap `distribution[0]` to object; unwrap `encodingFormat` arrays to strings
- **Save**: Wrap back to array; serializer wraps `encodingFormat` strings back to arrays

### Physical Structure Toggle

The "Describe Physical Structure" checkbox in hasPart items is only shown for tabular/spreadsheet/datacube MIME types. Uses OR+const rule conditions (not `enum`, which CzForm doesn't reliably support). The schema injection (`uischema_injection.py`) converts `encodingFormat` from array to string so rule conditions work.

### Form UX

- **Hover-to-show hints**: `showUnfocusedDescription: false` + `persistent-hint: false` in formConfig. CSS hides `.v-input__details` by default, shows on hover/focus-within. Rules target both `.metadata-form-step` and `.v-overlay__content` for portal-rendered content.
- **Compact spacing**: 2px margin between fields, 4px group margins
- **Description textareas**: `rows: 2, autoGrow: true` for compact initial height

## Update Existing Metadata

The Update Metadata page (`/metadata/update`) allows loading existing JSON-LD for editing:
- **By DOI** — Fetches from ADA bridge lookup API
- **From file** — Upload a local JSON-LD file
- **From URL** — Fetch from any URL

Creates a draft catalog record (skips validation) and navigates to the profile form. The profile form applies distribution schema flattening and encodingFormat unwrapping when loading record data.

## Deployment

Four Docker Compose configurations at the repo root:

| File | When to Use |
|---|---|
| `docker-compose-dev.yml` | Backend-only dev (backend + nginx, no frontend — you run Vite locally) |
| `docker-compose-demo.yml` | Self-contained demo on a VPS or local machine (HTTP, all 5 services) |
| `docker-compose-upstream.yml` | Full stack built from source |
| `docker-compose-artifact-registry.yml` | Full stack from pre-built images |

Nginx (`nginx/`) reverse proxies `/api/catalog/*` to the Django catalog backend (port 5003), `/api/*` to FastAPI (port 5002), and everything else to the frontend (port 5001). SSL termination happens at nginx (dev/production) or is omitted (demo). The `/api/catalog` location block must appear before `/api` in the nginx config for correct routing.

Environment variables (PostgreSQL credentials, OAuth credentials, JWT secrets) are in `.env` at the repo root. `.env.demo` is a ready-made template for demo deployments — copy it to `.env` and set `DEMO_HOST`/`OUTSIDE_HOST` to your VPS IP or domain.

### Demo Deployment

`docker-compose-demo.yml` provides a complete, self-contained stack over plain HTTP:

```
Internet → :80 → Nginx (nginx-demo.conf)
                   ├── /              → dspfront (Vue SPA on :5001)
                   ├── /api/catalog/* → catalog (Django on :5003)
                   ├── /api/*         → dspback (FastAPI on :5002)
                   └── /docs, /redoc  → dspback
                 PostgreSQL (:5432, named volume, two databases: dsp + catalog)
```

Key differences from `docker-compose-dev.yml`:

| | Dev | Demo |
|---|---|---|
| Frontend | Vite dev server on host (:8080), nginx proxies to `host.docker.internal` | Production SPA built in-container, served by internal nginx |
| Backend | `Dockerfile-dev` + `dev-entrypoint.sh`, bind-mounts source | Production `Dockerfile`, no bind-mount |
| Catalog | Bind-mounts source, gunicorn `--reload` | No source mount, auto-migrates, gunicorn without `--reload` |
| SSL | Self-signed certs (HTTPS :443) | Plain HTTP :80 |
| Postgres | Bind-mount `./dspback/postgres-data` | Named Docker volume `pgdata` |
| Config | `nginx-dev.conf` | `nginx-demo.conf` |

To deploy:
```bash
cp .env.demo .env
# Edit .env: set DEMO_HOST and OUTSIDE_HOST to VPS IP or domain
docker compose -f docker-compose-demo.yml up -d --build
```

## Vocabulary Namespaces (for OGC Building Blocks)

| Prefix | URI | Used For |
|---|---|---|
| `schema` | `http://schema.org/` | Core metadata (name, description, identifier) |
| `ada` | `https://ada.astromat.org/metadata/` | ADA-specific types |
| `cdi` | `http://ddialliance.org/Specification/DDI-CDI/1.0/RDF/` | Data structure descriptions |
| `prov` | `http://www.w3.org/ns/prov#` | Provenance (instruments) |
| `nxs` | `http://purl.org/nexusformat/definitions/` | NeXus instrument classes |
| `csvw` | `http://www.w3.org/ns/csvw#` | Tabular data |
| `spdx` | `http://spdx.org/rdf/terms#` | File checksums |
