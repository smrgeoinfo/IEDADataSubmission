# Agents Guide: IEDA Data Submission Portal

This document explains what this project is, how it works, and how to navigate the codebase when making changes.

## What This Project Is

The IEDA Data Submission Portal (repo: `smrgeoinfo/IEDADataSubmission`) is a web application that lets Earth Science researchers submit, manage, and discover research data across multiple repositories from a single interface. Researchers log in once with their ORCID, fill out standardized metadata forms, and submit to repositories like HydroShare, EarthChem, Zenodo, and ADA (Astromat Data Archive).

The project is a monorepo with three main components. `dspback` and `dspfront` are git submodules (tracking `develop` branch from `smrgeoinfo/dspback` and `smrgeoinfo/dspfront` respectively):

| Component | Stack | Purpose |
|---|---|---|
| `dspback/` | FastAPI, MongoDB (Motor/Beanie), Python | REST API for metadata CRUD, auth, search |
| `dspfront/` | Vue 3, TypeScript, Vuex ORM, Vuetify | SPA for forms, submissions, discovery |
| `OCGbuildingBlockTest/` | YAML schemas, JSON-LD | Modular schema components (OGC Building Blocks) |

## How It Works End-to-End

```
User → ORCID Login → Select Repository → Fill Schema-Driven Form → Submit
                                                                      ↓
                                              MongoDB ← Backend validates & stores
                                                ↓
                                          Atlas Search → Discovery API → Search Results
```

### 1. Authentication (Two Levels)

**User auth:** ORCID OAuth2 → JWT token stored in MongoDB `User` document and cookie.

**Repository auth:** Per-repository OAuth2 (HydroShare, Zenodo, EarthChem). Tokens stored as `RepositoryToken` documents linked to user. ADA and External repos skip this (no OAuth needed).

### 2. Schema-Driven Forms

Each repository has three files in `dspback/dspback/schemas/{repo}/`:

- `schema.json` — JSON Schema defining fields and validation rules
- `uischema.json` — JSON Forms UI Schema controlling layout, grouping, widgets
- `defaults.json` — Default values pre-populated in the form

The frontend fetches these from `/api/schema/{repo}/` and passes them to the JSON Forms renderer, which dynamically generates Vuetify form components. This means **changing a repository's form only requires editing JSON files**, not code.

### 3. Metadata Submission

1. Frontend POSTs form JSON to `/api/metadata/{repo}`
2. Backend validates against auto-generated Pydantic model (from `schema.json`)
3. `Record.to_submission()` extracts title, authors, URL into a `Submission` document
4. Full metadata JSON stored as string in `Submission.metadata_json`
5. Submission linked to user via `User.submissions` array

### 4. Discovery

MongoDB Atlas Search indexes the `discovery` collection. The `/api/discovery/search` endpoint builds aggregation pipelines with fuzzy matching, faceted filtering (content type, provider, dates, CZO clusters), and pagination.

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

Complex schemas (like ADA's 37 `$defs`) are decomposed into modular directories under `OCGbuildingBlockTest/_sources/`. Each building block has `bblock.json`, `schema.yaml`, `context.jsonld`, and `description.md`. Cross-references use relative `$ref` paths. The top-level profile (`profiles/adaProduct/`) composes all blocks.

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
| `dspback/dspback/pydantic_schemas.py` | `RepositoryType` enum, `User`/`Submission`/`RepositoryToken` Beanie documents, record models |

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

## Deployment

Three Docker Compose configurations at the repo root:

| File | When to Use |
|---|---|
| `docker-compose-dev.yml` | Backend-only dev (backend + nginx, no frontend) |
| `docker-compose-upstream.yml` | Full stack built from source |
| `docker-compose-artifact-registry.yml` | Full stack from pre-built images |

Nginx (`nginx/`) reverse proxies `/api/*` to the backend (port 5002) and everything else to the frontend (port 5001). SSL termination happens at nginx.

Environment variables (MongoDB URI, OAuth credentials, JWT secrets) are in `.env` at the repo root.

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
