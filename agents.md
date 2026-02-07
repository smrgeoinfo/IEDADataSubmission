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

Catalog flow (new):
User → ORCID Login → Select Profile → Fill BB-Driven Form → POST JSON-LD
                                                                 ↓
                                  catalog DB ← Django validates against profile schema
                                                 & extracts title/creators/identifier
                                                       ↓
                                               /api/catalog/records/ → JSON-LD harvesting
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
| `components/metadata/cz.ada-select-type.vue` | ADA profile selection page (`/metadata/ada`) |
| `components/metadata/cz.ada-profile-form.vue` | BB-driven ADA form (`/metadata/ada/:profile`) — fetches schema from GitHub Pages |
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

### Phase 2: BB-Driven ADA Form Builder

ADA metadata forms are now driven directly by OGC Building Block schemas rather than backend-served JSON. The flow:

1. User selects a profile at `/metadata/ada` (compact list with search filter, general product at top, analytical methods alphabetically below a divider)
2. `cz.ada-profile-form.vue` fetches `schema.json`, `uischema.json`, `defaults.json` from GitHub Pages
3. The uischema uses `Categorization` type — the form component detects this and renders Vuetify tabs (Basic Info, Attribution, Methods & Variables, Distribution, Metadata Record). Each tab gets its own `CzForm` instance sharing the same data object.
4. On save, the JSON-LD is POSTed to `/api/metadata/ada/jsonld`
5. Backend translator converts JSON-LD → flat format, validates, and stores

**Important:** CzForm's `renderers` is an internal class field (not a prop), so custom JSON Forms renderers cannot be injected. The Categorization tab handling is done at the parent component level instead.

**Schema pipeline**: `convert_for_jsonforms.py` converts the BB-validated Draft 2020-12 schemas to JSON Forms-compatible Draft 7 by resolving all `$ref`, simplifying `anyOf` patterns, converting `const` → `default`, and merging technique profile `allOf` constraints.

**Five profiles**: `adaProduct` (base), `adaEMPA`, `adaXRD`, `adaICPMS`, `adaVNMIR` — technique profiles add `enum` constraints on `schema:additionalType` and `schema:measurementTechnique`.

**Key files**:
- `OCGbuildingBlockTest/tools/convert_for_jsonforms.py` — Schema conversion script
- `OCGbuildingBlockTest/_sources/jsonforms/profiles/*/uischema.json` — Hand-crafted UI layouts
- `OCGbuildingBlockTest/_sources/jsonforms/profiles/*/defaults.json` — Default values
- `OCGbuildingBlockTest/build/jsonforms/profiles/*/schema.json` — Generated Draft 7 schemas
- `OCGbuildingBlockTest/.github/workflows/generate-jsonforms.yml` — CI workflow
- `dspfront/src/components/metadata/cz.ada-profile-form.vue` — Form component
- `dspfront/src/components/metadata/cz.ada-select-type.vue` — Profile selection

**Local dev**: Run `python tools/cors_server.py` from the `OCGbuildingBlockTest/build/jsonforms` directory to serve schemas on `http://localhost:8090` with CORS headers. The form component's `BB_BASE_URL` must be set to the local server URL during development.

### Adding a New ADA Profile

To add a new technique profile (e.g., `adaXRF`):

1. **OGC Building Block** — Create `OCGbuildingBlockTest/_sources/profiles/adaXRF/` with `bblock.json`, `schema.yaml`, `context.jsonld`, `description.md`. The `schema.yaml` should use `allOf` to extend `adaProduct` and add technique-specific `enum` constraints on `schema:additionalType` and `schema:measurementTechnique`. Copy from an existing technique profile (e.g., `adaEMPA`).
2. **JSON Forms static files** — Create `OCGbuildingBlockTest/_sources/jsonforms/profiles/adaXRF/` with `uischema.json` and `defaults.json`. Copy from an existing technique profile and adjust defaults.
3. **Schema conversion** — Add `'adaXRF'` to the `TECHNIQUE_PROFILES` list in `OCGbuildingBlockTest/tools/convert_for_jsonforms.py`.
4. **Frontend profile selection** — Add `{ key: 'adaXRF' }` to the `methodProfiles` array (alphabetically sorted) in `dspfront/src/components/metadata/cz.ada-select-type.vue`.
5. **Frontend form title** — Add `adaXRF: 'ADA XRF Product Metadata'` to the `profileNames` map in `dspfront/src/components/metadata/cz.ada-profile-form.vue`.
6. **i18n strings** — Add the profile entry under `metadata.ada.profiles` in `dspfront/src/i18n/messages.ts`.

## Catalog Backend (dspback-django)

The Django catalog backend provides generic Profile and Record management. Profiles are loaded from OGC Building Block build output; records store JSON-LD natively with JSON Schema validation.

### Key Files

| File | What It Does |
|---|---|
| `dspback-django/catalog/settings.py` | Django settings (DB, auth, DRF, JWT, ORCID, CORS) |
| `dspback-django/catalog/urls.py` | Root URL config — mounts records and accounts |
| `dspback-django/accounts/models.py` | Custom User with ORCID as USERNAME_FIELD |
| `dspback-django/accounts/authentication.py` | JWT auth (Bearer header + ?access_token= query param) |
| `dspback-django/accounts/views.py` | ORCID OAuth login/callback/logout, JWT issuance |
| `dspback-django/accounts/adapters.py` | allauth adapter populating orcid from social login UID |
| `dspback-django/records/models.py` | Profile (schema/uischema/defaults/base_profile), Record (UUID PK, JSON-LD, GIN index) |
| `dspback-django/records/serializers.py` | DRF serializers with validation + field extraction hooks |
| `dspback-django/records/views.py` | ProfileViewSet (lookup by name), RecordViewSet (CRUD + jsonld/import actions) |
| `dspback-django/records/validators.py` | JSON Schema validation (auto-detects Draft-07 vs Draft-2020-12) |
| `dspback-django/records/services.py` | extract_indexed_fields() from JSON-LD, fetch_jsonld_from_url() |
| `dspback-django/records/management/commands/load_profiles.py` | Loads profiles from OGC BB build output, sets parent relationships |

### API Endpoints

All under `/api/catalog/`:
- `profiles/` — CRUD for metadata profiles (public read, admin write), lookup by name
- `records/` — CRUD for JSON-LD records (public read, authenticated create, owner edit/delete)
- `records/{id}/jsonld/` — Raw JSON-LD export with `application/ld+json` content type
- `records/import-url/`, `records/import-file/` — Import from URL or file upload
- `admin/` — Django admin for Profile and Record inspection

### Record Lifecycle

1. `POST /api/catalog/records/` with `{profile: <id>, jsonld: {...}}`
2. Serializer validates JSON-LD against the profile's JSON Schema
3. `extract_indexed_fields()` pulls title (from `schema:name`), creators (from `schema:creator.@list[].schema:name`), identifier (from `@id` or `schema:identifier`)
4. Record stored with extracted fields for search/filter, full JSON-LD as source of truth
5. `GET /api/catalog/records/{id}/jsonld/` returns the raw JSON-LD for harvesting

## Deployment

Three Docker Compose configurations at the repo root:

| File | When to Use |
|---|---|
| `docker-compose-dev.yml` | Backend-only dev (backend + nginx, no frontend) |
| `docker-compose-upstream.yml` | Full stack built from source |
| `docker-compose-artifact-registry.yml` | Full stack from pre-built images |

Nginx (`nginx/`) reverse proxies `/api/catalog/*` to the Django catalog backend (port 5003), `/api/*` to FastAPI (port 5002), and everything else to the frontend (port 5001). SSL termination happens at nginx. The `/api/catalog` location block must appear before `/api` in the nginx config for correct routing.

Environment variables (PostgreSQL credentials, OAuth credentials, JWT secrets) are in `.env` at the repo root.

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
